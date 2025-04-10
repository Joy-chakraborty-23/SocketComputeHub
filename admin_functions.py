import json
import os
import psutil
from datetime import datetime, timedelta
import time

class AdminFunctions:
    def __init__(self, server_core):
        self.core = server_core
    
    def handle_admin_command(self, client_data, message):
        command = message.get('command')
        args = message.get('args', {})
        
        try:
            if command == 'add_user':
                self.add_user(client_data, args)
            elif command == 'delete_user':
                self.delete_user(client_data, args)
            elif command == 'list_users':
                self.list_users(client_data)
            elif command == 'view_logs':
                self.view_logs(client_data)
            elif command == 'server_status':
                self.get_server_status(client_data)
            # Add other admin commands here
            else:
                raise ValueError("Unknown command")
        except Exception as e:
            self.send_error(client_data, str(e))
    
    def add_user(self, client_data, args):
        username = args.get('username')
        password = args.get('password')
        is_admin = args.get('is_admin', False)
        
        if not username or not password:
            raise ValueError("Username and password required")
            
        with self.core.lock:
            with open(self.core.user_db, 'r+') as f:
                users = json.load(f)
                if username in users:
                    raise ValueError("User already exists")
                    
                users[username] = {
                    'password': self.core.hash_password(password),
                    'is_admin': is_admin,
                    'created': datetime.now().isoformat()
                }
                f.seek(0)
                json.dump(users, f)
                f.truncate()
                
        self.send_response(client_data, 'add_user', f"User {username} created")
        self.core.log_activity(client_data['username'], client_data['addr'][0], f'add_user:{username}')
    
    def delete_user(self, client_data, args):
        username = args.get('username')
        if not username:
            raise ValueError("Username required")
            
        with self.core.lock:
            with open(self.core.user_db, 'r+') as f:
                users = json.load(f)
                if username not in users:
                    raise ValueError("User does not exist")
                    
                if username == 'admin':
                    raise ValueError("Cannot delete admin user")
                    
                del users[username]
                f.seek(0)
                json.dump(users, f)
                f.truncate()
                
        self.force_disconnect_user(username)
        self.send_response(client_data, 'delete_user', f"User {username} deleted")
        self.core.log_activity(client_data['username'], client_data['addr'][0], f'delete_user:{username}')
    
    def list_users(self, client_data):
        with open(self.core.user_db, 'r') as f:
            users = json.load(f)
            
        active_users = []
        with self.core.lock:
            for client in self.core.clients:
                active_users.append({
                    'username': client['username'],
                    'ip': client['addr'][0],
                    'is_admin': client['is_admin'],
                    'login_time': client.get('login_time', 'N/A')
                })
                
        self.send_response(client_data, 'list_users', {
            'users': users,
            'active_users': active_users
        })
        self.core.log_activity(client_data['username'], client_data['addr'][0], 'list_users')
    
    def view_logs(self, client_data):
        logs = []
        try:
            with open(self.core.activity_log, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    logs.append(row)
        except FileNotFoundError:
            pass
                
        self.send_response(client_data, 'view_logs', logs[-100:])
        self.core.log_activity(client_data['username'], client_data['addr'][0], 'view_logs')
    
    def get_server_status(self, client_data):
        mem = psutil.virtual_memory()
        status = {
            'uptime': str(timedelta(seconds=time.time() - self.core.start_time)),
            'client_count': len(self.core.clients),
            'doc_size': len(self.core.document),
            'memory': f"{mem.used/1024/1024:.2f}MB / {mem.total/1024/1024:.2f}MB",
            'cpu': f"{psutil.cpu_percent()}%"
        }
        
        self.send_response(client_data, 'server_status', status)
    
    def force_disconnect_user(self, username):
        with self.core.lock:
            for client in self.core.clients[:]:
                if client['username'] == username:
                    try:
                        client['conn'].send(json.dumps({
                            'action': 'notification',
                            'message': 'You have been disconnected by admin'
                        }).encode())
                        client['conn'].close()
                    except:
                        pass
                    self.core.clients.remove(client)
                    self.core.log_activity('system', '0.0.0.0', f'force_disconnect:{username}')
    
    def send_response(self, client_data, command, result):
        try:
            client_data['conn'].send(json.dumps({
                'action': 'admin_response',
                'command': command,
                'result': result
            }).encode())
        except BrokenPipeError:
            print(f"Broken pipe error while sending {command} response.")
    
    def send_error(self, client_data, message):
        try:
            client_data['conn'].send(json.dumps({
                'action': 'error',
                'message': message
            }).encode())
        except BrokenPipeError:
            print("Broken pipe error while sending error message.")
