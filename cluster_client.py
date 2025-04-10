# cluster_client.py
import socket, json

class ClusterClient:
    def __init__(self, ip, port):
        self.addr = (ip, port)
        self.sock = None
        self.token = None

    def connect(self, username, password):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect(self.addr)
        except:
            return False
        # authenticate
        self.sock.send(json.dumps({
            "username": username,
            "password": password
        }).encode())
        resp = json.loads(self.sock.recv(4096).decode())
        if resp.get("status") == "authenticated":
            self.token = resp["session_token"]
            return True
        return False

    def execute(self, code):
        # send code to cluster
        msg = {
            "action": "execute",
            "token": self.token,
            "code": code,
            "files": []
        }
        self.sock.send(json.dumps(msg).encode())
        # wait for result
        resp = json.loads(self.sock.recv(65536).decode())
        # if error, ask AI suggestion locally
        if resp.get("action") == "error":
            return {"status":"error", "message":resp["message"], "suggestion": ""}
        return {"status":"success", "output":resp.get("output","")}

