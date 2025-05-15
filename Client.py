import contextlib
import socket
import threading
import time
import utils

def is_alive(conn: socket.socket): #https://stackoverflow.com/a/62277798 thank youuuuuuu
    try:
        data = conn.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            return False
    except BlockingIOError:
        return True  # socket is open and reading from it would block
    except ConnectionResetError:
        return False  # socket was closed for some other reason
    except Exception as e:
        return False
    return False
    
class Client:
    def __init__(self,name,parent=("127.0.0.1",5000)):
        self.name = name
        self.parent = parent
        self.connected = False
        self.buffer = bytearray()
        self.shutdown_flag = threading.Event()
        self.lock:threading.Lock=threading.Lock()
        self.buffer:list = []
        self.parent_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.thread:threading.Thread = threading.Thread(target=self.check_ping, daemon=True)
        self.thread.start()
        self.path = "/"
    
    def worker(self):
        while not self.shutdown_flag.is_set():
            self.check_ping()
            time.sleep(0.1)
    
    def check_ping(self):
        self.connected = is_alive(self.parent_socket)
        if not self.connected:
            try:
                try:
                    self.parent_socket.connect(self.parent)
                except Exception:
                    self.connected = True
                    return
                # Send your name as handshake, following the protocol
                name_bytes = self.name.encode("ascii")
                self.parent_socket.sendall(len(name_bytes).to_bytes(1, "big"))
                self.parent_socket.sendall(name_bytes)
                
                path_length = int.from_bytes(self.parent_socket.recv(4),byteorder="big")
                self.path = self.parent_socket.recv(path_length).decode("ascii")
                self.connected = True
                print(f"Connected to server at {self.parent[0]}:{self.parent[1]} as {self.path}")
            except Exception as e:
                print(f"Failed to connect to server: {e}")
                self.connected = False
    def recv(self):
        return utils.recv(self.parent_socket)
    def send(self, packet=None):
        """
        Send a packet to the parent socket.

        Args:
            is_header (bool): Whether this is a header packet.
            packet (dict or list): The packet data. will be encoded as JSON (ASCII).

        Raises:
            TypeError: If packet is not JSON encodable.
        """
        packet["from"] = self.path
        utils.send(self.parent_socket,packet)
            
    def shutdown(self):
        self.shutdown_flag.set()
        if is_alive(self.parent_socket):
            self.parent_socket.shutdown(socket.SHUT_RDWR)
        with contextlib.suppress(Exception):
            self.parent_socket.close()