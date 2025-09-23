# client_update_creds.py
import re
import json
import time
from pathlib import Path
import requests
import urllib3
from http import cookies as http_cookies
from datetime import datetime, timezone

# disable urllib3 InsecureRequestWarning (safe for local mitmproxy testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Config
TEMPLATE_FILE = "./margin_calls/requests/request75.txt"
CREDENTIALS_FILE = "margin_calls/credentials.json"
PROXY = "http://127.0.0.1:8080"
TARGET_URL = "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do"
OUT_REQUEST = "client_request_sent.txt"
OUT_RESPONSE = "client_response.txt"

# tokens to maintain
TOKEN_NAMES = ["AlteonP", "JSESSIONID", "TS01d67e35", "TS254a1510027"]

def read_template(path: str):
    raw = Path(path).read_bytes().decode(errors="ignore")
    if "\r\n\r\n" in raw:
        head, body = raw.split("\r\n\r\n", 1)
    elif "\n\n" in raw:
        head, body = raw.split("\n\n", 1)
    else:
        head, body = raw, ""
    header_lines = head.splitlines()
    return header_lines, body

def parse_headers(header_lines):
    start_line = header_lines[0] if header_lines else ""
    headers_list = []
    headers_dict = {}
    for line in header_lines[1:]:
        if not line.strip():
            continue
        parts = line.split(":", 1)
        if len(parts) == 2:
            name = parts[0].strip(); value = parts[1].lstrip()
            headers_list.append((name, value))
            headers_dict[name] = value
        else:
            headers_list.append((line, ""))
    return start_line, headers_list, headers_dict

