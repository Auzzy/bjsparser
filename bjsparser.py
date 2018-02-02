import atexit
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
    return browser

def strip_html(text):
    text = OPEN_CLOSE_TAG_RE.sub("", text)
    text = SINGLE_TAG_RE.sub("", text)
    text = text.replace("&amp;", "&")
    return text

def filter_in_club(browser):
    browser.click_link_by_partial_text("In Club")
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
            raise Exception("Next page failed to load.")

        product_pages.update(parse_items(browser))
    return product_pages

def get_products(browser, category_urls):
    products_by_category = {}
    for category, url in category_urls.items():
        browser.visit(url)
        if not browser.is_element_present_by_css(".below-header", wait_time=5):
            raise Exception("Category page failed to load")
        
        products_by_category[category] = {}
        if browser.is_element_present_by_id("cat"):
            if browser.is_element_present_by_css("div.product-area"):
                # item list page (e.g. http://www.bjs.com/computers/laptops.category.747.743.2002360.1)
                increase_items_per_page(browser)
                filter_in_club(browser)
                products = parse_items(browser)
                products_by_category[category].update(products)
            elif browser.is_element_present_by_css("div.categories"):
                # subcategory page (e.g. http://www.bjs.com/fresh--refrigerated-food/bakery.category.3000000000000117225.3000000000000117224.2001257.1)
                subcategory_cells = browser.find_by_css("a.cat")
                subcategory_pages = {subcategory_cell.text: subcategory_cell["href"] for subcategory_cell in subcategory_cells}
                products_by_subcategory = get_products(browser, subcategory_pages)
                products_by_category[category].update(products_by_subcategory)
            else:
                # unrecognized page
                pass
        else:
            # special landing page (e.g. http://www.bjs.com/apple.content.minisite_apple.B#/selection)
            pass

    return products_by_category

def get_category_urls(browser):
    shop_menu = browser.find_by_xpath("//ul[contains(@class, 'menu') and @role='menubar']")
    category_elements = shop_menu.find_by_xpath(".//li[not(contains(@class, 'is-drilldown-submenu-parent')) and not(contains(@class, 'js-drilldown-back'))]/a")

    category_pages = defaultdict(set)
    for category_anchor in category_elements:
        category_name = strip_html(category_anchor.html)
        category_pages[category_name].add(category_anchor["href"])
    return category_pages

def set_as_club(browser):
    browser.find_by_id("shopClubBtn").click()
    
    time.sleep(2)

    if browser.find_by_xpath(FIND_A_CLUB_XPATH).text.lower() != "bj's medford":
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
        raise Exception("Couldn't find \"Find a Club\"")

    browser.find_by_xpath(FIND_A_CLUB_XPATH).click()

    if not browser.is_element_present_by_xpath("//div[contains(@class, 'find-a-club')]", wait_time=5):
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