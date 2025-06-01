import socket
import threading
import os

# Configuration
BACKEND_SERVERS = [("localhost", 8001), ("localhost", 8002)]
LISTEN_PORT = 8888

cache_dir = os.path.join(os.getcwd(), "cache")
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir) 
cache_lock = threading.Lock()

def handle_request(client_socket, backend_servers, next_server_index):
    try:
        request_data = client_socket.recv(4096)
        if not request_data:
            return

        request_line = request_data.decode(errors='ignore').split('\r\n')[0]
        method, path, *_ = request_line.split()
        filename = path.strip("/")

        print(f"[RR] Received request: {method} {path}")
        print(f"[RR] Extracted filename: {filename}")

        # Check for sticky backend cookie
        cookie_header = [header for header in request_data.decode(errors='ignore').split('\r\n') if header.startswith("Cookie:")]
        if cookie_header:
            cookie_value = cookie_header[0].split("sticky_backend=")[-1].split(";")[0]
            backend_host, backend_port = cookie_value.split(":")
            backend_port = int(backend_port)
            print(f"[RR] Sticky backend found: {backend_host}:{backend_port}")
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.settimeout(5)  # Set a timeout for the backend connection

            backend_socket.connect((backend_host, backend_port))
            backend_socket.sendall(request_data)

            response_data = b""
            while True:
                chunk = backend_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk

            client_socket.sendall(response_data)
            return


        with cache_lock:
            try:
                with open(os.path.join(cache_dir, filename), "r") as cache_file:
                    output_data = cache_file.readlines()
                file_exist = "true"
                
                print(f"[CACHE]  {'hit':<6} {filename}")
                client_socket.send(b"HTTP/1.1 200 OK\r\n\r\n")
                for line in output_data:
                    client_socket.sendall(line.encode("utf-8"))
                
            except FileNotFoundError:
                file_exist = "false"
                print(f"[CACHE]  {'miss':<6} {filename}")

        if file_exist == "false":     
                
            backend_host, backend_port = backend_servers[next_server_index[0] % len(backend_servers)]
            next_server_index[0] += 1
            print(f"[RR]     → {backend_host}:{backend_port}  /{filename}")

            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.settimeout(5)  # Set a timeout for the backend connection

            backend_socket.connect((backend_host, backend_port))
            backend_socket.sendall(request_data)

            response_data = b""
            while True:
                chunk = backend_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk

            with cache_lock:
                response_lines = response_data.decode(errors='ignore').splitlines()
                if response_lines[0].startswith("HTTP/1.1 200 OK"):
                    response_body = "\r\n".join(response_lines[1:]).encode("utf-8")
                    with open(os.path.join(cache_dir, filename), "wb") as cache_file:
                        cache_file.write(response_body)
                    print(f"[CACHE]  {'stored':<6} {filename}")

                    client_socket.sendall(b"HTTP/1.1 200 OK\r\n")
                    client_socket.sendall(b"Set-Cookie: sticky_backend=" + backend_host.encode() + b":" + str(backend_port).encode() + b"; Path=/\r\n\r\n")
                    client_socket.sendall(response_body)
                else:
                    client_socket.sendall(response_data)
        
    except ConnectionRefusedError as e:
        print(f"[RR]     → {backend_host}:{backend_port}  /{filename}  [ERROR] {e}")
        client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        client_socket.sendall(b"<html><body><h1>502 Bad Gateway</h1></body></html>")
    except TimeoutError as e:
        print(f"[RR]     → {backend_host}:{backend_port}  /{filename}  [ERROR] {e}")
        client_socket.sendall(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
        client_socket.sendall(b"<html><body><h1>504 Gateway Timeout</h1></body></html>")
    finally:
        client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("localhost", LISTEN_PORT))
    server_socket.listen(5)

    print(f"[+] Load Balancer listening on :{LISTEN_PORT}")

    next_server_index = [0]

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"[+] Accepted connection from {client_address}")
        thread = threading.Thread(target=handle_request, args=(client_socket, BACKEND_SERVERS, next_server_index))
        thread.start()

if __name__ == "__main__":
    main()