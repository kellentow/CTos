import os
import math
import requests
import socket
import threading
import time

class CTos():
    def __init__(self,name):
        print("Starting CToS")
        self.hub = None
        self.name = name
        self.ip = socket.gethostbyname(socket.gethostname())

        try:
            size = os.get_terminal_size()
            self.size = (size.columns, size.lines)
        except:
            self.size = (80, 24)
            print("Error getting true terminal size")

        self.find_hub()  # Moved after initializing self.hub
        self.clear()
        pinger = threading.Thread(target=self.ping)
        pinger.start()
        self.run()

    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.logo()
        if self.hub is not None:
            print(f"Hub IP: {self.hub}")
        else:
            print("No hub connected")

    def color(self, color=(None, None)):
        bg_color, fg_color = color

        # ANSI escape sequences for colors
        bg_code = {
            'black': '40',
            'red': '41',
            'green': '42',
            'yellow': '43',
            'blue': '44',
            'magenta': '45',
            'cyan': '46',
            'white': '47',
            None: '49'  # Default background color
        }
        fg_code = {
            'black': '30',
            'red': '31',
            'green': '32',
            'yellow': '33',
            'blue': '34',
            'magenta': '35',
            'cyan': '36',
            'white': '37',
            None: '39'  # Default foreground color
        }
        ansi_sequence = f"\033[{bg_code.get(bg_color)};{fg_code.get(fg_color)}m"
        return ansi_sequence
    
    def send_cmd(self, cmd, to):
        r = requests.post(f"http://{self.hub}/cmd",json={"cmd":cmd,"to":to,"from":self.name})
        if r.status_code == 200:
            print(r.json())
        else:
            print("Error sending command")
    
    def ping(self,interval=10):
        while True:
            if self.hub is not None:
                r = requests.post(f"http://{self.hub}/ping",json={"name":self.name,"ip":self.ip})
                if r.status_code == 200:
                    pass
                else:
                    self.hub = None
            time.sleep(interval)

    def logo(self):
        logo = [ "  ____ _____",
                f" / ___|_   _|{self.color()} ___   ___ ",
                f"| |     | | {self.color()} / _ \ / __|",
                f"| |___  | | {self.color()}| |_| |\__ \\",
                f" \____| |_| {self.color()} \___/ |___/"]
        for line in logo:
            if self.hub is not None:
                ansi = self.color((None, 'green'))
            else:
                ansi = self.color((None, 'red'))
            print(ansi + line)

    def find_hub(self, hubips=None):
        response = requests.Response()
        response.status_code = 404

        if self.hub is not None:
            while response.status_code != 200:
                response = requests.post(f"http://{self.hub}/remove_device", json={"name": self.name,"ip":self.ip})

        print("Finding Hub")
        self.hub = None
        if hubips is None:
            hubips = ["199.187.115.75:8000", "192.168.1.190:8000", "192.168.1.49:8000", "192.168.1.518000", "127.0.0.1:7100"]
        else:
            hubips = [hubips]
        for hubip in hubips:
            try:
                r = requests.post(f"http://{hubip}/ping", timeout=1,json={"name": self.name,"ip":self.ip})
                if r.status_code == 200:
                    self.hub = hubip
                    requests.post(f"http://{hubip}/ping", timeout=1,json={"name": self.name,"ip":self.ip,"parent":self.hub})
                    print("Hub found:", self.hub)
                    break  # Found the hub, no need to continue trying other IPs
            except requests.exceptions.Timeout:
                print(f"Timeout while trying {hubip}")
            except requests.exceptions.RequestException as e:
                print(f"Error connecting to {hubip}: {e}")
        else:
            print("Hub not found")

    def run(self):
        while True:
            inp = input(">>> ")
            if inp == "exit":
                self.clear()
                response = requests.Response()
                response.status_code = 404
                while response.status_code != 200:
                    response = requests.post(f"http://{self.hub}/remove_device", json={"name": "Computer","ip":self.ip})
                break
            elif inp == "restart":
                self.clear()
                self.__init__()
            elif inp == "clear" or inp == "cls":
                self.clear()
            elif inp.startswith("hub"):
                args = inp.split()
                if len(args) > 1:
                    if args[1] == "set":
                        if len(args) > 2:
                            self.find_hub(args[2])
                        else:
                            print("Please specify hub ip")
                    elif args[1] == "clear":
                        self.hub = None
                    elif args[1] == "find":
                        self.find_hub()
                    elif args[1] == "info":
                        if len(args) > 2:
                            r = requests.get(f"http://{self.hub}/info/{'/'.join(args[2:])}", timeout=5)
                        else:
                            r = requests.get(f"http://{self.hub}/info/", timeout=5)
                        if r.status_code == 200:
                            print(r.json())
                        else:
                            print("Error getting info from hub")
                    elif args[1] == "version":
                        r = requests.get(f"http://{self.hub}/version", timeout=5)
                        if r.status_code == 200:
                            print(f"The hub is v{r.json()}")
                        else:
                            print("Error getting version from hub")
                    elif args[1] == "cmd":
                        if len(args) > 3:
                            requests.post(f"http://{self.hub}/cmd/", json={"cmd": args[2],"to":args[3],"from":self.name})
                        else:
                            print("Please specify recepiant and the command")
                    elif args[1] == "help":
                        print("hub set [ip] - Set hub ip")
                        print("hub clear - Clear hub ip")
                        print("hub find - Find hub ip")
                        print("hub info [device] - Get info about device")
                        print("hub version - Get version of hub")
                        print("hub help - Print this help")
                    else:
                        print("Unknown command")
            elif inp == "ls":
                if self.hub is not None:
                    r = requests.get(f"http://{self.hub}/list", timeout=5)
                    if r.status_code == 200:
                        devices = r.json()
                        max_ip_length = max([len(ip) for ip in devices.values()])
                        max_device_length = max([len(device) for device in devices])
                        max_device_Ip_length = max([len(device)+3+len(devices[device]) for device, ip in devices.items()])
                        dash = "-" * math.ceil((max_device_Ip_length - 8)/2)
                        print(dash + "Devices:" + dash)
                        for device, ip in devices.items():
                            space_num_device = max_device_length - len(device)
                            space_num_ip = max_ip_length - len(ip)
                            print(f"{device}{' ' * space_num_device} - {ip}{' ' * space_num_ip}")
                    else:
                        print("Error getting device list")
                else:
                    print("No hub connected")
            elif inp.startswith("cmd"):
                args = inp.split()
                if len(args) > 1:
                    if self.hub is not None:
                        if len(args) > 2:
                            self.send_cmd(args[1], args[2])
                        else:
                            print("Please specify recepiant and the command")
                    else:
                        print("No hub connected")
            elif inp == "help":
                print("exit - exit the program")
                print("clear - clear the screen")
                print("restart - restart the program")
                print("hub [command] - manage hub")
                print("ls - list devices")
                print("cmd [command] [device] - send command to device")
                print("help - show this help")
            else:
                print("Unknown command")

if __name__ == "__main__":
    term = CTos("device1")
