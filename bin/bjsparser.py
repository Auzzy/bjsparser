import argparse

from bjsparserlib import download

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory_filepath", help="Path to a file to store the inventory as JSON.")
    return vars(parser.parse_args())

if __name__ == "__main__":
    args = parse_args()

    download(args["inventory_filepath"])