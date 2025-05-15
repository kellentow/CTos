import os
class Protocol:
    def handle(self,packet):
        return packet


class PacketError(Exception):
    def __init__(self, *args, **kwargs):
        super(self).__init__(*args, **kwargs)