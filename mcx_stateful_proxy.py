# mcx_stateful_proxy.py
import os
import re
import json
import threading
import tempfile
from mitmproxy import http

# ----------------- CONFIG -----------------
TARGET_HOST = "eclear.mcxccl.com"
MONITORED_URL = "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do"

BASE_DIR = "margin_calls"
REQ_DIR = os.path.join(BASE_DIR, "requests")
RESP_DIR = os.path.join(BASE_DIR, "responses")
COUNTER_FILE = os.path.join(BASE_DIR, "counter.txt")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
# ------------------------------------------

os.makedirs(REQ_DIR, exist_ok=True)
os.makedirs(RESP_DIR, exist_ok=True)

_lock = threading.Lock()


# ----------------- UTILITIES -----------------
def _read_counter():
    try:
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except FileNotFoundError:
        return 0
    except Exception:
        return 0


def _write_counter(value: int):
    fd, tmp = tempfile.mkstemp(dir=BASE_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(value))
        os.replace(tmp, COUNTER_FILE)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _atomic_write(path: str, data: bytes):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _wire_format_request(flow: http.HTTPFlow) -> bytes:
    req = flow.request
    line = f"{req.method} {req.path} HTTP/{req.http_version}\r\n".encode()

    headers_bytes = b""
    for k, v in req.headers.items(multi=True):
        headers_bytes += f"{k}: {v}\r\n".encode()

    body = req.raw_content or b""
    return line + headers_bytes + b"\r\n" + body


def _wire_format_response(flow: http.HTTPFlow) -> bytes:
    resp = flow.response
    if not resp:
        return b"<no response>\r\n"

    line = f"HTTP/{resp.http_version} {resp.status_code} {resp.reason}\r\n".encode()

    headers_bytes = b""
    for k, v in resp.headers.items(multi=True):
        headers_bytes += f"{k}: {v}\r\n".encode()

    body = resp.raw_content or b""
    return line + headers_bytes + b"\r\n" + body


# def _save_credentials(creds: dict):
#     """Write latest tokens to credentials.json atomically"""
#     fd, tmp = tempfile.mkstemp(dir=BASE_DIR)
#     try:
#         with os.fdopen(fd, "w", encoding="utf-8") as f:
#             json.dump(creds, f, indent=2)
#         os.replace(tmp, CREDENTIALS_FILE)
#     finally:
#         if os.path.exists(tmp):
#             try:
#                 os.remove(tmp)
#             except Exception:
#                 pass
from datetime import datetime

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
        self.flow_to_index = {}
        self.counter = _read_counter()
        self.lock = _lock
        # dict to store latest values
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
        # cookies
        cookie_header = flow.request.headers.get("Cookie", "")
        for name in ["AlteonP", "JSESSIONID", "TS01d67e35", "TS254a1510027"]:
            m = re.search(rf"{name}=([^;]+)", cookie_header)
            if m:
                self.credentials[name] = m.group(1)

        # IXHRts in body
        if flow.request.urlencoded_form:
            if "IXHRts" in flow.request.urlencoded_form:
                self.credentials["IXHRts"] = flow.request.urlencoded_form["IXHRts"]
        else:
            m = re.search(r"IXHRts=(\d+)", flow.request.get_text(strict=False))
            if m:
                self.credentials["IXHRts"] = m.group(1)

        _save_credentials(self.credentials)

    def _update_from_response(self, flow: http.HTTPFlow):
        if not flow.response:
            return
        # Set-Cookie headers
        set_cookies = flow.response.headers.get_all("Set-Cookie")
        for sc in set_cookies:
            for name in ["TS01d67e35", "TS254a1510027"]:
                m = re.search(rf"{name}=([^;]+)", sc)
                if m:
                    self.credentials[name] = m.group(1)

        # IXHRts in body
        body = flow.response.get_text(strict=False)
        m = re.search(r"IXHRts[#*#=](\d+)", body)
        if m:
            self.credentials["IXHRts"] = m.group(1)

        _save_credentials(self.credentials)

    # ---- mitmproxy hooks ----
    def request(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return

        with self.lock:
            self.counter += 1
            index = self.counter
            _write_counter(self.counter)
            self.flow_to_index[flow.id] = index

        req_path = os.path.join(REQ_DIR, f"request{index}.txt")
        try:
            data = _wire_format_request(flow)
            _atomic_write(req_path, data)
            self._update_from_request(flow)
        except Exception as e:
            print(f"[addon] failed to write request {req_path}: {e}")

    def response(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return

        with self.lock:
            index = self.flow_to_index.pop(flow.id, None)

        if index is None:
            with self.lock:
                self.counter += 1
                index = self.counter
                _write_counter(self.counter)

        resp_path = os.path.join(RESP_DIR, f"response{index}.txt")
        try:
            data = _wire_format_response(flow)
            _atomic_write(resp_path, data)
            self._update_from_response(flow)
        except Exception as e:
            print(f"[addon] failed to write response {resp_path}: {e}")

    def error(self, flow: http.HTTPFlow):
        print(f"[addon] flow error id={getattr(flow, 'id', None)} err={getattr(flow, 'error', None)}")


addons = [StatefulCredentialsProxy()]
