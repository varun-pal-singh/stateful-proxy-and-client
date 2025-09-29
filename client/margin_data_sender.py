import requests
import json
import time
import os
import configparser

CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
# CLIENT_DIR C:\Users\admin01\Desktop\get_margin_data\client

print("CLIENT_DIR", CLIENT_DIR)

CONFIG_FILE_PATH = os.path.join(CLIENT_DIR, '..', 'config', 'config.ini')

config = configparser.ConfigParser()
read_files = config.read(CONFIG_FILE_PATH)

if not read_files:
    print(f"ERROR: Could not read configuration file at: {CONFIG_FILE_PATH}")

SERVER_URL = config['CREDENTIALS']['SERVER_URL']

path_with_dots = os.path.join(CLIENT_DIR, '..', 'parser', 'margin-utilization-view.json')
FILE_PATH = os.path.normpath(path_with_dots)

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