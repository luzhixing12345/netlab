import socket
import os
import threading
import time
from config import *
import struct
import sys


def read_and_send(socket_conn: socket.socket, file_path: str, thread_id: int, thread_send_size: int):
    start_offset = thread_id * thread_send_size  # 起始偏移位置
    with open(file_path, "rb") as f:
        f.seek(start_offset)

        # 如果小于分块大小, 直接一次性发送过去
        if thread_send_size <= CHUNK_SIZE:
            data = f.read(thread_send_size)
            socket_conn.send(data)
        else:
            # 按照分块大小发送 n 次
            n = thread_send_size // CHUNK_SIZE
            for sequence_number in range(n - 1):
                data = str(f.read(CHUNK_SIZE))
                header = struct.pack("!IIQ", thread_id, sequence_number, int(time.time() * 1000))
                full_message = header + data.encode("utf-8")
                socket_conn.send(full_message)
            # 最后一次把 thread_send_size 剩余的部分都发过去
            data = str(f.read(thread_send_size - (n - 1) * CHUNK_SIZE))
            header = struct.pack("!IIQ", thread_id, sequence_number, int(time.time() * 1000))
            full_message = header + data.encode("utf-8")
            socket_conn.send(data)


class Server:
    def __init__(self) -> None:
        self.control_socket: socket.socket
        self.client_address: socket._RetAddress
        self.data_socket: socket.socket
        self.client_data_address: socket._RetAddress
        self.rtt = 0
        self.init_socket()

        self.establish_connection()
        # self.prepare_send_threads()

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

        self.file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        self.file_size = os.path.getsize(self.file_path)

    def prepare_send_threads(self):
        """
        创建 THREAD_NUMBER 个线程使用 data_socket 传输数据
        """

        # 计算每一个线程需要发送的文件大小, 如果不能整除的话采用四舍五入的方式
        thread_send_size = int(round(self.file_size / SEND_THREAD_NUMBER))
        self.threads = []
        for thread_id in range(SEND_THREAD_NUMBER - 1):
            thread = threading.Thread(
                target=read_and_send, args=(self.data_socket, self.file_path, thread_id, thread_send_size)
            )
            self.threads.append(thread)

        # 将剩余部分都放入最后一个线程发送
        bias = thread_send_size * SEND_THREAD_NUMBER - self.file_size
        thread = threading.Thread(
            target=read_and_send,
            args=(
                self.data_socket,
                self.file_path,
                SEND_THREAD_NUMBER - 1,
                thread_send_size - bias,
                CHUNK_SIZE,
            ),
        )
        self.threads.append(thread)

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

        syn_ack_data = f"SYN ACK {self.file_size}"
        self.data_socket.sendto(syn_ack_data.encode(), self.client_address)
        self.log("send syn ack")

        syn_retry_time = 0
        tcp_syn_timeout = TCP_SYN_TIMEOUT

        while syn_retry_time < TCP_SYN_RETIRES:
            self.control_socket.settimeout(tcp_syn_timeout)
            try:
                ack_data, _ = self.control_socket.recvfrom(1024)
                self.log("receive ACK")
                self.data_socket.sendto(b'hello client', self.client_address)
                break
            except socket.timeout:
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log("timeout, double")
                


    def run(self):
        """ """

    def close_socket(self):
        self.control_socket.close()
        self.data_socket.close()

    def log(self, info: str):
        sys.stderr.write(f"server: {info}\n")

    def get_time(self):
        return time.time()


def main():
    server = Server()
    server.close_socket()


if __name__ == "__main__":
    main()
