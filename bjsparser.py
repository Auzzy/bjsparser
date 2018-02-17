import atexit
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict

from splinter import Browser

# Two appear on the page, but only the one whose parent is 'title-bar' is visible
FIND_A_CLUB_XPATH = "//div[contains(@class, 'title-bar')]//span[contains(@class, 'club-name')]/parent::a"

PHANTOMJS_URL = "https://bitbucket.org/ariya/phantomjs/downloads/phantomjs-2.1.1-linux-x86_64.tar.bz2"
OPEN_CLOSE_TAG_RE = re.compile(r"<(.*?)>.*?</\1>")
SINGLE_TAG_RE = re.compile("<.*?>")

ITEMS_CACHE_FILEPATH = ".cache.items.json"
COMPLETED_CACHE_FILEPATH = ".cache.completed.json"


def install_phantomjs(phantomjs_url=PHANTOMJS_URL):
    filename = "phantomjs.tar.bz2"
    
    tempdir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tempdir)
    
    filepath = os.path.join(tempdir, filename)
    download_phantomjs_cmd = "wget {0} -O {1}".format(phantomjs_url, filepath)
    subprocess.call(shlex.split(download_phantomjs_cmd))

    untar_phantomjs_cmd = "tar -xjvf {0} -C {1}".format(filepath, tempdir)
    untar_output = subprocess.check_output(shlex.split(untar_phantomjs_cmd))
    phantomjs_dir = untar_output.splitlines()[0].decode('utf-8')

    os.environ["PATH"] += ":" + os.path.join(tempdir, phantomjs_dir, "bin")

def init_browser():
    browser = Browser("phantomjs")
    browser.driver.set_window_size(2000, 10000)
    browser.driver.set_page_load_timeout(30)
    return browser

def strip_html(text):
    text = OPEN_CLOSE_TAG_RE.sub("", text)
    text = SINGLE_TAG_RE.sub("", text)
    text = text.replace("&amp;", "&")
    return text

def filter_in_club(browser):
    if not browser.is_element_present_by_css(".counts .club", wait_time=5):
        print(browser.url)
        raise Exception("\"In Club\" button missing.")

    browser.find_by_css(".counts .club").click()
    time.sleep(2)

def increase_items_per_page(browser):
    pagination_select = browser.find_by_xpath("//select[@name='pagination']")[0]
    option_values = {int(option.text.split()[0].strip()): option["value"] for option in pagination_select.find_by_tag("option")}
    pagination_select.select(option_values[max(option_values.keys())])
    time.sleep(2)

def parse_items(browser):
    product_cells = browser.find_by_css("div.product")
    product_pages = {product_cell.find_by_css("p.title")[0].text: product_cell.find_by_tag("a")[0]["href"] for product_cell in product_cells}
    if browser.is_element_present_by_css("a.next"):
        browser.find_by_css("a.next").click()
        if not browser.is_element_present_by_css(".below-header", wait_time=5):
            print(browser.url)
            raise Exception("Next page failed to load.")

        product_pages.update(parse_items(browser))
    return product_pages

def handle_category_page(browser, category_path, cache):
    if browser.is_element_present_by_id("cat"):
        if browser.is_element_present_by_css("div.product-area"):
            # item list page (e.g. http://www.bjs.com/computers/laptops.category.747.743.2002360.1)
            increase_items_per_page(browser)
            filter_in_club(browser)
            products = parse_items(browser)
            write_item_cache(cache, products, category_path)
            return products
        elif browser.is_element_present_by_css("div.categories"):
            # subcategory page (e.g. http://www.bjs.com/fresh--refrigerated-food/bakery.category.3000000000000117225.3000000000000117224.2001257.1)
            subcategory_cells = browser.find_by_css("a.cat")
            subcategory_pages = {subcategory_cell.text: [subcategory_cell["href"]] for subcategory_cell in subcategory_cells}
            products = walk_products(browser, subcategory_pages, category_path, cache)
            cache_subcategories_complete(cache, category_path)
            return products
        else:
            print("UNRECOGNIZED PAGE SETUP: {}".format(browser.url))
    else:
        # special landing page (e.g. http://www.bjs.com/apple.content.minisite_apple.B#/selection)
        pass

def visit_category_page(browser, category, url):
    print("{}: {}".format(category, url))
    browser.visit(url)
    if not browser.is_element_present_by_css(".below-header", wait_time=5):
        print("Category page failed to load. Trying again...")
        browser.visit(url)
        if not browser.is_element_present_by_css(".below-header", wait_time=5):
            print(browser.url)
            raise Exception("Category page failed to load")

def cache_subcategories_complete(cache, category_path):
    # Handles the lack a parent category, such as "View All".
    if not category_path:
        return

    subcategory_items = {}
    # Convert to list to allow key deletion while iterating
    for key, value in list(cache["items"].items()):
        if category_path == key[:-1]:
            subcategory_items.update(value)
            del cache["items"][key]
            del cache["serializable_items"][">".join(key)]
    cache["items"][category_path] = subcategory_items
    cache["serializable_items"][">".join(category_path)] = subcategory_items

    items_cache_json = json.dumps(cache["serializable_items"])
    with open(ITEMS_CACHE_FILEPATH, 'w') as cache_file:
        cache_file.write(items_cache_json)

