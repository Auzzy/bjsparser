import argparse

from bjsparserlib import download_and_populate

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("database_filepath", help="Path to a database file to dump the inventory. If the file doesn't exist, it will be created.")
    parser.add_argument("--inventory-filepath", help="Path to a file to store the inventory as JSON. This allows caching, as well as rebuilding the database.")
    return vars(parser.parse_args())

if __name__ == "__main__":
    args = parse_args()

    download_and_populate(args.get("inventory_filepath"), args["database_filepath"])