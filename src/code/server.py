import socket
import os
import threading
import time
from config import *
import struct
import sys
from typing import List, Dict


class Server:
    def __init__(self) -> None:
        self.rtt = 0
        self.package_sent_number = 0
        self.ack_received_number = 0
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
        self.timers: Dict[int, Dict[int, float]] = {}
        for thread_id in range(SERVER_SEND_THREAD_NUMBER):
            self.timers[thread_id] = {}

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

        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_address = (CLIENT_IP, CLIENT_DATA_PORT)
        # self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, CHUNK_SIZE)
        print(f"UDP data socket start, waiting for client...")

    def establish_connection(self):
        """
        交换 c-s 的基础信息, 包括

        - RTT
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
        创建 THREAD_NUMBER 个线程使用 data_socket 传输数据
        """

        # 计算每一个线程需要发送的文件大小, 如果不能整除的话采用四舍五入的方式
        thread_send_size = int(round(self.file_size / SERVER_SEND_THREAD_NUMBER))
        self.send_threads: list[threading.Thread] = []
        for thread_id in range(SERVER_SEND_THREAD_NUMBER - 1):
            thread = threading.Thread(target=self.read_and_send, args=(thread_id, thread_send_size))
            self.send_threads.append(thread)

        # 将剩余部分都放入最后一个线程发送
        bias = thread_send_size * SERVER_SEND_THREAD_NUMBER - self.file_size
        thread = threading.Thread(
            target=self.read_and_send,
            args=(
                SERVER_SEND_THREAD_NUMBER - 1,
                thread_send_size - bias,
            ),
        )
        self.send_threads.append(thread)

        for thread in self.send_threads:
            thread.start()

    def read_and_send(self, thread_id: int, thread_send_size: int):
        start_offset = thread_id * thread_send_size  # 起始偏移位置
        self.log(f"start sending thread {thread_id}")

        with open(self.file_path, "rb") as f:
            f.seek(start_offset)

            # 如果小于分块大小, 直接一次性发送过去
            if thread_send_size <= CHUNK_SIZE:
                data = f.read(thread_send_size)
                self.timers[thread_id][0] = self.get_time()
                self.data_socket.sendto(data, self.client_address)
                self.log(f"[{thread_id}] send data {len(data)}")
            else:
                # 按照分块大小发送 n 次
                n = thread_send_size // CHUNK_SIZE
                for sequence_number in range(n - 1):
                    data = f.read(CHUNK_SIZE)
                    header = struct.pack("!IId", thread_id, sequence_number, self.get_time())
                    full_message = header + data
                    self.timers[thread_id][sequence_number] = self.get_time()
                    self.data_socket.sendto(full_message, self.client_address)
                    self.log(f"[{thread_id}] send data {sequence_number}:{len(full_message)}")
                    self.package_sent_number += 1
                # 最后一次把 thread_send_size 剩余的部分都发过去
                # sequence_number = n - 1
                # data = f.read(thread_send_size - sequence_number * CHUNK_SIZE)
                # header = struct.pack("!IId", thread_id, sequence_number, self.get_time())
                # full_message = header + data
                # self.timers[thread_id][sequence_number] = self.get_time()
                # self.data_socket.sendto(data, self.client_address)
                # self.log(f"[{thread_id}] send data {sequence_number}")

    def receive_ack(self):
        self.receive_threads: List[threading.Thread] = []
        self.control_socket.settimeout(None)
        for thread_id in range(SERVER_ACK_HANDLE_THREAD_NUMBER):
            thread = threading.Thread(target=self.handle_ack, args=(thread_id, ))
            thread.daemon = True
            thread.start()
            self.receive_threads.append(thread)

    def handle_ack(self, thread_id):
        """
        处理来自 client 的 ack 数据包
        """
        while True:
            ack_data, _ = self.control_socket.recvfrom(1024)
            send_thread_id, sequence_number, timestamp = struct.unpack("!IId", ack_data[:16])
            self.log(f"[{thread_id}] receive {send_thread_id} {sequence_number}")
            self.ack_received_number += 1

    def close_socket(self):
        self.control_socket.close()
        self.data_socket.close()

    def log(self, info: str):
        sys.stderr.write(f"server: {info}\n")

    def show_statistical_info(self):
        self.log(f"send    {self.package_sent_number} packages")
        self.log(f"receive {self.ack_received_number} acks")

    def get_time(self):
        return time.time()


def main():
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt as e:
        print(e)
        server.show_statistical_info()
    finally:
        server.close_socket()
    print("over")


if __name__ == "__main__":
    main()
