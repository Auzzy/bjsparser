import json
import requests
import time

BJS_CLUB_ID = "0001"
BJS_API_ENDPOINT = "https://bjswholesale-cors.groupbycloud.com/api/v1/search"
PAGE_SIZE = 120
FIELDS = [
    "title",
    "gbi_categories",
    "visualVariant.nonvisualVariant.product_url",
    "visualVariant.nonvisualVariant.clubid_price",
    "visualVariant.nonvisualVariant.displayPrice"
]
REFINEMENTS = [
    {
        "navigationName": "visualVariant.nonvisualVariant.availability",
        "type": "Value",
        "value": f"Club{BJS_CLUB_ID}"
    }
]
EXCLUDE_CATEGORIES = [
    "TVs & Home Theater",
    "Computers & Tablets",
    "Office",
    "Furniture",
    "Patio & Outdoor Living",
    "Lawn & Garden",
    "Baby & Kids",
    "Sports & Fitness",
    "Toys & Video Games",
    "Jewelry",
    "Apparel",
    "Gift Cards",
    "Clearance"
]


def done(page_json):
    return get_end_index(page_json) == page_json["totalRecordCount"]

def get_end_index(page_json):
    return page_json["pageInfo"]["recordEnd"]

def get_price(item_info):
    prices = set()
    for item in item_info["visualVariant"]:
        variant = item["nonvisualVariant"][0]
        clubid_price = variant.get("clubid_price")
        if clubid_price:
            prices.add(dict([price_and_club.split("_") for price_and_club in clubid_price.split(";")])[BJS_CLUB_ID])
        else:
            prices.add(variant["displayPrice"])

    max_price = max(prices)
    min_price = min(prices)
    return (max_price, ) if max_price == min_price else (min_price, max_price)

def process_page_items(page_json):
    page_items = []
    for item in page_json["records"]:
        item_info = item["allMeta"]

        # I'm unsure why some products have a gbi_categories value of null...
        gbi_categories = [gbi_category for gbi_category in item_info["gbi_categories"] if gbi_category]

        categories = []
        for gbi_category in gbi_categories:
            categories.append([gbi_category[index] for index in sorted(gbi_category) if gbi_category[index]])

        page_items.append({
            "name": item_info["title"],
            "categories": categories,
            "url": item_info["visualVariant"][0]["nonvisualVariant"][0]["product_url"],
            "price": get_price(item_info)
        })

    return page_items

def create_payload(start_index):
    return {
        "skip": start_index,
        "pageSize": PAGE_SIZE,
        "fields": FIELDS,
        "refinements": REFINEMENTS,
        "area": "BCProduction",
        "collection": "productionB2CProducts",
        "sort": {
            "field": "_relevance",
            "order": "Descending"
        },
        "excludedNavigations": [
            "visualVariant.nonvisualVariant.availability"
        ],
        "biasing": {
            "biases": []
        },
        "query": None
    }

def send_request(start_index):
    response = requests.post(BJS_API_ENDPOINT, json=create_payload(start_index))
    return response.json()

def _update_inventory(current_inventory, new_inventory, inventory_filepath):
    current_inventory["inventory"].extend(new_inventory)

    if inventory_filepath:
        with open(inventory_filepath, 'w') as bjs_items_file:
            json.dump(current_inventory, bjs_items_file)

    return current_inventory

def _clear_inventory(inventory_filepath):
    inventory = {"inventory": []}
    with open(inventory_filepath, 'w') as bjs_inventory_file:
        json.dump(inventory, bjs_inventory_file)
    return inventory

def download(inventory_filepath):
    inventory = {}
    if inventory_filepath:
        inventory = _clear_inventory(inventory_filepath)
    
    start_index = 0
    while True:
        page_json = send_request(start_index)
        page_inventory = process_page_items(page_json)
        inventory = _update_inventory(inventory, page_inventory, inventory_filepath)

        if done(page_json):
            break

        start_index = get_end_index(page_json)

        # Since this is an unofficial API, self-throttle to avoid pissing them off.
        time.sleep(5)

    return inventory