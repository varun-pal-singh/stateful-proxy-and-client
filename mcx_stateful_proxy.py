import os
import re
import json
import threading
import tempfile
import configparser
from mitmproxy import http
from datetime import datetime
import configparser

CURR_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(CURR_DIR, '.', 'config')
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, 'config.ini')

config = configparser.ConfigParser()
read_files = config.read(CONFIG_FILE_PATH)

if not read_files:
    print(f"ERROR: Could not read configuration file at: {CONFIG_FILE_PATH}")

# ----------------- CONFIG -----------------
TARGET_HOST = config['CREDENTIALS']['TARGET_HOST']
MONITORED_URL = config['CREDENTIALS']['MONITORED_URL']
MARGIN_URL  = config['CREDENTIALS']['MARGIN_URL']

CREDENTIALS_FILE  = os.path.join(CONFIG_DIR, 'credentials.json')

# BROWSER_REQ_DIR = os.path.normpath(config["PATH"]["BROWSER_REQ_DIR"])
# BROWSER_RES_DIR = os.path.normpath(config["PATH"]["BROWSER_RES_DIR"])

# path_with_dots = os.path.join(PARSER_DIR, '..', 'calls', 'browser-calls', 'responses', 'curr_response.txt')

# RESPONSE_FILE_PATH = os.path.normpath(path_with_dots)

BROWSER_REQUEST_DIR = os.path.join(CURR_DIR, './calls', 'browser-calls', 'requests')
BROWSER_RESPONSE_DIR = os.path.join(CURR_DIR, './calls', 'browser-calls', 'responses')

MARGIN_REQUEST_FILE = os.path.join(BROWSER_REQUEST_DIR, "curr_request.txt")
MARGIN_RESPONSE_FILE = os.path.join(BROWSER_RESPONSE_DIR, "curr_response.txt")

PREV_MARGIN_REQUEST_FILE = os.path.join(BROWSER_REQUEST_DIR, "prev_request.txt")
PREV_MARGIN_RESPONSE_FILE = os.path.join(BROWSER_RESPONSE_DIR, "prev_response.txt")

os.makedirs(BROWSER_REQUEST_DIR, exist_ok=True)
os.makedirs(BROWSER_RESPONSE_DIR, exist_ok=True)

_lock = threading.Lock()


