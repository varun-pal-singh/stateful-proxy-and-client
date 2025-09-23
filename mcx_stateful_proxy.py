import os
import re
import json
import threading
import tempfile
import configparser
from mitmproxy import http
from datetime import datetime

# ----------------- CONFIG -----------------
TARGET_HOST = "eclear.mcxccl.com"
# MONITORED_URL = "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do"
MONITORED_URL = "https://eclear.mcxccl.com/Bancs"

config = configparser.ConfigParser()
config.read('config/config.ini')


# TARGET_HOST = str(config["CREDENTIALS"]["TARGET_HOST"])
# MONITORED_URL = str(config["CREDENTIALS"]["MONITORED_URL"])
# CREDENTIALS_FILE_PATH = config["PATH"]["CREDENTIALS_FILE_PATH"]

BASE_DIR = "calls"
BROWSER_DIR = "browser-calls"
CLIENT_DIR = "client-calls"

REQ_DIR = os.path.join(BASE_DIR, BROWSER_DIR, "requests")
RESP_DIR = os.path.join(BASE_DIR, BROWSER_DIR, "responses")
COUNTER_FILE = os.path.join(BASE_DIR, "counter.txt")

CREDENTIALS_FILE = os.path.join("config", "credentials.json")

print(CREDENTIALS_FILE)
# ------------------------------------------

os.makedirs(REQ_DIR, exist_ok=True)
os.makedirs(RESP_DIR, exist_ok=True)

_lock = threading.Lock()


# ----------------- UTILITIES -----------------
def _save_credentials(creds: dict):
    """Write latest tokens to credentials.json atomically"""
    # always refresh last_updated on save
    creds["last_updated"] = datetime.now().isoformat() + "Z"

    fd, tmp = tempfile.mkstemp(dir=BASE_DIR)
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


        try:
            self._update_from_request(flow)
        except Exception as e:
            print(f"[addon] failed to write request: {e}")

    def response(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return

        try:
            self._update_from_response(flow)
        except Exception as e:
            print(f"[addon] failed to write response: {e}")


addons = [StatefulCredentialsProxy()]