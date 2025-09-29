from bs4 import BeautifulSoup
import json
import time
import os
import configparser

CURR_DIR = os.path.dirname(os.path.abspath(__file__))
print("CURR_DIR", CURR_DIR)
# CURR_DIR C:\Users\admin01\Desktop\get_margin_data\parser

path_with_dots = os.path.join(CURR_DIR, '..', 'calls', 'browser-calls', 'responses', 'curr_response.txt')

RESPONSE_FILE_PATH = os.path.normpath(path_with_dots)

print("RESOLVED_PATH", RESPONSE_FILE_PATH) 

# ../calls/browser-calls/responses/curr_response.txt

output_path = os.path.join(CURR_DIR, "margin-utilization-view.json")

def parse_response():
    # Load the uploaded response.txt file
    with open(RESPONSE_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse HTML
    soup = BeautifulSoup(content, "html.parser")

    # Locate the table by id
    table = soup.find("table", {"id": "RSK335_Table"})

    if table:
        # Extract headers
        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]

        # Extract first row values
        row = table.find("tbody").find("tr")
        values = [td.get_text(strip=True) for td in row.find_all("td")]

        # Combine into dictionary
        table_data = dict(zip(headers, values))

        # Save to JSON file
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(table_data, f, indent=4, ensure_ascii=False)

        print("table parsed")

if __name__ == "__main__":
    while True:
        parse_response()
        time.sleep(10)  # wait 10 seconds