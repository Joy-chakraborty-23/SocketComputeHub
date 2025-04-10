# server_ui.py
import socket
import threading
import json
from uuid import uuid4

class ServerUI:
    def __init__(self, host, port, core):
        self.host = host
        self.port = port
        self.core = core
        self.clients = {}  # token -> client_info

        # A simple in‑memory user store; replace with your JSON DB logic
        self.users = {
            "admin": {"password": "admin123", "is_admin": True}
        }

    def start_client_listener(self):
        """Master: listen for notebook‑client connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to all IPv4 interfaces
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        print(f"Master: client interface listening on {self.host}:{self.port}")

        while self.core.running:
            try:
                client_sock, addr = self.server_socket.accept()
            except OSError:
                break  # socket closed
            t = threading.Thread(target=self.authenticate_client, args=(client_sock, addr))
            t.start()

    def authenticate_client(self, client_socket, address):
        """Perform simple username/password auth, then hand off to request handler."""
        try:
            data = client_socket.recv(1024).decode()
            creds = json.loads(data)
            username = creds.get("username")
            password = creds.get("password")
            if username in self.users and self.users[username]["password"] == password:
                token = str(uuid4())
                # Register client
                client_info = {
                    "socket": client_socket,
                    "address": address,
                    "username": username,
                    "token": token
                }
                self.clients[token] = client_info
                # Send success
                client_socket.send(json.dumps({
                    "status": "authenticated",
                    "session_token": token
                }).encode())
                # Start handling their requests
                self.handle_client_requests(client_socket, client_info)
            else:
                client_socket.send(json.dumps({
                    "status": "error",
                    "message": "Invalid credentials"
                }).encode())
                client_socket.close()
        except Exception:
            client_socket.close()

    def handle_client_requests(self, client_socket, user_info):
        """Main loop for a connected, authenticated client."""
        token = user_info["token"]
        while self.core.running:
            try:
                data = client_socket.recv(65536).decode()
                if not data:
                    break
                msg = json.loads(data)
            except (ConnectionResetError, json.JSONDecodeError):
                break

            # Validate token
            if msg.get("token") != token:
                client_socket.send(json.dumps({
                    "action": "error",
                    "message": "Invalid session token"
                }).encode())
                break

            action = msg.get("action")
            if action == "upload":
                fname = msg.get("filename")
                content = msg.get("content", "")
                # Save to upload_dir via core
                saved = self.core.save_uploaded_file(fname, content)
                ack = {"action": "upload_ack"} if saved else {"action": "error", "message": "Upload failed"}
                client_socket.send(json.dumps(ack).encode())

            elif action == "execute":
                code = msg.get("code", "")
                files = msg.get("files", [])
                # Enqueue job in core
                job_id = self.core.enqueue_job(client_socket, code, files)
                # Immediately return job_id if you want
                client_socket.send(json.dumps({
                    "action": "job_queued",
                    "job_id": job_id
                }).encode())

            else:
                client_socket.send(json.dumps({
                    "action": "error",
                    "message": f"Unknown action '{action}'"
                }).encode())

        # Cleanup on disconnect
        try:
            del self.clients[token]
        except KeyError:
            pass
        client_socket.close()

