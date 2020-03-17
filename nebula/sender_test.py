import socket
import time

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 23456  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print("Sending")
    time.sleep(1)
    s.sendall(b"Hello, world")
    time.sleep(4)
    s.sendall(b"Hello, world2")
    print("Done")
