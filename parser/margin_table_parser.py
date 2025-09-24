from bs4 import BeautifulSoup
import json

# Load the uploaded response.txt file
file_path = "../calls/template/response.txt"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Parse HTML
soup = BeautifulSoup(content, "html.parser")

# Locate the table by id
table = soup.find("table", {"id": "RSK335_Table"})

# Extract headers
headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]

# Extract first row values
row = table.find("tbody").find("tr")
values = [td.get_text(strip=True) for td in row.find_all("td")]

# Combine into dictionary
table_data = dict(zip(headers, values))

# Save to JSON file
output_path = "margin-info.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(table_data, f, indent=4, ensure_ascii=False)

output_path