def write_item_cache(cache, products, category_path):
    cache["items"][category_path] = products
    cache["serializable_items"][">".join(category_path)] = products
    items_cache_json = json.dumps(cache["serializable_items"])
    with open(ITEMS_CACHE_FILEPATH, 'w') as cache_file:
        cache_file.write(items_cache_json)

def write_completed_cache(cache, category_path):
    # Handles the lack a parent category, such as "View All".
    if not category_path:
        return

    cache["completed"].append(category_path)
    completed_cache_json = json.dumps(cache["completed"])
    with open(COMPLETED_CACHE_FILEPATH, 'w') as cache_file:
        cache_file.write(completed_cache_json)

def walk_products(browser, category_urls, parent_categories, cache):
    products_by_category = {}
    for category, urls in category_urls.items():
        category_path = parent_categories + ((category,) if category != "View All" else tuple())
        if list(category_path) in cache["completed"]:
            if category_path in cache["items"]:
                products_by_category[category] = cache["items"][category_path]
        else:
            products_by_category[category] = {}
            for url in urls:
                visit_category_page(browser, category, url)
                products = handle_category_page(browser, category_path, cache)
                products_by_category[category].update(products)
            write_completed_cache(cache, category_path)

    return products_by_category

def load_cache():
    cache = {"items": {}, "serializable_items": {}, "completed": []}

    if os.path.exists(ITEMS_CACHE_FILEPATH):
        with open(ITEMS_CACHE_FILEPATH) as cache_file:
            raw_cache_contents = cache_file.read()
        if raw_cache_contents:
            cache["serializable_items"] = json.loads(raw_cache_contents)
            cache["items"] = {tuple(key.split(">")): value for key, value in cache["serializable_items"].items()}
    
    if os.path.exists(COMPLETED_CACHE_FILEPATH):
        with open(COMPLETED_CACHE_FILEPATH) as cache_file:
            raw_cache_contents = cache_file.read()
        if raw_cache_contents:
            cache["completed"] = json.loads(raw_cache_contents)

    return cache

def write_completed_cache(cache, category_path):
    cache["completed"].append(category_path)
    with open(COMPLETED_CACHE_FILEPATH, 'w') as cache_file:
        json.dump(cache["completed"], cache_file)

    return cache

def get_products(browser, category_urls):
    cache = load_cache()
    return walk_products(browser, category_urls, tuple(), cache)

def get_category_urls(browser):
    category_elements = browser.find_by_xpath("//li[contains(@class, 'is-drilldown-submenu-item') and not(contains(@class, 'is-drilldown-submenu-parent')) and not(contains(@class, 'js-drilldown-back'))]/a")

    category_pages = defaultdict(list)
    for category_anchor in category_elements:
        category_name = strip_html(category_anchor.html)
        category_pages[category_name].append(category_anchor["href"])
    return category_pages

def set_as_club(browser):
    browser.find_by_id("shopClubBtn").click()
    
    time.sleep(5)

    if browser.find_by_xpath(FIND_A_CLUB_XPATH).text.lower() != "bj's medford":
        print(browser.url)
        raise Exception("Club doesn't seem to be set.")

def enter_location(browser):
    club_search_form = browser.find_by_xpath("//form[@id='locator_dropdown']")[0]
    club_search_form.find_by_xpath("//select[@name='clubState']").select("MA")
    
    town_value = club_search_form.find_by_text("Medford").value
    club_search_form.find_by_xpath("//select[@name='clubTown']").select(town_value)

    if not browser.is_element_present_by_id("shopClubBtn", wait_time=5):
        raise Exception("The page doesn't seem to have loaded.")

def find_a_club(browser):
    """The URL of "Find a Club" appears to be managed by a CMS, so it's subject to change. Looking for the button and
    clicking it is more reliable.
    """
    if not browser.is_element_present_by_xpath(FIND_A_CLUB_XPATH, wait_time=5):
        print(browser.url)
        raise Exception("Couldn't find \"Find a Club\"")

    browser.find_by_xpath(FIND_A_CLUB_XPATH).click()

    if not browser.is_element_present_by_xpath("//div[contains(@class, 'find-a-club')]", wait_time=5):
        print(browser.url)
        raise Exception("The Find a Club page does not seem to have loaded.")

def select_my_club(browser):
    browser.visit("http://www.bjs.com/")
    find_a_club(browser)
    enter_location(browser)
    set_as_club(browser)
    
if __name__ == "__main__":
    install_phantomjs()
    with init_browser() as browser:
        select_my_club(browser)
        category_urls = get_category_urls(browser)
        products_by_category = get_products(browser, category_urls)
        for category, products in products_by_category.items():
            with open(os.path.join("inventory", category.replace(" ", "-"))) as category_file:
                json.dump(products, category_file)
