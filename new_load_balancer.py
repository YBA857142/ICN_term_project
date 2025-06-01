#!/usr/bin/env python3
import socket, threading, os, itertools, time
from http.cookies import SimpleCookie
 
# ── 0. Configuration ──────────────────────────────────────────────────────────
BACKEND_SERVERS = [("localhost", 8001), ("localhost", 8002)]
LISTEN_PORT     = 8888
CACHE_DIR       = os.path.join(os.getcwd(), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
 
ROUND_ROBIN     = itertools.cycle(BACKEND_SERVERS)   # thread-safe iterator
rr_lock         = threading.Lock()                   # only for cookie fallback
CACHE_LOCK      = threading.Lock()
 
TIMEOUT         = 5          # seconds for backend connect / recv
 
# ── 1. Helpers ────────────────────────────────────────────────────────────────
def choose_backend_from_cookie(cookie_header: str):
    c = SimpleCookie()
    c.load(cookie_header)
    if "sticky_backend" not in c:                       # no cookie
        return None
    host, _, port = c["sticky_backend"].value.partition(":")
    try:
        port = int(port)
    except ValueError:
        return None
    candidate = (host, port)
    # quick reachability test
    try:
        with socket.create_connection(candidate, timeout=1):
            return candidate
    except OSError:
        return None
 
def round_robin_backend():
    # itertools.cycle is thread-safe for next(); extra lock not strictly needed
    return next(ROUND_ROBIN)
 
def build_http_error(code, phrase):
    body  = f"<html><body><h1>{code} {phrase}</h1></body></html>".encode()
    hdr   = (f"HTTP/1.1 {code} {phrase}\r\n"
             f"Content-Length: {len(body)}\r\n"
             f"Content-Type: text/html; charset=UTF-8\r\n"
             "Connection: close\r\n\r\n").encode()
    return hdr + body
 
# ── 2. Worker ────────────────────────────────────────────────────────────────
def handle(client, client_address):
    try:
        request = client.recv(65536)                    # one RTT assumption
        if not request:
            return
        print("=================================")
        header_block = request.split(b"\r\n\r\n", 1)[0]
        headers      = header_block.decode(errors="ignore").split("\r\n")
        req_line     = headers[0]
        method, path, _ = req_line.split()
        print(f"[INFO] {method} {path} from {client_address[0]}:{client_address[1]}")
        
        # normalise path for cache key
        clean_path = path.split("?", 1)[0].lstrip("/") or "index.html"
        cache_file = os.path.join(CACHE_DIR, clean_path + ".cache")
 
        # ── 2.1 Cache lookup ────────────────────────────────────────────────
        with CACHE_LOCK:
            if os.path.isfile(cache_file):
                print(f"[CACHE] hit  {clean_path}")
                with open(cache_file, "rb") as f:
                    client.sendall(f.read())
                return
            else:
                print(f"[CACHE] miss {clean_path}")
 
        # ── 2.2 Sticky-session cookie check ─────────────────────────────────
        cookie_line = next((h for h in headers if h.lower().startswith("cookie:")), "")
        cookie_value = cookie_line.partition(":")[2].strip()
        print(f"[DEBUG] Cookie value: {cookie_value}")
        backend = choose_backend_from_cookie(cookie_value)
 
        used_rr   = False
        if backend is None:
            backend  = round_robin_backend()
            used_rr  = True
 
        host, port = backend
        if not used_rr:
            print(f"[STICKY] Using backend from cookie: {host}:{port}")
        else:
            print(f"[RR]  → {host}:{port} /{clean_path}")
 
        # ── 2.3 Forward to backend ─────────────────────────────────────────
        with socket.create_connection(backend, timeout=TIMEOUT) as bsock:
            print(f"REQUEST: {request}")
            bsock.sendall(request)
            response = b""
            while True:
                chunk = bsock.recv(65536)
                if not chunk: break
                response += chunk
 
        # ── 2.4 Cache store if 200 OK ──────────────────────────────────────
        if response.startswith(b"HTTP/1.1 200"):
            with CACHE_LOCK:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, "wb") as f:
                    f.write(response)
                print(f"[CACHE] stored {clean_path}")
 
        # ── 2.5 Inject Set-Cookie header if backend chosen by RR ───────────
        if used_rr:
            head, body = response.split(b"\r\n\r\n", 1)
            response   = b"\r\n".join([
                          head,
                          f"Set-Cookie: sticky_backend={host}:{port}; Path=/".encode(),
                          b"", body])
 
        client.sendall(response)
 
    except ConnectionRefusedError:
        client.sendall(build_http_error(502, "Bad Gateway"))
    except socket.timeout:
        client.sendall(build_http_error(504, "Gateway Timeout"))
    except Exception as e:
        print("[ERROR]", e)
        client.sendall(build_http_error(500, "Internal Server Error"))
    finally:
        client.close()
 
# ── 3. Main ─────────────────────────────────────────────────────────────────
def main():
    # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", LISTEN_PORT))
    s.listen()
    print(f"[+] Load balancer listening on :{LISTEN_PORT}")

    while True:
        c, addr = s.accept()
        handle(c, addr)
        threading.Thread(target=handle, args=(c, addr), daemon=True).start()
 
if __name__ == "__main__":
    main()
