import socket
import time
import threading
import requests
from flask import Flask, jsonify, request

class Device:
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name
        self.last_ping = time.time()

    def is_alive(self):
        return time.time() - self.last_ping >= 10

class ProxyHub:
    def __init__(self,name):
        self.name = name
        self.ip = socket.gethostbyname(socket.gethostname())
        self.html = Flask(__name__)
        self.children = {}
        self.parent = "http://192.168.1.49:8000"
        self.connected = False
        self.shutdown_flag = threading.Event()
        self.lock = threading.Lock()

        # Adding routes
        self.add_routes()
    
    def add_routes(self):
        self.html.add_url_rule('/api/ping', 'ping', self.ping, methods=['POST'])
        self.html.add_url_rule('/api/add_device', 'add_device', self.add_device_route, methods=['POST'])
        self.html.add_url_rule('/api/remove_device', 'remove_device', self.remove_device_route, methods=['POST'])
        self.html.add_url_rule('/api/list', 'list_devices', self.list_devices, methods=['GET'])
        self.html.add_url_rule('/api/info/', 'get_info', self.hub_info)
        self.html.add_url_rule('/api/info/<path:variable>', 'dynamic_route', self.dynamic_route)
        self.html.add_url_rule('/api/shutdown', 'shutdown', self.shutdown, methods=['POST'])

    def check_ping(self):
        while not self.shutdown_flag.is_set():
            with self.lock:
                for name, child in list(self.children.items()):
                    if not child.is_alive():
                        self.children.pop(name)
                        print(f"Removed {name} from the list of children")
            time.sleep(10)

    def add_device(self, name, ip, otself=None):
        with self.lock:
            if name in self.children:
                return "Device already exists", 500
            else:
                if otself is not None:
                    self.children[name] = otself
                else:
                    self.children[name] = Device(ip, name)
                request.post(f"{self.parent}/add_device", json={"name": self.name, "ip": self.ip})
                return "Device added successfully"
            

    def remove_device(self, name):
        with self.lock:
            if name in self.children:
                self.children.pop(name)
                return "Device removed successfully"
            else:
                return "Device does not exist", 500

    def list_devices(self):
        with self.lock:
            return jsonify({name: device.ip for name, device in self.children.items()})

    def add_device_route(self):
        data = request.json
        name = data.get('name')
        ip = data.get('ip')
        otself = data.get('device')
        return self.add_device(name, ip, otself=otself)

    def remove_device_route(self):
        data = request.json
        name = data.get('name')
        return self.remove_device(name)

    def ping(self):
        data = request.json
        ip = data.get('ip')
        name = data.get('name')
        print(f"Received ping from {name}")
        with self.lock:
            if name not in self.children:
                self.children[name] = Device(ip, name)
            self.children[name].last_ping = time.time()
            return "pong"
    def hub_info(self):
        with self.lock:
            r = requests.get(f"{self.parent}/info/")
            return r.json()
        
    def dynamic_route(self, *args):
            with self.lock:
                var="/".join(args)
                r = requests.get(f"{self.parent}/info/{var}")
                return r.json(), r.status_code

    def ping_hub(self):
        while not self.shutdown_flag.is_set():
            try:
                r = requests.post(f"{self.parent}/ping", json={"name": self.name, "ip": self.ip})
                self.connected = r.status_code == 200
                if self.connected:
                    print("Ping to main hub successful")
                else:
                    print("Ping to main hub failed")
            except requests.ConnectionError:
                self.connected = False
                print("Connection error while pinging main hub")
            time.sleep(10)

    def shutdown(self):
        self.shutdown_flag.set()
        shutdown_thread = threading.Thread(target=request.environ.get('werkzeug.server.shutdown'))
        shutdown_thread.start()
        return "Shutting down..."

    def run(self):
        threading.Thread(target=self.ping_hub).start()
        threading.Thread(target=self.check_ping).start()
        self.html.run(host='0.0.0.0', port=7100)

if __name__ == '__main__':
    proxy_hub = ProxyHub("proxy1")
    threading.Thread(target=proxy_hub.run).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        print("Shutting down...")
        # Stop ProxyHub
        requests.post("http://127.0.0.1:7100/shutdown")
        exit()