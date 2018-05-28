import json
import requests
import time

ITEMS_FILEPATH = "products.json"

BJS_CLUB_ID = "Club0001"
BJS_API_ENDPOINT = "https://bjswholesale-cors.groupbycloud.com/api/v1/search"
PAGE_SIZE = 120
FIELDS = [
    "title",
    "gbi_categories",
    "visualVariant.nonvisualVariant.product_url"
]
REFINEMENTS = [
    {
        "navigationName": "visualVariant.nonvisualVariant.availability",
        "type": "Value",
        "value": BJS_CLUB_ID
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

def _write_items(new_items):
    with open(ITEMS_FILEPATH, 'r') as bjs_items_file:
        current_items = json.load(bjs_items_file)

    current_items["items"].extend(new_items)
    with open(ITEMS_FILEPATH, 'w') as bjs_items_file:
        json.dump(current_items, bjs_items_file)

def _clear_items():
    with open(ITEMS_FILEPATH, 'w') as bjs_items_file:
        json.dump({"items": []}, bjs_items_file)

def download_raw_bjs_inventory():
    _clear_items()

    start_index = 0
    while True:
        page_json = send_request(start_index)
        page_items = process_page_items(page_json)
        _write_items(page_items)

        if done(page_json):
            break

        start_index = get_end_index(page_json)

        # Since this is an unofficial API, self-throttle to avoid pissing them off.
        time.sleep(5)

if __name__ == "__main__":
    download_raw_bjs_inventory()
