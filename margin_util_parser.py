#!/usr/bin/env python3
import os
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup

RESP_DIR = "./margin_calls/responses"
PREFERRED = os.path.join(RESP_DIR, "response5.txt")
TARGET_ATTR = "wca_utilizedcolpercent"   # header attr for "Margin Utilization"
TARGET_TEXT = "margin utilization"

def pick_input_file():
    # Prefer explicit response.txt if present, otherwise choose newest file in directory
    if os.path.isfile(PREFERRED):
        return PREFERRED
    try:
        files = [
            os.path.join(RESP_DIR, f)
            for f in os.listdir(RESP_DIR)
            if os.path.isfile(os.path.join(RESP_DIR, f))
        ]
        if not files:
            return None
        newest = max(files, key=os.path.getmtime)
        return newest
    except Exception:
        return None

def parse_number(s):
    if s is None:
        return None
    s = str(s).strip()
    # remove commas and surrounding parentheses
    s_clean = s.replace(",", "").replace("(", "-").replace(")", "")
    # handle common scientific notation as string
    try:
        return float(s_clean)
    except Exception:
        # fallback: regex extract a number
        m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s_clean)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
    return None

def extract_margin_utilization_from_html(content):
    soup = BeautifulSoup(content, "html.parser")

    # Prefer the table with id RSK335_Table, else first table
    table = soup.find("table", id="RSK335_Table") or soup.find("table")
    if not table:
        return None

    # find headers
    thead = table.find("thead")
    headers = thead.find_all("th") if thead else []

    mu_index = None
    tgt_lower = TARGET_ATTR.lower()
    for i, th in enumerate(headers):
        # check attributes values (case-insensitive)
        for k, v in th.attrs.items():
            # attributes values can be strings or lists
            if isinstance(v, str) and v.strip().lower() == tgt_lower:
                mu_index = i
                break
            if isinstance(v, (list, tuple)):
                vals = [str(x).strip().lower() for x in v]
                if tgt_lower in vals:
                    mu_index = i
                    break
        if mu_index is not None:
            break
        # check visible header text
        text = th.get_text(strip=True).lower() if th.get_text() else ""
        if TARGET_TEXT in text:
            mu_index = i
            break

    # find first data row
    tbody = table.find("tbody")
    row = tbody.find("tr") if tbody else table.find("tr")
    if not row:
        return None
    cells = row.find_all("td")

    # If we have an index, grab that cell (preferred)
    if mu_index is not None and mu_index < len(cells):
        td = cells[mu_index]
        raw = td.get("svrVal") or td.get("svrval") or td.text.strip()
        num = parse_number(raw)
        if num is not None:
            return {"num": num, "fmt": f"{num:,.2f}", "raw": raw, "source": "svrVal/index"}
        else:
            # fallback to visible text
            visible = td.text.strip()
            num2 = parse_number(visible)
            if num2 is not None:
                return {"num": num2, "fmt": f"{num2:,.2f}", "raw": visible, "source": "visible/index"}

    # Fallback: try wcStrut mapping (a list of column keys in order)
    wc_input = soup.find("input", id=lambda i: i and i.startswith("wcStrut"))
    if wc_input and wc_input.has_attr("value"):
        wc_val = wc_input["value"]
        cols = re.findall(r"'([^']+)'", wc_val)  # extract keys from c=['a','b',...]
        cols_lower = [c.lower() for c in cols]
        if TARGET_ATTR.lower() in cols_lower:
            idx = cols_lower.index(TARGET_ATTR.lower())
            if idx < len(cells):
                td = cells[idx]
                raw = td.get("svrVal") or td.get("svrval") or td.text.strip()
                num = parse_number(raw)
                if num is not None:
                    return {"num": num, "fmt": f"{num:,.2f}", "raw": raw, "source": "wcStrut"}

    # Final fallback: scan cells and return the first numeric-looking cell
    for td in cells:
        raw = td.get("svrVal") or td.get("svrval") or td.text.strip()
        num = parse_number(raw)
        if num is not None:
            return {"num": num, "fmt": f"{num:,.2f}", "raw": raw, "source": "first_numeric_fallback"}

    return None

def extract_margin_utilization(file_path, retries=2, retry_delay=0.2):
    # Try to read and parse. If parsing finds nothing, retry shortly (helps when file is being written)
    for attempt in range(retries + 1):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return None

        res = extract_margin_utilization_from_html(content)
        if res:
            return res
        if attempt < retries:
            time.sleep(retry_delay)
    return None

def main_loop():
    last_file = None
    last_mtime = None
    print("Watching for response files in:", RESP_DIR)
    while True:
        filepath = pick_input_file()
        if not filepath:
            print("No response files found. (Make sure", RESP_DIR, "exists.)")
        else:
            try:
                mtime = os.path.getmtime(filepath)
            except Exception:
                mtime = None

            # Only re-process when file or modification time changed
            if filepath != last_file or mtime != last_mtime:
                print("\n------------------------------------------------------------")
                print("Processing file:", filepath)
                if mtime:
                    print("Modified:", datetime.fromtimestamp(mtime).isoformat())
                res = extract_margin_utilization(filepath)
                if res:
                    print("Margin Utilization:", res["fmt"], f"(raw: {res['raw']})  [source: {res['source']}]")
                else:
                    print("Margin Utilization not found in file.")
                last_file = filepath
                last_mtime = mtime
            else:
                # file unchanged — print a small heartbeat
                print(".", end="", flush=True)
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
