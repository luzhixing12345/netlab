import socket
import os
import threading
import time
from config import *
import struct
import sys
from typing import List, Dict
import hashlib

class PackageInfo:
    def __init__(self, send_time: float, seek_pos: int, package_size: int) -> None:
        self.send_time: float = send_time  # 数据包发送时间
        self.seek_pos: int = seek_pos  # 偏移量
        self.package_size: int = package_size  # 包大小

class ServerInfo:
    package_sent_number = 0 # 发送的数据包个数
    ack_received_number = 0 # 接收到的 ACK 个数

class Server:
    def __init__(self) -> None:
        self.rtt = 0
        self.info = ServerInfo()
        self.info.package_sent_number = 0
        self.info.ack_received_number = 0
        self.status = TCPstatus.CLOSED

        self.init_socket()
        self.status = TCPstatus.LISTEN
        

        # 确定发送文件是否压缩
        if ENABLE_PRE_ZIP:
            start_time = time.time()
            if not os.path.exists(ZIP_FILE_PATH):
                raise FileNotFoundError(ZIP_FILE_PATH)
            with open(FILE_PATH, "rb") as f_in:
                with ZIP_LIB.open(ZIP_FILE_PATH, "wb") as f_out:
                    f_out.writelines(f_in)
            end_time = time.time()
            print(f"zip time: [{end_time - start_time}]")

        else:
            if not os.path.exists(FILE_PATH):
                raise FileNotFoundError(FILE_PATH)

        # 确定文件路径和大小
        self.file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        self.file_size = os.path.getsize(self.file_path)

        # 初始化计时器
        self.timers: Dict[int, Dict[int, PackageInfo]] = {}
        for thread_id in range(SERVER_SEND_THREAD_NUMBER):
            self.timers[thread_id] = {}
            
        self.init_thread()

    def run(self):
        self.establish_connection()
        self.receive_ack()
        self.send_data()

        for thread in self.receive_threads:
            thread.join()

        for thread in self.send_threads:
            thread.join()

    def init_socket(self):
        """
        创建两个 socket

        - control_socket 用于传输 ACK NAK 确认帧
        - data_socket 用于传输数据包
        """
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        control_address = (SERVER_IP, SERVER_CONTROL_PORT)
        self.control_socket.bind(control_address)
        print(f"UDP control socket start, listen {control_address}")

        # 发送端的发送缓冲区设置为最大
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, MAX_UDP_BUFFER_SIZE)
        self.client_address = (CLIENT_IP, CLIENT_DATA_PORT)
        print("UDP data socket start, waiting for client...")

    def init_thread(self):
        '''
        初始化所有线程, 但并不执行
        '''
        
        self.send_threads: list[threading.Thread] = [] # 发送线程
        self.receive_threads: List[threading.Thread] = [] # 接收 ACK 线程
        self.timer_checker = threading.Thread(target=self.check_timer_arrival, args=()) # 定时器检查线程
        self.timer_checker.daemon = True
        
        # 初始化发送线程
        # 计算每一个线程需要发送的文件大小, 如果不能整除的话采用四舍五入的方式
        thread_send_size = int(round(self.file_size / SERVER_SEND_THREAD_NUMBER))
        for thread_id in range(SERVER_SEND_THREAD_NUMBER - 1):
            thread = threading.Thread(target=self.send_package, args=(thread_id, thread_send_size))
            thread.daemon = True
            self.send_threads.append(thread)
        # 将剩余部分都放入最后一个线程发送
        bias = thread_send_size * SERVER_SEND_THREAD_NUMBER - self.file_size
        thread = threading.Thread(
            target=self.send_package,
            args=(
                SERVER_SEND_THREAD_NUMBER - 1,
                thread_send_size - bias,
            ),
        )
        thread.daemon = True
        self.send_threads.append(thread)
        
        # 初始化接收线程
        for thread_id in range(SERVER_ACK_HANDLE_THREAD_NUMBER):
            thread = threading.Thread(target=self.handle_ack, args=(thread_id,))
            thread.daemon = True
            self.receive_threads.append(thread)

    def establish_connection(self):
        """
        三次握手建立连接
        
        初步计算 RTT 时延, 告知 client 传输文件大小
        """
        syn_data, _ = self.control_socket.recvfrom(1024)
        syn_data = SYN_PATTERN.match(syn_data.decode())

        client_send_time = syn_data.group("time")
        self.log(f'receive SYN {syn_data.group("syn_number")} {client_send_time}')
        start_time = self.get_time()
        self.rtt = start_time - float(client_send_time)
        self.log(f"rtt = {self.rtt}")
        self.status = TCPstatus.SYN_RCVD

        syn_ack_data = f"SYN ACK {self.file_size}"
        self.data_socket.sendto(syn_ack_data.encode(), self.client_address)
        self.log("send syn ack")

        syn_retry_time = 0
        tcp_syn_timeout = self.rtt * 10

        while syn_retry_time < TCP_SYN_RETIRES:
            self.control_socket.settimeout(tcp_syn_timeout)
            try:
                ack_data, _ = self.control_socket.recvfrom(1024)
                self.log("receive ACK")
                self.status = TCPstatus.ESTABLISHED
                break
            except socket.timeout:
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.rtt *= 2
                self.log("ACK timeout, double")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

    def send_data(self):
        """
        所有发送线程都可以开始发送数据了
        """
        for thread in self.send_threads:
            thread.start()

    def send_package(self, thread_id: int, thread_send_size: int):
        '''
        每个线程根据偏移量分块发送
        
        1                            4                          8
        +----------------------------+--------------------------+
        |                            |                          |
        |         thread id          |      sequence number     |
        |                            |                          |
        +----------------------------+--------------------------+
        |                                                       |
        |                      start offset                     |
        |                                                       |
        +-------------------------------------------------------+
        |                                                       |
        |                         data                          |
        |                                                       |
        +-------------------------------------------------------+
        '''
        start_offset = thread_id * thread_send_size  # 起始偏移位置
        self.log(f"start sending thread {thread_id}")

        with open(self.file_path, "rb") as f:
            f.seek(start_offset)

            # 如果小于分块大小, 直接一次性发送过去
            if thread_send_size <= CHUNK_SIZE:
                data = f.read(thread_send_size)
                header = struct.pack("!IIQ", thread_id, sequence_number, start_offset)
                full_message = header + data
                send_time = self.get_time()
                self.data_socket.sendto(full_message, self.client_address)

                self.log(f"[{thread_id}] send data {len(data)}")
                self.timers[thread_id][0] = PackageInfo(
                    send_time=send_time,
                    seek_pos=start_offset,
                    package_size=thread_send_size,
                )
            else:
                # 按照分块大小发送 n 次
                n = thread_send_size // CHUNK_SIZE
                for sequence_number in range(n):
                    # 发送的文件内容数据
                    seek_pos = start_offset + sequence_number * CHUNK_SIZE  # 文件偏移量

                    if sequence_number == n - 1:
                        # 最后一次把 thread_send_size 剩余的部分都发过去
                        package_size = thread_send_size - sequence_number * CHUNK_SIZE
                    else:
                        package_size = CHUNK_SIZE  # 数据块大小
                    
                    data = f.read(package_size)    
                    header = struct.pack("!IIQ", thread_id, sequence_number, seek_pos)

                    full_message = header + data
                    send_time = self.get_time()  # 发送时间
                    self.data_socket.sendto(full_message, self.client_address)

                    self.log(f"[{thread_id}] send data {sequence_number}:{len(full_message)}")
                    self.info.package_sent_number += 1
                    # 添加一个定时器
                    self.timers[thread_id][sequence_number] = PackageInfo(
                        send_time=send_time,
                        seek_pos=seek_pos,
                        package_size=package_size,
                    )

    def receive_ack(self):
        """
        创建接收线程, 准备收 ACK 数据包
        """
        self.control_socket.settimeout(None)
        for thread in self.receive_threads:
            thread.start()
        self.timer_checker.start()

    def handle_ack(self, thread_id):
        """
        处理来自 client 的 ack 数据包
        """
        while True:
            ack_data, _ = self.control_socket.recvfrom(1024)
            send_thread_id, sequence_number, timestamp = struct.unpack("!IId", ack_data[:16])
            self.log(f"[{thread_id}] receive {send_thread_id} {sequence_number}")
            self.info.ack_received_number += 1

    def check_timer_arrival(self):
        '''
        检查
        '''
        self.log('init timer checker')
        

    def close_socket(self):
        self.control_socket.close()
        self.data_socket.close()

    def log(self, info: str):
        sys.stderr.write(f"server: {info}\n")

    def show_statistical_info(self):
        self.log(f"send packages: {self.info.package_sent_number}")
        self.log(f"receive acks: {self.info.ack_received_number}")
        self.log(f'package loss: {round((self.info.package_sent_number - self.info.ack_received_number)/self.info.package_sent_number, 2)}')

    def get_time(self):
        return time.time()

    def calculate_md5(self, block_size=8192):
        md5_hash = hashlib.md5()
        with open(self.file_path, "rb") as file:
            for chunk in iter(lambda: file.read(block_size), b""):
                md5_hash.update(chunk)
        print(f'md5: {md5_hash.hexdigest()}')

def main():
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt as e:
        print(e)
        server.show_statistical_info()
        server.calculate_md5()
    finally:
        server.close_socket()
    print("over")


if __name__ == "__main__":
    main()
