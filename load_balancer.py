import socket
import threading

# Configuration
BACKEND_SERVERS = [("localhost", 8001), ("localhost", 8002)]
LISTEN_PORT = 8888

# In-memory cache
cache = {}
cache_lock = threading.Lock()

def handle_request(client_socket, backend_servers, next_server_index):
    try:
        request_data = client_socket.recv(4096)
        if not request_data:
            return

        request_line = request_data.decode(errors='ignore').split('\r\n')[0]
        method, path, *_ = request_line.split()
        filename = path.strip("/")

        with cache_lock:
            if filename in cache:
                print(f"[CACHE]  {'hit':<6} {filename}")
                client_socket.sendall(cache[filename])
                return
            else:
                print(f"[CACHE]  {'miss':<6} {filename}")

        backend_host, backend_port = backend_servers[next_server_index[0] % len(backend_servers)]
        next_server_index[0] += 1
        print(f"[RR]     → {backend_host}:{backend_port}  /{filename}")

        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_socket.connect((backend_host, backend_port))
        backend_socket.sendall(request_data)

        response_data = b""
        while True:
            chunk = backend_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk

        with cache_lock:
            cache[filename] = response_data
            print(f"[CACHE]  {'stored':<6} {filename}")

        client_socket.sendall(response_data)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", LISTEN_PORT))
    server_socket.listen(5)

    print(f"[+] Load Balancer listening on :{LISTEN_PORT}")

    next_server_index = [0]

    while True:
        client_socket, client_address = server_socket.accept()
        thread = threading.Thread(target=handle_request, args=(client_socket, BACKEND_SERVERS, next_server_index))
        thread.start()

if __name__ == "__main__":
    main()
