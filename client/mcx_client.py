import requests
import time
import json
import os
from urllib.parse import urlencode

# ----------------- CONFIG -----------------
# The URL of your local mitmproxy instance
PROXIES = {
    'http': 'http://127.0.0.1:8080',
    'https': 'http://127.0.0.1:8080',
}

# The target URL of the web application
TARGET_URL = "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do"

# Define the user agent that your proxy will look for to identify this client.
USER_AGENT = "MCX-Client-Margin-1.0"

# The file containing the static part of the request body
PAYLOAD_FILE = "payload.txt"
# ----------------- END CONFIG -----------------

def run_client():
    """
    Sends a single request to the target server via the proxy.
    """
    try:
        # Load the static part of the request body from a file.
        with open(PAYLOAD_FILE, 'r', encoding='utf-8') as f:
            static_payload = f.read()

        # Define the headers to match the browser's request exactly.
        headers = {
            "Host": "eclear.mcxccl.com",
            "User-Agent": USER_AGENT,  # This is the key for the proxy
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://eclear.mcxccl.com",
            "Connection": "keep-alive",
            "Referer": "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do?app=bancsapp?prefix=/RSK&page=/RSK335.do&confViewSize=22&reqType=0&mode=DEF_MODE&cParent=&parentName=blank&browserType=IE55&GuiWinName=RSK335&compname=RSK&locale=&winlocale=&over_ride_button=Cancel&AvlHt=726&AvlWd=983&tblWd=967&GuiBrowserInst=0&theme=black&confViewSize=22&pageId=RSK335&wintitle=Margin%20Utilization%20View&availHeight=820&availWidth=1067&tabid=2&",
        }

        print("Sending request to proxy...")

        # Send the POST request to the target URL.
        # The proxy is configured to inject cookies, IXHRts, and rndaak.
        # `verify=False` is used to skip SSL verification for the proxy's self-signed certificate.
        response = requests.post(
            TARGET_URL,
            headers=headers,
            data=static_payload,
            proxies=PROXIES,
            verify=False
        )

        print(f"\nResponse Status Code: {response.status_code}")
        print("Response Body:")
        print(response.text)

        # Check for successful response
        if "unable to process the request" not in response.text:
            print("\nRequest was successful!")
        else:
            print("\nRequest failed. Check the response body for details.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_client()