def read_credentials(path: str):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_credentials(path: str, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def build_cookie_header(orig_cookie: str, creds: dict):
    orig_cookie = orig_cookie or ""
    parts = [p.strip() for p in orig_cookie.split(";") if p.strip() != ""]
    cookies = []
    existing = {}
    for i, p in enumerate(parts):
        if "=" in p:
            k, v = p.split("=", 1); k=k.strip(); v=v.strip()
            cookies.append([k, v]); existing[k] = i
        else:
            cookies.append([p, ""]); existing[p] = i
    for t in TOKEN_NAMES:
        if t in existing and creds.get(t) is not None:
            cookies[existing[t]][1] = creds[t]
    for t in TOKEN_NAMES:
        if t not in existing and creds.get(t) is not None:
            cookies.append([t, creds[t]])
    return "; ".join(f"{k}={v}" if v != "" else k for k, v in cookies)

def replace_ixhrts(body: str, new_ts: str):
    b = re.sub(r"IXHRts=\d+", f"IXHRts={new_ts}", body)
    b = re.sub(r"IXHRts[#*#=]+\d+", f"IXHRts#*#{new_ts}", b)
    return b

def format_request_for_file(start_line, headers_list, body):
    head = start_line + "\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers_list)
    return head + "\r\n\r\n" + body

def format_response_for_file(resp):
    status_line = f"HTTP/1.1 {resp.status_code} {resp.reason}"
    headers = "\r\n".join(f"{k}: {v}" for k, v in resp.headers.items())
    body = resp.text
    return status_line + "\r\n" + headers + "\r\n\r\n" + body

def extract_set_cookie_headers(resp):
    """Return a list of raw Set-Cookie header strings (attempt multiple strategies)."""
    cookies = []
    # Try to get from resp.raw if available
    try:
        raw_headers = getattr(resp, "raw", None)
        if raw_headers is not None:
            raw_hdrs = getattr(raw_headers, "headers", None)
            if raw_hdrs is not None:
                # some implementations provide get_all
                try:
                    cookies = raw_hdrs.get_all("Set-Cookie") or []
                except Exception:
                    # fallback: iterate items and collect Set-Cookie keys
                    cookies = [v for k, v in raw_hdrs.items() if k.lower() == "set-cookie"]
    except Exception:
        pass
    # Fallback to resp.headers (may contain only one combined header)
    if not cookies:
        # requests.Response.headers may hold only last Set-Cookie; to be safe, try split by newline/comma heuristics
        sc = resp.headers.get("Set-Cookie") or resp.headers.get("set-cookie")
        if sc:
            # if multiple cookies were combined with commas (rare but possible), split on newline then comma that looks like cookie=...
            # split on newline first
            parts = re.split(r"\r?\n", sc)
            # further split parts that contain multiple cookie= occurrences
            out = []
            for p in parts:
                if p.count("=") >= 2 and "," in p:
                    # try splitting on comma followed by space and token-looking substring
                    subparts = re.split(r", (?=[A-Za-z0-9_\-]+=)", p)
                    out.extend(subparts)
                else:
                    out.append(p)
            cookies = [o.strip() for o in out if o.strip()]
    return cookies

def parse_cookie_values(set_cookie_headers):
    """
    Given list of Set-Cookie header strings, return dict of cookie_name -> cookie_value
    (only top-level name=value, ignoring attributes Path, Secure, HttpOnly)
    """
    result = {}
    for sc in set_cookie_headers:
        try:
            c = http_cookies.SimpleCookie()
            c.load(sc)
            for k in c.keys():
                result[k] = c[k].value
        except Exception:
            # fallback parse: take up to first ';'
            main = sc.split(";", 1)[0].strip()
            if "=" in main:
                k, v = main.split("=", 1)
                result[k.strip()] = v.strip()
    return result

def extract_ixhrts_from_body(body_text):
    # match IXHRts#*#12345 or IXHRts=12345
    m = re.search(r"IXHRts[#*#=]+(\d{8,})", body_text)
    if m:
        return m.group(1)
    return None

def merge_and_update_credentials(existing: dict, new_tokens: dict, ixhrts: str):
    # existing: dict (may contain tokens and last_updated)
    cred = dict(existing)  # shallow copy
    # Only update token keys present in new_tokens
    for k, v in new_tokens.items():
        if k in TOKEN_NAMES:
            cred[k] = v
    # Update IXHRts key if found
    if ixhrts:
        cred["IXHRts"] = ixhrts
    # Update last_updated as ISO UTC
    cred["last_updated"] = datetime.now(timezone.utc).astimezone().isoformat()
    return cred

def main():
    header_lines, body = read_template(TEMPLATE_FILE)
    start_line, headers_list, headers_dict = parse_headers(header_lines)

    creds = read_credentials(CREDENTIALS_FILE)

    # update cookie header
    orig_cookie = headers_dict.get("Cookie", "")
    new_cookie = build_cookie_header(orig_cookie, creds)
    if new_cookie:
        found = False
        for i, (k, v) in enumerate(headers_list):
            if k.lower() == "cookie":
                headers_list[i] = (k, new_cookie); found = True; break
        if not found:
            headers_list.append(("Cookie", new_cookie))

    # replace IXHRts with fresh epoch ms
    new_ts = str(int(time.time() * 1000))
    new_body = replace_ixhrts(body, new_ts)

    # update Content-Length
    new_cl = str(len(new_body.encode("utf-8")))
    updated = False
    for i, (k, v) in enumerate(headers_list):
        if k.lower() == "content-length":
            headers_list[i] = (k, new_cl); updated = True; break
    if not updated:
        headers_list.append(("Content-Length", new_cl))

    # Build headers for requests
    headers_for_requests = {k: v for k, v in headers_list}
    if "Host" in headers_dict and "Host" not in headers_for_requests:
        headers_for_requests["Host"] = headers_dict["Host"]
    if "User-Agent" not in headers_for_requests:
        headers_for_requests["User-Agent"] = headers_dict.get("User-Agent", "MCX-Client-Margin-1.0")

    # Save exact request we will send
    Path(OUT_REQUEST).write_text(format_request_for_file(start_line, headers_list, new_body), encoding="utf-8")
    print(f"Wrote request sent to {OUT_REQUEST}")

    proxies = {"http": PROXY, "https": PROXY}
    try:
        resp = requests.post(TARGET_URL,
                             headers=headers_for_requests,
                             data=new_body.encode("utf-8"),
                             proxies=proxies,
                             verify=False,
                             timeout=30)
    except Exception as e:
        Path(OUT_RESPONSE).write_text(f"Request failed: {e}", encoding="utf-8")
        print("Request failed:", e)
        return

    # Save response
    out_resp_text = format_response_for_file(resp)
    Path(OUT_RESPONSE).write_text(out_resp_text, encoding="utf-8")
    print(f"Saved response to {OUT_RESPONSE} (status {resp.status_code})")

    # Extract Set-Cookie headers and IXHRts from response
    set_cookie_headers = extract_set_cookie_headers(resp)  # list[str]
    parsed_cookies = parse_cookie_values(set_cookie_headers)  # dict name->value
    ixhrts_found = extract_ixhrts_from_body(resp.text)

    # Only keep tokens we care about (so we don't overwrite unrelated cookies)
    tokens_to_update = {k: v for k, v in parsed_cookies.items() if k in TOKEN_NAMES}

    if tokens_to_update or ixhrts_found:
        merged = merge_and_update_credentials(creds, tokens_to_update, ixhrts_found)
        write_credentials(CREDENTIALS_FILE, merged)
        print("Updated credentials.json with:", {**tokens_to_update, **({"IXHRts": ixhrts_found} if ixhrts_found else {})})
    else:
        print("No token updates found in response.")

if __name__ == "__main__":
    main()
