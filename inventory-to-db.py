import collections
import json
import os
import sqlite3
import sys

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
    ["Jewelry", "Rings", "Diamond Rings"],
    "Apparel",
    "Gift Cards",
    "Clearance"
]

def load_inventory():
    with open("products.json") as bjs_items_file:
        return json.load(bjs_items_file)

def _insert_if_new(table_name, data):
    colnames = list(data.keys())
    coldata = [data[colname] for colname in colnames]

    sql_where_format = " AND ".join(["{} = ?".format(colname) for colname in colnames])
    sql_where = "SELECT id FROM {} WHERE {}".format(table_name, sql_where_format)
    cursor.execute(sql_where, coldata)

    category_rows = cursor.fetchall()
    if not category_rows:
        sql_insert_format = ", ".join(colnames)
        sql_insert_values_format = ", ".join(len(colnames) * "?")
        sql_insert = "INSERT INTO {} ({}) VALUES ({})".format(table_name, sql_insert_format, sql_insert_values_format)
        cursor.execute(sql_insert, coldata)
        return cursor.lastrowid
    elif len(category_rows) == 1:
        return category_rows[0][0]
    else:
        raise Exception("There are multiple rows matching {}".format(data))

def insert_categories(categories, store):
    if categories:
        category = max(categories, key=len)
    else:
        return None

    parent_id = _insert_if_new("categories", {"name": category[0], "store": store})
    for subcategory in category[1:]:
        parent_id = _insert_if_new("categories", {"name": subcategory, "store": store, "parentid": parent_id})
    return parent_id

def exclude(categories, exclude_categories):
    for category in categories:
        if tuple(category) in exclude_categories:
            return True
    return False

db_path = sys.argv[1] if len(sys.argv) >= 2 else "inventory.db"
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("PRAGMA foreign_keys = ON")
cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, store TEXT, parentid INTEGER, FOREIGN KEY(parentid) REFERENCES categories(id))")
cursor.execute("""CREATE TABLE IF NOT EXISTS products (name, categoryid, url, store, stocked)""")

# Create a set of all category paths. So if the list above contains ["Jewelry", "Rings", "Diamond Rings"],
# the generated list will contain ("Jewelry",), ("Jewelry", "Rings"), and ("Jewelry", "Rings", "Diamond Rings").
exclude_categories = set()
for category in EXCLUDE_CATEGORIES:
    category_item = (category, ) if isinstance(category, str) else tuple(category)
    for index in range(len(category_item)):
        exclude_categories.add(category_item[:index + 1])

store = "BJs"
inventory = load_inventory()
for item in inventory["items"]:
    if exclude(item["categories"], exclude_categories):
        continue

    category_id = insert_categories(item["categories"], store)
    if not category_id:
        print("No category information for {}".format(item["name"]))
        continue

    cursor.execute("INSERT INTO products (name, categoryid, url, store, stocked) VALUES (?, ?, ?, ?, ?)", (item["name"], category_id, item["url"], store, None))

connection.commit()
connection.close()
