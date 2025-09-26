import requests
import configparser

config = configparser.RawConfigParser()
config.read('../config/config.ini')

MARGIN_URL = config['CREDENTIALS']['MARGIN_URL']
USER_AGENT = config["REQUEST"]["USER_AGENT"]
HOST = config["REQUEST"]["HOST"]
ORIGIN = config["REQUEST"]["ORIGIN"]
REFERER = config["REQUEST"]["REFERER"]

PROXIES = {
    "http": config["REQUEST"]["PROXY_HTTP"],
    "https": config["REQUEST"]["PROXY_HTTPS"],
}

PAYLOAD_FILE = config['PATH']['PAYLOAD_FILE']

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
            "Host": HOST,
            "User-Agent": USER_AGENT,  # This is the key for the proxy
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": ORIGIN,
            "Connection": "keep-alive",
            "Referer": REFERER,
        }

        # `verify=False` is used to skip SSL verification for the proxy's self-signed certificate.
        response = requests.post(
            MARGIN_URL,
            headers=headers,
            data=static_payload,
            proxies=PROXIES,
            verify=False
        )

        print(f"\nResponse Status Code: {response.status_code}")
        # print("Response Body:")
        # print(response.text)

        # Check for successful response
        if "unable to process the request" not in response.text:
            print("\nRequest was successful!")
        else:
            print("\nRequest failed. Check the response body for details.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_client()
