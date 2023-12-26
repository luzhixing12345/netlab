import socket
import time
from config import *
import threading
from typing import List
import struct
import sys

FILE_DATA = []


class Client:
    def __init__(self) -> None:
        self.file_content = []  # 文件内容
        self.status: TCPstatus  # 客户端的状态, 仿照 TCP 三次握手
        self.rtt = 0
        self.init_socket()
        self.establish_connection()
        # self.receive_data()

    def init_socket(self):
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 服务端地址
        self.server_address = (SERVER_IP, SERVER_CONTROL_PORT)
        self.data_socket.bind((CLIENT_IP, CLIENT_DATA_PORT))

    def establish_connection(self):
        """
        仿照 TCP 三次握手, 服务端确定 RTT, 客户端确定文件大小
        """
        # 初次建立
        self.status = TCPstatus.CLOSED
        
        syn_retry_time = 0
        tcp_syn_timeout = TCP_SYN_TIMEOUT
        
        while syn_retry_time < TCP_SYN_RETIRES:
            # SYN 为客户端的发送时间戳
            # syn_data = struct.pack("!Q", int(time.time() * 1000))
            self.data_socket.settimeout(tcp_syn_timeout)
            start_time = self.get_time()
            syn_data = f'SYN {syn_retry_time} {start_time}'
            self.control_socket.sendto(syn_data.encode(), self.server_address)
            
            self.status = TCPstatus.SYN_SENT
            self.log('send SYN')
            try:
                syn_ack_data, _ = self.data_socket.recvfrom(1024)
                syn_ack_data = SYN_ACK_PATTERN.match(syn_ack_data.decode())
                end_time = self.get_time()
                self.rtt = end_time - start_time
                self.log(f'receive SYN ACK, file size = [{syn_ack_data.group("filesize")}] rtt = [{self.rtt}]')
                break
            except socket.timeout:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log('SYN ACK timeout, double')

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)
        
        self.status = TCPstatus.ESTABLISHED
        syn_retry_time = 0
        tcp_ack_timeout = self.rtt * 2
        
        while syn_retry_time < TCP_SYN_RETIRES:
            # SYN 为客户端的发送时间戳
            self.control_socket.settimeout(tcp_ack_timeout)
            syn_data = 'ACK'
            self.control_socket.sendto(syn_data.encode(), self.server_address)
            self.log('send ACK')
            try:
                syn_ack_data, _ = self.data_socket.recvfrom(1024)
                self.log(f"received data: {syn_ack_data.decode()}")
                break
            except socket.timeout:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log('ACK timeout, double')
        
        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)
            

    def receive_data(self):
        """ """
        self.threads: List[threading.Thread] = []
        for _ in RECEIVE_THREAD_NUMBER:
            thread = threading.Thread(target=self.receive_package, args=())
            thread.start()
            self.threads.append(thread)

        for thread in self.threads:
            thread.join()

    def receive_package(self):
        """
        每个线程执行的函数
        """
        data, _ = self.data_socket.recvfrom(CHUNK_SIZE + 8)
        thread_id, sequence_number, timestamp = struct.unpack("!IIQ", data[:16])
        message_content = data[16:].decode("utf-8")
        self.file_content.append(message_content)

        ack_header = struct.pack("!IIQ", thread_id, sequence_number, int(time.time() * 1000))
        self.control_socket.sendto(ack_header, self.server_address)

    def close_socket(self):
        # 关闭socket
        self.control_socket.close()
        self.data_socket.close()
        
    def log(self, info: str):
        sys.stderr.write(f"client: {info}\n")
        
    def get_time(self):
        return time.time()


def main():
    client = Client()
    client.close_socket()


if __name__ == "__main__":
    main()
