import socket
import threading
from datetime import datetime

# Configuration
HOST = "localhost"
PORT = 8001  # Changed port
SERVER_NAME = "Backend Server 1" #Added server name

def log(port, address, code, message, path=""):
    """Logs messages in the specified format."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if path:
        print(f"[{timestamp}] [{port}] {address[0]} - - \"GET {path} HTTP/1.1\" {code} - -")
    else:
        print(f"[{timestamp}] [{port}] {address[0]} - - code {code}, message {message} - -")


def handle_client(client_socket, client_address, port):
    try:
        request = client_socket.recv(1024).decode()
        print(f"[{port}] Received request:\n{request}")

        # Simple response for GET requests
        if request.startswith("GET /index.html"):
            response = "HTTP/1.1 200 OK\nContent-Type: text/html\n\n<html><body><h1>Hello from Backend Server 1!</h1><p>This is index.html</p></body></html>"
            log(port, client_address, 200, "-", "/index.html")
        elif request.startswith("GET /helloworld.html"):
            response = "HTTP/1.1 200 OK\nContent-Type: text/html\n\n<html><body><h1>Hello from Backend Server 1!</h1><p>This is helloworld.html</p></body></html>"
            log(port, client_address, 200, "-", "/helloworld.html")
        elif request.startswith("GET /favicon.ico"):
            response = "HTTP/1.1 404 Not Found\nContent-Type: text/html\n\n<html><body><h1>404 Not Found from Backend Server 1</h1></body></html>"
            log(port, client_address, 404, "File not found", "/favicon.ico")
        else:
            response = "HTTP/1.1 404 Not Found\nContent-Type: text/html\n\n<html><body><h1>404 Not Found from Backend Server 1</h1></body></html>"
            log(port, client_address, 404, "File not found")

        client_socket.sendall(response.encode())
        print(f"[{port}] Sent response:\n{response}")
    except Exception as e:
        print(f"[{port}] Error: {e}")
    finally:
        client_socket.close()

def start_server(port, server_name): # Added port and server_name parameters
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, port))
    server_socket.listen()

    print(f"[{port}] Listening on {HOST}:{port}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"[{port}] Accepted connection from {client_address}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address, port)) # Pass port
        client_thread.start()

if __name__ == "__main__":
    start_server(PORT, SERVER_NAME) # Pass PORT and SERVER_NAME
