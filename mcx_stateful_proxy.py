# addon.py
import os
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
# ------------------------------------------

os.makedirs(REQ_DIR, exist_ok=True)
os.makedirs(RESP_DIR, exist_ok=True)

_lock = threading.Lock()

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
            try: os.remove(tmp)
            except Exception: pass

def _atomic_write(path: str, data: bytes):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass

def _wire_format_request(flow: http.HTTPFlow) -> bytes:
    """
    Reconstruct request in HTTP wire format (request-line + raw headers + CRLF + raw body)
    Uses raw_headers and raw_content to preserve bytes as mitmproxy exposes them.
    """
    req = flow.request
    # request-line: METHOD SP PATH SP HTTP/VERSION CRLF
    method = req.method.encode("ascii", errors="replace")
    path = req.path.encode("utf-8", errors="replace")
    version = ("HTTP/" + req.http_version).encode("ascii", errors="replace")
    line = method + b" " + path + b" " + version + b"\r\n"

    # raw_headers is list of (name_bytes, value_bytes) in newer mitmproxy versions.
    headers_bytes = b""
    try:
        # If raw_headers exists and is bytes-pairs
        raw_h = getattr(req, "raw_headers", None)
        if raw_h:
            # raw_h can be list of tuples (name, value)
            for name, val in raw_h:
                if isinstance(name, str):
                    name = name.encode("utf-8", errors="replace")
                if isinstance(val, str):
                    val = val.encode("utf-8", errors="replace")
                headers_bytes += name + b": " + val + b"\r\n"
        else:
            # Fallback: use req.headers (may normalize casing/order)
            for k, v in req.headers.items(multi=True):
                headers_bytes += k.encode("utf-8", errors="replace") + b": " + v.encode("utf-8", errors="replace") + b"\r\n"
    except Exception:
        # best-effort fallback
        for k, v in req.headers.items(multi=True):
            headers_bytes += k.encode("utf-8", errors="replace") + b": " + v.encode("utf-8", errors="replace") + b"\r\n"

    # blank line then body
    body = req.raw_content or b""
    return line + headers_bytes + b"\r\n" + body

def _wire_format_response(flow: http.HTTPFlow) -> bytes:
    """
    Reconstruct response in HTTP wire format (status-line + raw headers + CRLF + raw body)
    Uses raw_headers and raw_content to preserve bytes as mitmproxy exposes them.
    """
    resp = getattr(flow, "response", None)
    if not resp:
        return b"<no response>\r\n"

    # status-line: HTTP/VERSION SP STATUS SP REASON CRLF
    version = ("HTTP/" + resp.http_version).encode("ascii", errors="replace")
    status = str(resp.status_code).encode("ascii", errors="replace")
    reason = (resp.reason or "").encode("utf-8", errors="replace")
    line = version + b" " + status + b" " + reason + b"\r\n"

    headers_bytes = b""
    try:
        raw_h = getattr(resp, "raw_headers", None)
        if raw_h:
            for name, val in raw_h:
                if isinstance(name, str):
                    name = name.encode("utf-8", errors="replace")
                if isinstance(val, str):
                    val = val.encode("utf-8", errors="replace")
                headers_bytes += name + b": " + val + b"\r\n"
        else:
            for k, v in resp.headers.items(multi=True):
                headers_bytes += k.encode("utf-8", errors="replace") + b": " + v.encode("utf-8", errors="replace") + b"\r\n"
    except Exception:
        for k, v in resp.headers.items(multi=True):
            headers_bytes += k.encode("utf-8", errors="replace") + b": " + v.encode("utf-8", errors="replace") + b"\r\n"

    body = getattr(resp, "raw_content", None) or b""
    return line + headers_bytes + b"\r\n" + body

class StatefulCredentialsProxy:
    def __init__(self):
        # map flow.id -> index
        self.flow_to_index = {}
        self.counter = _read_counter()
        self.lock = _lock

    def _is_target(self, flow: http.HTTPFlow) -> bool:
        try:
            if flow.request.host != TARGET_HOST:
                return False
            # allow query strings; use startswith so exact-match issues with query params are avoided
            return flow.request.pretty_url.startswith(MONITORED_URL)
        except Exception:
            return False

    def request(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return

        with self.lock:
            # increment counter so indices start at 1
            self.counter += 1
            index = self.counter
            _write_counter(self.counter)
            self.flow_to_index[flow.id] = index

        req_path = os.path.join(REQ_DIR, f"request{index}.txt")
        try:
            data = _wire_format_request(flow)
            _atomic_write(req_path, data)
            print(f"[addon] wrote request -> {req_path} (flow id: {flow.id})")
        except Exception as e:
            print(f"[addon] failed to write request {req_path}: {e}")

    def response(self, flow: http.HTTPFlow):
        if not self._is_target(flow):
            return

        with self.lock:
            index = self.flow_to_index.pop(flow.id, None)

        if index is None:
            # request not seen by this addon (maybe reload). Assign next index to keep sequence.
            with self.lock:
                self.counter += 1
                index = self.counter
                _write_counter(self.counter)
            print(f"[addon] warning: response without mapping; assigned index {index} (flow id: {flow.id})")

        resp_path = os.path.join(RESP_DIR, f"response{index}.txt")
        try:
            data = _wire_format_response(flow)
            _atomic_write(resp_path, data)
            print(f"[addon] wrote response -> {resp_path} (flow id: {flow.id})")
        except Exception as e:
            print(f"[addon] failed to write response {resp_path}: {e}")

    def error(self, flow: http.HTTPFlow):
        print(f"[addon] flow error id={getattr(flow, 'id', None)} err={getattr(flow, 'error', None)}")

addons = [ StatefulCredentialsProxy() ]
