import socket
import time
from config import *
import threading
from typing import List, Set, Tuple
import struct
import hashlib
import sys
from queue import Queue


class ClientInfo:
    package_received_number = 0  # 接收到的有效数据包的个数(不包含重复接收的数据包)
    package_duplicated_number = 0  # 重复接收的数据包的个数
    ack_sent_number = 0  # 发送的 ACK 个数
    write_data_number = 0

class Client:
    def __init__(self) -> None:
        self.info = ClientInfo()
        self.status = TCPstatus.CLOSED  # 客户端的状态, 仿照 TCP 三次握手
        self.init_socket()
        self.init_thread()

        self.file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        self.file_data_blocks: Set[Tuple[int, int]] = set()

    def run(self):
        self.establish_connection()

        for thread in self.write_threads:
            thread.join()

        for thread in self.receive_threads:
            thread.join()

    def init_socket(self):
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 设置接收缓冲区为最大
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, MAX_UDP_BUFFER_SIZE)
        # 服务端地址
        self.server_address = (SERVER_IP, SERVER_CONTROL_PORT)
        self.data_socket.bind((CLIENT_IP, CLIENT_DATA_PORT))

    def init_thread(self):
        """
        初始化所有接收线程
        """
        self.receive_threads: List[threading.Thread] = []  # 接收线程
        self.write_threads: List[threading.Thread] = []  # 写文件线程

        data_queue = Queue()

        for thread_id in range(CLIENT_RECEIVE_THREAD_NUMBER):
            thread = threading.Thread(
                target=self.receive_package,
                args=(
                    thread_id,
                    data_queue,
                ),
            )
            thread.daemon = True
            self.receive_threads.append(thread)

        for thread_id in range(CLIENT_WRITE_THEAD_NUMBER):
            thread = threading.Thread(
                target=self.write_data,
                args=(
                    thread_id,
                    data_queue,
                ),
            )
            thread.daemon = True
            self.write_threads.append(thread)

    def establish_connection(self):
        """
        仿照 TCP 三次握手, 服务端确定 RTT, 客户端确定文件大小
        """
        # 初次建立
        self.status = TCPstatus.CLOSED

        syn_retry_time = 0
        tcp_syn_timeout = TCP_SYN_TIMEOUT
        RTT = 0

        while syn_retry_time < TCP_SYN_RETIRES:
            # SYN 为客户端的发送时间戳
            # syn_data = struct.pack("!Q", int(time.time() * 1000))
            self.data_socket.settimeout(tcp_syn_timeout)
            start_time = self.get_time()
            syn_data = f"SYN {syn_retry_time} {start_time}"
            self.control_socket.sendto(syn_data.encode(), self.server_address)

            self.status = TCPstatus.SYN_SENT
            self.log("send SYN")
            try:
                syn_ack_data, _ = self.data_socket.recvfrom(1024)
                syn_ack_data = SYN_ACK_PATTERN.match(syn_ack_data.decode())
                end_time = self.get_time()
                RTT = end_time - start_time
                self.file_size = syn_ack_data.group("filesize")
                self.log(f"receive SYN ACK, file size = [{self.file_size}] rtt = [{RTT}]")
                self.create_empty_file()
                break
            except socket.timeout:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log("SYN ACK timeout, double")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

        self.status = TCPstatus.ESTABLISHED
        syn_retry_time = 0
        tcp_ack_timeout = RTT * 10
        self.receive_data()

        while syn_retry_time < TCP_SYN_RETIRES:
            # SYN 为客户端的发送时间戳
            syn_data = "ACK"
            self.control_socket.sendto(syn_data.encode(), self.server_address)
            self.log("send ACK")
            time.sleep(tcp_ack_timeout)
            if self.status == TCPstatus.RECEIVING_DATA:
                break
            else:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log("ACK timeout, double")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

    def create_empty_file(self):
        """
        创建一个大小为 filesize 的空文件, 以便后续的进程可以直接在对应位置写入
        """
        assert self.file_size != 0
        self.create_file_thread = threading.Thread(target=self.init_file, args=())
        self.create_file_thread.daemon = True
        self.create_file_thread.start()

    def init_file(self):
        with open(self.file_path, "wb") as file:
            # 将文件指针移动到指定大小
            file.seek(self.file_size - 1)
            # 写入一个空字节,这样文件就会扩展到指定大小
            file.write(b"\0")

    def receive_data(self):
        """
        可以开始接收数据
        """
        # 等待创建文件的进程结束
        self.create_file_thread.join()

        # 先启动写线程
        for thread in self.write_threads:
            thread.start()

        self.data_socket.settimeout(None)            
        for thread in self.receive_threads:
            thread.start()

    def receive_package(self, thread_id: int, data_queue: Queue):
        """
        从 data socket 接收数据, 从 control socket 发送 ACK, ACK 数据包格式如下

        1                          4                          8
        +--------------------------+--------------------------+
        |                          |                          |
        |       thread id          |      sequence number     |
        |                          |                          |
        +--------------------------+--------------------------+
        |                                                     |
        |                    receive time                     |
        |                                                     |
        +-----------------------------------------------------+
        """
        self.log(f"start listening thread")
        while True:
            package_data, _ = self.data_socket.recvfrom(CHUNK_SIZE * 2)
            self.status = TCPstatus.RECEIVING_DATA

            send_thread_id, sequence_number, start_offset = struct.unpack("!IIQ", package_data[:DATA_HEADER_SIZE])

            data_block_id = (send_thread_id, sequence_number)
            if data_block_id in self.file_data_blocks:
                # 已经接收过了, 这是因为ACK 数据包丢失重发的数据
                # ACK 丢包说明网络环境可能不太好, 多次重发 ACK 数据包通知 server 数据已到达
                for _ in range(MAX_ACK_RETRIES):
                    receive_time = self.get_time()
                    ack_header = struct.pack("!IId", send_thread_id, sequence_number, receive_time)
                    self.control_socket.sendto(ack_header, self.server_address)

                self.log(f"data already received, send {MAX_ACK_RETRIES} acks")
                self.info.package_duplicated_number += 1
            else:
                # 正常接收的数据
                self.file_data_blocks.add(data_block_id)

                # 先回复 ACK 包再写入
                receive_time = self.get_time()
                ack_header = struct.pack("!IId", send_thread_id, sequence_number, receive_time)
                self.control_socket.sendto(ack_header, self.server_address)

                data = package_data[DATA_HEADER_SIZE:]
                data_queue.put((start_offset, data))

                self.log(f"[{thread_id}] send ack")
                self.info.package_received_number += 1
                self.info.ack_sent_number += 1

    def write_data(self, thread_id: int, data_queue: Queue):
        """ """
        # 以覆盖的方式写入文件对应的位置
        while True:
            start_offset, data = data_queue.get()
            self.log(f'write {start_offset} {len(data)}')
            with open(self.file_path, "rb+") as f:
                f.seek(start_offset)
                f.write(data)
            self.info.write_data_number += 1

    def close_socket(self):
        # 关闭socket
        self.control_socket.close()
        self.data_socket.close()

    def log(self, info: str):
        sys.stderr.write(f"client: {info}\n")

    def show_statistical_info(self):
        self.log(f"receive packages: {self.info.package_received_number}")
        self.log(f'duplicate packages: {self.info.package_duplicated_number}')
        self.log(f"sent acks: {self.info.ack_sent_number}")
        self.log(f'write data: {self.info.write_data_number}')

    def get_time(self):
        return time.time()

    def calculate_md5(self, block_size=8192):
        md5_hash = hashlib.md5()
        with open(self.file_path, "rb") as file:
            for chunk in iter(lambda: file.read(block_size), b""):
                md5_hash.update(chunk)
        print(f"md5: {md5_hash.hexdigest()}")


def main():
    client = Client()
    try:
        client.run()
    except KeyboardInterrupt as e:
        print(e)
        client.show_statistical_info()
        client.calculate_md5()
    finally:
        client.close_socket()
    print("over")


if __name__ == "__main__":
    main()
