from Client import Client
import time, utils

#SelfEcho Test

#settings
packets=1000
max_trys=50 #1 try = 1ms

#state
fails=0
latency=[float("inf"),0,0]
total_data = 0

def bytes_to_readable(bytes:int):
    dif = 2**10
    cur = 1
    names = ["B","KiB","MiB","GiB","TiB","PiB"]
    for item in names:
        if cur <= bytes < cur*dif:
            return f"{bytes / cur:.2f}{item}"
        cur *= dif

payload = {"protocol":0,"payload":"","dest":"/Test_reciever"}
client1 = Client("Test_sender",parent=("192.168.1.168",5000))
client2 = Client("Test_reciever",parent=("192.168.1.168",5000))
time.sleep(0.1)
for i in range(packets):
    fraction_text = f"\r{i+1}{" "*(len(str(packets))-len(str(i+1)))}/{packets}"
    print(f"{fraction_text}  {round((i+1)/packets*100)}%",end=" "*10)
    payload["payload"] = "E"*(2**20) #1MiB
    total_data += len(utils.coder(payload, encode=True)[1])
    start = time.time()
    client1.send(payload)
    time.sleep(0)
    trys = 0
    got = None
    while got != payload and trys < max_trys:
        trys+=1
        got=client2.recv()
    if trys >= max_trys:
        fails +=1
        print(f"\n{i}: Message not recieved properly\n")
    else:
        l = time.time()-start
        latency[0] = min(latency[0] ,l)
        latency[1] += l
        latency[2] = max(latency[2] ,l)

print(f"""\nPacket data:
Sent: {packets}
Dropped: {fails}
Sent%: {100-(fails/packets*100)}
Dropped%: {fails/packets*100}
Bytes: {bytes_to_readable(total_data)}
B/s: {bytes_to_readable(round(total_data/latency[1],2))}""")

print(f"""\nLatency:
Send Time: {round(latency[1]*1000,3)}ms
Min Latency: {round(latency[0]*1000,3)}ms
Avg Latency: {round((latency[1]*1000)/packets,3)}ms
Max Latency: {round(latency[2]*1000,3)}ms""")
