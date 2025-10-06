import os
import re
import json
import threading
import tempfile
import configparser
from mitmproxy import http
from datetime import datetime
from urllib.parse import parse_qs
import configparser
import time
import random

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

BROWSER_REQUEST_DIR = os.path.join(CURR_DIR, './calls', 'browser-calls', 'requests')
BROWSER_RESPONSE_DIR = os.path.join(CURR_DIR, './calls', 'browser-calls', 'responses')

MARGIN_REQUEST_FILE = os.path.join(BROWSER_REQUEST_DIR, "curr_request.txt")
MARGIN_RESPONSE_FILE = os.path.join(BROWSER_RESPONSE_DIR, "curr_response.txt")

PREV_MARGIN_REQUEST_FILE = os.path.join(BROWSER_REQUEST_DIR, "prev_request.txt")
PREV_MARGIN_RESPONSE_FILE = os.path.join(BROWSER_RESPONSE_DIR, "prev_response.txt")

os.makedirs(BROWSER_REQUEST_DIR, exist_ok=True)
os.makedirs(BROWSER_RESPONSE_DIR, exist_ok=True)

config = configparser.RawConfigParser()
config.read(CONFIG_FILE_PATH)

DEFAULT_MARGIN_PAYLOAD_TEMPLATE = config["DEFAULTS"]["DEFAULT_MARGIN_PAYLOAD_TEMPLATE"]
AUTO_CAPTURE_FLAG = config["DEFAULTS"]["AUTO_CAPTURE_FLAG"]

_lock = threading.Lock()

EMPTY_CHECK_FIELDS = [
    "MCB_SearchWC_wca_bpid",
    "MCB_SearchWC_wca_associatedtm",
    "MCB_SearchWC_wca_actype",
    "MCB_SearchWC_wca_associatedcm",
    "MCB_SearchWC_wca_category",
]

DFLT_CHECK_FIELDS = [
    "propertyMap(MCB_SearchWC_wca_bpid_Cmb)",
    "propertyMap(MCB_SearchWC_wca_associatedtm_Cmb)",
    "propertyMap(MCB_SearchWC_wca_associatedcm_Cmb)",
    "MCB_SearchWC_wca_CMName",
    "MCB_SearchWC_wca_TMName",
]


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
    
    def _is_unfiltered(self, flow: http.HTTPFlow) -> bool:
        if flow.request.pretty_url != MARGIN_URL:
            return False 
        
        content = flow.request.content
        if not content:
            return False # No content to check

        try:
            form_dict_of_lists = parse_qs(content.decode('utf-8'))
        except Exception as e:
            print(f"[Proxy] Error parsing request body: {e}")
            return False

        # Extract the first value for each key for simplified checking
        params = {k: v[0] for k, v in form_dict_of_lists.items()}

        is_unfiltered = True
        for field in EMPTY_CHECK_FIELDS:
            value = params.get(field, "")
            if value != "":
                print(f"[Proxy] FILTERED: Skipping recording. Field '{field}' has value: '{value}'")
                is_unfiltered = False
                break

        for field in DFLT_CHECK_FIELDS:
            value = params.get(field, "")
            if value != "DFLT":
                # If any field has a value, the request is filtered.
                print(f"[Proxy] FILTERED: Skipping recording. Field '{field}' has value: '{value}'")
                is_unfiltered = False
                break
        
        if "sQuery" in params and params["sQuery"] != "Client Code  Equals  DFLT AND TM / CP  Equals  DFLT AND CM  Equals  DFLT":
            is_unfiltered = False
            
        return is_unfiltered
        
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

    # this function will hit if we get margin request call from our mcx_client.py
    def _rewrite_margin_request(self, flow: http.HTTPFlow):
        if flow.request.pretty_url != MARGIN_URL:
            return

        request_text = flow.request.get_text(strict=False)

        if AUTO_CAPTURE_FLAG in request_text:
            ixhrts_val = self.credentials.get("IXHRts", "")
            rndaak_str = self.credentials.get("rndaak", "")
            
            if not ixhrts_val or not rndaak_str:
                print("[Proxy] ERROR: Missing IXHRts or rndaak for auto-capture rewrite.")
                fresh_ixhrts = int(time.time() * 1000)
            else:
                try:
                    base_ixhrts = int(ixhrts_val)
                    jitter_ms = random.randint(50, 200)
                    fresh_ixhrts = base_ixhrts + jitter_ms
                    
                except ValueError:
                    print("[Proxy] WARNING: IXHRts token was invalid. Generating fresh epoch time.")
                    fresh_ixhrts = int(time.time() * 1000)

            final_payload = DEFAULT_MARGIN_PAYLOAD_TEMPLATE.format(
                IXHRts=fresh_ixhrts, 
                rndaak=rndaak_str
            )

            final_payload = DEFAULT_MARGIN_PAYLOAD_TEMPLATE.format(
                IXHRts=ixhrts_val,
                rndaak=rndaak_str
            )
            
            flow.request.set_text(final_payload)

            print("Final payload", final_payload)

            flow.request.headers["Content-Length"] = str(len(final_payload))

            print(f"[Proxy] AUTO-CAPTURE: Rewrote payload for {MARGIN_URL}")

    # ---- mitmproxy hooks ----
    def request(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return
        
        # Initialize metadata flag, to be consistent between req res cycle
        flow.metadata["is_unfiltered_margin_request"] = False

        if flow.request.pretty_url == MARGIN_URL:
            if self._is_unfiltered(flow):
                flow.metadata["is_unfiltered_margin_request"] = True

        is_unfiltered = flow.metadata.get("is_unfiltered_margin_request", False)

        # is_unfiltered = True

        if is_unfiltered:
            # if its default margin req

            # if this request is generated by our mcx_client.py
            self._rewrite_margin_request(flow)

            # record req in curr_request.txt fil
            self._record_request_flow(flow)

        try:
            # update tokens
            self._update_from_request(flow)
        except Exception as e:
            print(f"[addon] failed to write request: {e}")

    def response(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return
        
        is_unfiltered = flow.metadata.get("is_unfiltered_margin_request", False)

        # is_unfiltered = True

        if is_unfiltered:
            # if its default margin req

            # record res in curr_response.txt 
            self._record_response_flow(flow)

        try:
            # update tokens
            self._update_from_response(flow)
        except Exception as e:
            print(f"[addon] failed to write response: {e}")


addons = [StatefulCredentialsProxy()]