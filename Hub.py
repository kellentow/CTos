from flask import Flask, jsonify, request, send_file
import socket
import time
import threading
import requests
import os

class Device:
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name
        self.last_ping = time.time()

    def is_alive(self):
        return time.time() - self.last_ping < 10

class MainHub:
    def __init__(self):
        self.ip = socket.gethostbyname(socket.gethostname())
        self.html = Flask(__name__)
        self.children = {}
        self.device_count = 0
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
        self.html.add_url_rule('/', 'index', self.website)
        self.html.add_url_rule('/<path:variable>', 'website', self.website)
        self.html.add_url_rule('/api/cmd', 'cmd', self.cmd)
        self.html.add_url_rule('/html/', 'filelist', self.filelist)
        self.html.add_url_rule('/html/<path:variable>', 'file', self.html_files)

    def cmd(self):
        data = request.json
        cmd = data.get('cmd')
        a = data.get('from')
        b = data.get('to')
        print(f"{a} {cmd} -> {b}")
        for device in self.children.values():
            if device.name == a:
                a_ip = device.ip
            if device.name == b:
                b_ip = device.ip

        r = requests.post(f"http://{b_ip}/cmd", json={"cmd": cmd, "from": a_ip})
        return r.json , r.status_code

    def filelist(self):
        files = os.listdir("html")
        return jsonify(files)
    
    def website(self, variable=""):
        if variable == "":
            variable = "home"
        if variable.endswith(".html"):
            variable = variable[:-5]
        return send_file(f"html/{variable}.html")

    def html_files(self, variable=""):
        try:
            if not variable.startswith("html/"):
                file_path = os.path.join("html", variable)
            else:
                file_path = os.path.join("html", variable[5:])
            if not os.path.isfile(file_path):
                raise FileNotFoundError
            return send_file(file_path)
        except FileNotFoundError:
            return "file not found", 404

    def check_ping(self):
        while not self.shutdown_flag.is_set():
            with self.lock:
                for name, child in list(self.children.items()):
                    if not child.is_alive():
                        self.children.pop(name)
                        print(f"Removed {name} from the list of children")
            time.sleep(10)

    def add_device(self, name, ip):
        with self.lock:
            self.children[name] = Device(ip, name)
            return "Device added successfully"
        
    def hub_info(self):
        print(f"Hub info requested")
        return jsonify({
            "ip": self.ip,
            "children": [child.name for child in self.children.values()]
        })
    
    def dynamic_route(self, variable=""):
        args = variable.split("/")
        print(f"{args}'s Info requested")
        parent = self
        try:
            for arg in args:
                parent = parent.children[arg]
            if "children" in parent.__dict__:
                return jsonify({"ip": parent.ip, "name": parent.name, "children": [child.name for child in parent.children.values()]})
            else:
                return jsonify({"ip": parent.ip, "name": parent.name})
        except KeyError:
            print(f"Invalid path")
            return "Invalid path", 500
        except Exception as e:
            print(f"Something went wrong: {e}")
            return "Something went wrong", 500

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
        return self.add_device(name, ip)

    def remove_device_route(self):
        data = request.json
        name = data.get('name')
        return self.remove_device(name)

    def ping(self):
        data = request.json
        name = data.get('name')
        ip = data.get('ip')
        print(f"Received ping from {name}")
        with self.lock:
            if name not in self.children:
                self.children[name] = Device(ip, name)
            self.children[name].last_ping = time.time()
            return "pong"
            

    def shutdown(self):
        self.shutdown_flag.set()
        shutdown_thread = threading.Thread(target=request.environ.get('werkzeug.server.shutdown'))
        shutdown_thread.start()
        return "Shutting down..."

    def run(self):
        threading.Thread(target=self.check_ping).start()
        self.html.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main_hub = MainHub()
    threading.Thread(target=main_hub.run).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        print("Shutting down...")
        # Stop MainHub
        requests.post("http://127.0.0.1:8000/shutdown")
        exit()