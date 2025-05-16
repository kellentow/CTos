import utils, time
from Hub import MainHub, logging
from Client import Client

# Configure logging
logging.basicConfig(
    handlers=[
        logging.StreamHandler(),  # Output logs to the console
        logging.FileHandler("proxy_hub.log", mode="a")  # Optionally log to a file
    ]
)

class ProxyHub(MainHub,Client):
    """
    ProxyHub acts as both a hub and a client, forwarding data between local and parent connections.
    It combines the behaviors of MainHub and Client to enable proxying and path handling.

    Args:
        name (str): The name of the proxy hub.
        parent (tuple, optional): The address of the parent server. Defaults to ("127.0.0.1", 5000).
    """
    def __init__(self, name, parent=("127.0.0.1", 5000)):
        """
        Initializes a ProxyHub instance with both hub and client capabilities.

        Args:
            name (str): The name of the proxy hub.
            parent (tuple, optional): The address of the parent server. Defaults to ("127.0.0.1", 5000).
        """
        MainHub.__init__(self, website=False, port=5100)
        Client.__init__(self, name=name, parent=parent)
    def shutdown(self):
        """
        Shuts down the proxy hub by disconnecting everything and disconnecting from the parent hub
        """
        Client.shutdown(self)
        MainHub.shutdown(self)
    def send(self,data):
        """ 
        Wrapper for the MainHub to also handle sending data to the hub's parents
        """
        if MainHub.send(self,data) == "../":
            utils.send(self.parent_socket,data)

if __name__ == '__main__':
    proxy_hub = ProxyHub("proxy1")
    proxy_hub.run()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        e.with_traceback()
    finally:
        print("Shutting down...")
        proxy_hub.shutdown()