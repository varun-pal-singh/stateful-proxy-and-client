from bs4 import BeautifulSoup
import json
import time
import configparser

config = configparser.ConfigParser()
config.read('../config/config.ini')

RESPONSE_FILE_PATH = config['PATH']['RESPONSE_FILE_PATH']
output_path = "margin-utilization-view.json"

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

        output_path

if __name__ == "__main__":
    while True:
        parse_response()
        time.sleep(10)  # wait 10 seconds