import socket
import time
from config import *

class Client:
    
    def __init__(self) -> None:
        self.init_socket()
        self.exchange_info()
    
    def init_socket(self):
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 服务端地址
        self.server_address = (SERVER_IP, SERVER_CONTROL_PORT)

    def exchange_info(self):
        
        for i in range(RTT_SEND_TIME):
            send_time = f'{time.time()}'
            self.control_socket.sendto(send_time.encode(), self.server_address)
            i += 1
            print(f'send {i}/{RTT_SEND_TIME}')
            

    def close_socket(self):
        # 关闭socket
        self.control_socket.close()
        self.data_socket.close()
        
def main():

    client = Client()    
    client.close_socket()

if __name__ == "__main__":
    main()
