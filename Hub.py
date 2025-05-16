from flask import Flask, send_file
import socket
import time
import threading
import os, sys
import logging
import utils
import gc

FLAGS = {"plugins":False}

if utils.is_admin() and os.name == "posix":
    os.system("sudo ulimit -n 65535") #more fd-s
    os.system("sudo taskset -c 2 python3 Hub.py") #main on 1 core but it gets the entire core

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # Log format
    handlers=[
        logging.StreamHandler(),  # Output logs to the console
        logging.FileHandler("main_hub.log", mode="a")  # Optionally log to a file
    ]
)

def is_alive(socc: socket.socket):
    try:
        # Peek at the socket to check if it's still alive
        data = socc.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            # If no data is returned, the socket is closed
            return False
    except BlockingIOError:
        # No data available, but the socket is still open
        return True
    except ConnectionResetError:
        # Connection was reset by the peer
        return False
    except Exception as e:
        # Any other exception indicates the socket is not alive
        print(f"DEBUG: Exception in is_alive: {e}")
        return False
    return True

class Device:
    def __init__(self, socket:socket.socket, addr, name:str, parent):
        self.logger = logging.getLogger(f"Device-{name}")
        self.parent:MainHub = parent
        self.socket = socket
        self.addr = addr
        self.name:str = name
        self.logger.info(f"{addr[0]}:{addr[1]} as {name} connected")
        self.recv_buffer:list[dict] = []
        self.send_buffer:list[dict] = []
        self.lock:threading.Lock=threading.Lock()
        self.thread:threading.Thread = threading.Thread(target=self.worker,name=name,daemon=True)
        self.thread.start() #start last to prevent race conditions

    def worker(self):
        try:
            while is_alive(self.socket) and not self.parent.shutdown_flag.is_set():
                payload = "a"
                while payload is not None:
                    with self.lock:
                        payload = utils.recv(self.socket)
                        if payload is not None:
                            self.recv_buffer.append(payload)

                        if len(self.send_buffer) > 0:
                            for packet in self.send_buffer:
                                utils.send(self.socket,packet)
                    time.sleep(0)
                for packet in self.recv_buffer:
                    self.handle_packet(packet)
        except Exception as e:
            self.logger.error(f"Exception in worker: {e}")
        finally:
            self.logger.info(f"{self.addr[0]}:{self.addr[1]} as {self.name} disconnected")
    
    def __del__(self):
        self.socket.close()
        self = None
    def handle_packet(self,packet=None):
        if packet is None:
            return
        protocol_handler = self.parent.protocols.get(packet["protocol"])
        if protocol_handler is not None and FLAGS["plugins"]:
            new_packet = protocol_handler[0].handle(self,packet)
            self.parent.send(new_packet)
        else:
            self.parent.send(packet)

class MainHub:
    def __init__(self,website=True,port=5000):
        self.logger = logging.getLogger("Main Hub")
        self.children = {}
        self.protocols = {}
        self.device_count = 0
        self.shutdown_flag = threading.Event()
        self.lock = threading.Lock()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024*1024)
        self.server_socket.bind(("0.0.0.0",port))
        self.ip = self.server_socket.getsockname()[0]
        self.path = "/"

        self.server_socket.listen(5)
        self.server_thread = threading.Thread(target=self.server_handler, daemon=True)
        if website:
            # Adding routes
            self.html = Flask(__name__)
            self.add_routes()
        else:
            self.html = None
        if FLAGS["plugins"]:
            self.load_protocols()

    def load_protocols(self):
        import importlib.util
        plugins_dir = "./plugins/"
        for filename in os.listdir(plugins_dir):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            module_name = filename[:-3]
            file_path = os.path.join(plugins_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Validate the module
                    if hasattr(module, "__protocol__") and hasattr(module, "main"):
                        protocol_id = module.__protocol__
                        protocol_version = getattr(module, "__version__", "unknown")
                        protocol_name = getattr(module, "__name__", "unknown")
                        if not isinstance(protocol_id, str):
                            self.logger.error(f"Invalid protocol ID in {filename}: {protocol_id}")
                            continue
                        if protocol_id in self.protocols:
                            self.logger.warning(f"Duplicate protocol ID {protocol_id} in {filename}")
                            continue
                        self.protocols[protocol_id] = (module.main(), protocol_version, protocol_name)
                        self.logger.info(f"Loaded protocol: {protocol_name} (ID: {protocol_id}, Version: {protocol_version})")
                    else:
                        self.logger.error(f"Invalid plugin: {filename} (missing __protocol__ or main)")
            except Exception as e:
                self.logger.error(f"Failed to load plugin {filename}: {e}")
    
    def server_handler(self):
        while not self.shutdown_flag.is_set():
            for name in list(self.children.keys()):
                device = self.children[name]
                if not is_alive(device.socket):
                    self.children.pop(name)
            try:
                client_socket, client_address = self.server_socket.accept()
                client_socket.settimeout(2)  # Set a timeout so handshake doesn't last too long
            except OSError:
                self.logger.error("OSError while accepting connection")
                continue
            try:
                length_byte = client_socket.recv(1)
                if length_byte == b"":
                    client_socket.close() #bad thing happened, make them try again
                else:
                    length = int.from_bytes(length_byte,"big",signed=False)
                    name = client_socket.recv(length).decode("ascii")
                    client_path = f"{self.path}/{name}".replace("//","/")
                    client_socket.send(len(client_path).to_bytes(length=4,byteorder="big")) #up to 16711935 devices in a path
                    client_socket.send(client_path.encode("ascii"))
                    client_socket.settimeout(None)
                    self.children[name] = Device(client_socket,client_address,name,self)
            except socket.timeout:
                self.logger.info("Socket timeout while waiting for client data")
                client_socket.close()
                continue

    def send(self,data=None):
        if data is None:
            return #Protocol stopped data transfer or data was invalid
        dest = data["dest"]
        frm = data["from"]
    
        # Remove the hub's path prefix from the destination path
        if dest.startswith(self.path):
            rel_path = dest[len(self.path):].lstrip("/")
        else:
            rel_path = "../" # in future handle relative paths

        # The next hop is the first component of the relative path
        next_dest = rel_path.split("/", 1)[0] if rel_path else "../"
        
        if next_dest != "../":
            print(f"{frm} -> {self.path} -> {dest}")
            if next_dest not in self.children:
                return print(f"{next_dest} is not a child of {self.path}")
            
            dest:Device = self.children[next_dest]
            dest.send_buffer.append(data)
        else:
            parent_path = "/".join(self.path.split("/")[:-1])
            print(f"{frm} -> {self.path} -> {parent_path}")
            return "../"

    def add_routes(self):
        def website(variable=""):
            if variable == "":
                variable = "home"
            if variable.endswith(".html"):
                variable = variable[:-5]
            return send_file(f"html/{variable}.html")

        def html_files(variable=""):
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
        self.html.add_url_rule('/', 'index', website)
        self.html.add_url_rule('/<path:variable>', 'website', website)
        self.html.add_url_rule('/html/<path:variable>', 'file', html_files)

    def run(self,port=8000):
        if self.html is not None:
            self.html.run(host='0.0.0.0', port=port)
        self.server_thread.start()

    def shutdown(self):
        self.shutdown_flag.set()
        self.server_thread.join()
        for child in self.children:
            with child.lock:
                child.thread.join()

if __name__ == '__main__':
    main_hub = MainHub()
    try:
        main_hub.run()
    except Exception as e:
        e.with_traceback()
    print("Shutting down...")
    main_hub.shutdown()
    exit()