# ----------------- UTILITIES -----------------
def _save_credentials(creds: dict):
    """Write latest tokens to credentials.json atomically"""
    # always refresh last_updated on save
    creds["last_updated"] = datetime.now().isoformat() + "Z"

    fd, tmp = tempfile.mkstemp(dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        os.replace(tmp, CREDENTIALS_FILE)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass



# ----------------- MAIN ADDON -----------------
class StatefulCredentialsProxy:
    def __init__(self):
        self.lock = _lock
        self.credentials = {}

    def _is_target(self, flow: http.HTTPFlow) -> bool:
        try:
            if flow.request.host != TARGET_HOST:
                return False
            return flow.request.pretty_url.startswith(MONITORED_URL)
        except Exception:
            return False
        
    def _record_request_flow(self, flow: http.HTTPFlow):
        if flow.request.pretty_url != MARGIN_URL:
            return

        with self.lock:
            try:
                # Check if current files exist.
                # If so, rename them to 'prev' files.
                if os.path.exists(MARGIN_REQUEST_FILE):
                    os.replace(MARGIN_REQUEST_FILE, PREV_MARGIN_REQUEST_FILE)

                if flow.request:
                    with open(MARGIN_REQUEST_FILE, "wb") as f:
                        f.write(flow.request.get_content())
                        print(f"Recorded current request to {MARGIN_REQUEST_FILE}")
            
            except Exception as e:
                print(f"Error recording files for MARGIN_URL: {e}")

    def _record_response_flow(self, flow: http.HTTPFlow):
        if flow.request.pretty_url != MARGIN_URL:
            return

        with self.lock:
            try:
                # Check if current files exist.
                # If so, rename them to 'prev' files.
                if os.path.exists(MARGIN_RESPONSE_FILE):
                    os.replace(MARGIN_RESPONSE_FILE, PREV_MARGIN_RESPONSE_FILE)

                if flow.response:
                    with open(MARGIN_RESPONSE_FILE, "wb") as f:
                        f.write(flow.response.get_content())
                        print(f"Recorded current response to {MARGIN_RESPONSE_FILE}")
            
            except Exception as e:
                print(f"Error recording files for MARGIN_URL: {e}")

    # ---- helpers for extracting tokens ----
    def _update_from_request(self, flow: http.HTTPFlow):
        updated = False
        cookie_header = flow.request.headers.get("Cookie", "")
        for name in ["AlteonP", "JSESSIONID", "TS01d67e35", "TS254a1510027"]:
            m = re.search(rf"{name}=([^;]+)", cookie_header)
            if m:
                self.credentials[name] = m.group(1)

        if flow.request.urlencoded_form:
            if "IXHRts" in flow.request.urlencoded_form and self.credentials.get("IXHRts") != flow.request.urlencoded_form["IXHRts"]:
                self.credentials["IXHRts"] = flow.request.urlencoded_form["IXHRts"]
                updated = True
            if "rndaak" in flow.request.urlencoded_form and self.credentials.get("rndaak") != flow.request.urlencoded_form["rndaak"]:
                self.credentials["rndaak"] = flow.request.urlencoded_form["rndaak"]
                updated = True
        else:
            m_ixhrts = re.search(r"IXHRts=(\d+)", flow.request.get_text(strict=False))
            if m_ixhrts and self.credentials.get("IXHRts") != m_ixhrts.group(1):
                self.credentials["IXHRts"] = m_ixhrts.group(1)
                updated = True
            
            m_rndaak = re.search(r"rndaak=([^&]+)", flow.request.get_text(strict=False))
            if m_rndaak and self.credentials.get("rndaak") != m_rndaak.group(1):
                self.credentials["rndaak"] = m_rndaak.group(1)
                updated = True

        if updated:
            _save_credentials(self.credentials)

    def _update_from_response(self, flow: http.HTTPFlow):
        if not flow.response:
            return
        # Set-Cookie headers
        updated = False
        set_cookies = flow.response.headers.get_all("Set-Cookie")
        for sc in set_cookies:
            for name in ["AlteonP", "JSESSIONID", "TS01d67e35", "TS254a1510027"]:
                m = re.search(rf"{name}=([^;]+)", sc)
                if m:
                    self.credentials[name] = m.group(1)

        # IXHRts in body
        body = flow.response.get_text(strict=False)
        m_ixhrts = re.search(r"IXHRts[#*#=](\d+)", body)
        if m_ixhrts and self.credentials.get("IXHRts") != m_ixhrts.group(1):
            self.credentials["IXHRts"] = m_ixhrts.group(1)
            updated = True

        # rndaak in body (newly added)
        m_rndaak = re.search(r"rndaak[#*#=]([^<]+)", body)
        if m_rndaak and self.credentials.get("rndaak") != m_rndaak.group(1):
            self.credentials["rndaak"] = m_rndaak.group(1).strip()
            updated = True
        
        if updated:
            print("[Proxy] Credentials updated from response.")
            _save_credentials(self.credentials)

    # ---- mitmproxy hooks ----
    def request(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return
        # recording only margin url req res

        # self._record_margin_flow(flow) 
        self._record_request_flow(flow)

        try:
            self._update_from_request(flow)
        except Exception as e:
            print(f"[addon] failed to write request: {e}")

    def response(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return
        # recording only margin url req res
        
        # self._record_margin_flow(flow) 
        self._record_response_flow(flow)

        try:
            self._update_from_response(flow)
        except Exception as e:
            print(f"[addon] failed to write response: {e}")


addons = [StatefulCredentialsProxy()]