import socket
import os
import threading
import time
from config import *


def read_and_send(socket_conn: socket.socket, file_path: str, start_offset: int, chunk_size: int):
    with open(file_path, "rb") as file:
        file.seek(start_offset)  # 设置文件指针到指定的偏移位置
        data = file.read(chunk_size)
        socket_conn.send(data)

class Server:
    
    def __init__(self) -> None:
        self.control_socket: socket.socket
        self.client_control_address: socket._RetAddress
        self.data_socket: socket.socket
        self.client_data_address: socket._RetAddress
        self.init_socket()
        self.exchange_info()
        # self.prepare_send_threads()
        
    def init_socket(self):
        '''
        创建两个 socket
        
        - control_socket 用于传输 ACK NAK 确认帧
        - data_socket 用于传输数据包
        '''
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        control_address = (SERVER_IP, SERVER_CONTROL_PORT)
        self.control_socket.bind(control_address)
        print(f"UDP control socket start, listen {control_address}")
        
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF, CHUNK_SIZE)
        data_address = (SERVER_IP, SERVER_DATA_PORT)
        self.data_socket.bind(data_address)
        print(f"UDP data socket start, listen {data_address}")
        
        if ENABLE_PRE_ZIP:
            start_time = time.time()
            with open(FILE_PATH, 'rb') as f_in:
                with ZIP_LIB.open(ZIP_FILE_PATH, 'wb') as f_out:
                    f_out.writelines(f_in)
            end_time = time.time()
            print(f'zip time: [{end_time - start_time}]')
        
    def prepare_send_threads(self):
        '''
        创建 THREAD_NUMBER 个线程使用 data_socket 传输数据
        '''
        # 确认路径存在
        if ENABLE_PRE_ZIP:
            if not os.path.exists(ZIP_FILE_PATH):
                raise FileNotFoundError(ZIP_FILE_PATH)
        else:
            if not os.path.exists(FILE_PATH):
                raise FileNotFoundError(FILE_PATH)
        
        file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        file_size = os.path.getsize(file_path)
        self.threads = []
        for i in range(THREAD_NUMBER):
            start_offset = i * (file_size // THREAD_NUMBER)  # 计算每个线程的起始偏移位置
            thread = threading.Thread(target=read_and_send, args=(self.data_socket,file_path, start_offset, CHUNK_SIZE))
            self.threads.append(thread)

    def exchange_info(self):
        '''
        交换 c-s 的基础信息, 包括
        
        - RTT
        '''
        self.rtt = self.calculate_rtt()
        print(f'rtt = {self.rtt}')

    def calculate_rtt(self):
        '''
        通过 control_socket 计算当前网络的 RTT 大小
        '''
        rtts = []
        i = 0
        while True:
            data, self.client_control_address = self.control_socket.recvfrom(1024)
            # receive_time = time.time()
            # rtts.append(2 * (receive_time - float(data.decode())))
            i += 1
            print(f"receive {i}/{RTT_SEND_TIME}")
        return sum(rtts)/len(rtts)
    
    def run(self):
        '''
        '''
    
    def close_socket(self):
        self.control_socket.close()
        self.data_socket.close()

def main():

    server = Server()      
    server.close_socket()

if __name__ == "__main__":
    main()
