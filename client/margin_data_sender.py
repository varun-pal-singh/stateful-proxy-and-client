import requests
import json
import time
import configparser

config = configparser.ConfigParser()
config.read('../config/config.ini')

SERVER_URL = config['CREDENTIALS']['SERVER_URL']
FILE_PATH = config['PATH']['MARGIN_UTILIZATION_VIEW_FILE_PATH']

# print("SERVER_URL", SERVER_URL)
# print("FILE_PATH", FILE_PATH)

def send_data():
    """Reads data from the JSON file and sends it to the server."""
    try:
        with open(FILE_PATH, 'r') as f:
            data = json.load(f)

        response = requests.post(SERVER_URL, json=data)
        
        if response.status_code == 200:
            print(f"Data sent successfully to {SERVER_URL}. Server response: {response.text}")
        else:
            print(f"Failed to send data. Status code: {response.status_code}, Response: {response.text}")
            
    except FileNotFoundError:
        print(f"Error: The file '{FILE_PATH}' was not found.\n")
    except json.JSONDecodeError:
        print(f"Error: The file '{FILE_PATH}' is not a valid JSON file.\n")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to the server: {e}\n")

if __name__ == '__main__':
    print("Starting data transmission...")
    try:
        while True:
            send_data()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nTransmission stopped by user.")