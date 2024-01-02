import socket
import time
import threading
from typing import List, Set
import struct
import hashlib
from queue import Queue

import gzip
import lzma
from enum import Enum
import re

LOG_MODE = "DEBUG"
LOG_MODE = "INFO"

CLIENT_IP = "202.100.10.2"  # 客户端 IP, 其实没有必要确定, 也不应该知道
SERVER_IP = "202.100.10.3"  # 服务端 IP

# CLIENT_IP = "192.168.232.137"  # 客户端 IP, 其实没有必要确定, 也不应该知道
# SERVER_IP = "192.168.232.136"  # 服务端 IP

# CLIENT_IP = "127.0.0.1"  # only for debug
# SERVER_IP = "127.0.0.1"  # only for debug

SERVER_CONTROL_PORT = 8000  # 服务端端口
CLIENT_DATA_PORT = 8001  # 客户端端口

ADJUST_RTT_THRESHOLD = 1000  # 调整 RTT 的次数阈值
MAX_RTT_MULTIPLIER = 10  # 超过 RTT 的时间倍数, 确定丢包后重传

FILE_PATH = "output.bin"  # 文件路径
CHUNK_SIZE = 1 * 1024  # 32KB
MAX_UDP_BUFFER_SIZE = 425984

DEFAULT_THREAD_NUMBER = 1024
SERVER_SEND_THREAD_NUMBER = DEFAULT_THREAD_NUMBER  # 服务端发送线程数
SERVER_TIMEOUT_RESEND_THREAD_NUMBER = DEFAULT_THREAD_NUMBER // 16  # 服务端重发线程数
CLIENT_RECEIVE_THREAD_NUMBER = SERVER_SEND_THREAD_NUMBER + SERVER_TIMEOUT_RESEND_THREAD_NUMBER # 客户端接收线程数
SERVER_ACK_HANDLE_THREAD_NUMBER = CLIENT_RECEIVE_THREAD_NUMBER # 服务端 ACK 处理线程数

# 见 server.py send_package 数据包头部格式
DATA_HEADER_SIZE = 8

ENABLE_PRE_ZIP = False  # 采用预先压缩
STATISTIC_INTERVAL = 2  # 统计信息的输出间隔
# gzip: 更快的压缩速度
# lzma: 更小的压缩体积

ZIP_LIB = gzip  # 默认采用的压缩算法
# ZIP_LIB = lzma
ZIP_FILE_PATH = f"{FILE_PATH}.z"


class TCPstatus(Enum):
    CLOSED = "CLOSED"
    LISTEN = "LISTEN"
    SYN_SENT = "SYN_SENT"
    SYN_RCVD = "SYN_RCVD"
    ESTABLISHED = "ESTABLISHED"

    # 新增的一个状态
    RECEIVING_DATA = "RECEIVING_DATA"


# https://zhuanlan.zhihu.com/p/483856828
TCP_SYN_RETIRES = 6  # 最多重发 6 次
TCP_SYN_TIMEOUT = 1  # SYN 的超时时间, 每次超时后翻倍

TCP_FIN_RETIRES = 6  # 最多重发 6 次

SYN_ACK_PATTERN = re.compile(r"SYN ACK (?P<max_package_count>\d+)")

# 当客户端发送的 ACK 服务器没有收到,重发的数据包过来之后客户端多次重发 ACK 的数量
MAX_ACK_RETRIES = 2


class ClientInfo:
    package_received_count = 0  # 接收到的有效数据包的个数(不包含重复接收的数据包)
    package_duplicated_count = 0  # 重复接收的数据包的个数
    ack_sent_count = 0  # 发送的 ACK 个数


class Client:
    def __init__(self) -> None:
        self.info = ClientInfo()
        self.status = TCPstatus.CLOSED  # 客户端的状态, 仿照 TCP 三次握手
        self.init_socket()
        self.init_thread()

        self.file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        self.block_pos_set: Set[int] = set()
        # self.max_package_count = 0  # 可以通过 file_size 和配置信息计算出来一共需要多少数据包

    def run(self):
        self.establish_connection()

        # for thread in self.write_threads:
        #     thread.join()

        # for thread in self.receive_threads:
        #     thread.join()
        # self.log('finish transport')
        self.finish_event.wait()
        self.write_data()
        self.statistic_thread.join()
        self.close_connection()
        self.log(f"total time = {self.total_time}")

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
        self.lock = threading.Lock()
        self.receive_threads: List[threading.Thread] = []  # 接收线程
        # 统计信息的线程, 每隔2秒更新一次
        self.statistic_thread = threading.Thread(target=self.display_statistic, args=())
        self.statistic_thread.daemon = True

        for thread_id in range(CLIENT_RECEIVE_THREAD_NUMBER):
            thread = threading.Thread(
                target=self.receive_package,
                args=(thread_id,),
            )
            thread.daemon = True
            self.receive_threads.append(thread)

        # 结束事件
        self.finish_event = threading.Event()

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
            self.control_socket.sendto(b"SYN", self.server_address)

            self.status = TCPstatus.SYN_SENT
            self.log("send SYN")
            try:
                syn_ack_data, _ = self.data_socket.recvfrom(1024)
                try:
                    syn_ack_data = SYN_ACK_PATTERN.match(syn_ack_data.decode())
                    self.max_package_count = int(syn_ack_data.group("max_package_count"))
                    self.log(f"receive SYN ACK")
                    break
                except:
                    self.log("error SYN ACK type! should be SYN ACK <max_package_count>")

            except socket.timeout:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_syn_timeout *= 2
                self.log(f"SYN ACK timeout, double -> {tcp_syn_timeout}")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

        self.status = TCPstatus.ESTABLISHED
        syn_retry_time = 0
        tcp_ack_timeout = TCP_SYN_TIMEOUT
        self.receive_data()

        while syn_retry_time < TCP_SYN_RETIRES:
            # SYN 为客户端的发送时间戳
            syn_data = "ACK"
            self.control_socket.sendto(syn_data.encode(), self.server_address)
            self.log("send ACK")
            time.sleep(tcp_ack_timeout)
            if self.status == TCPstatus.RECEIVING_DATA:
                self.log("successfully build connection")
                break
            else:
                # 如果超时, 超时时间翻倍, 重新设置
                syn_retry_time += 1
                tcp_ack_timeout *= 2
                self.log(f"ACK timeout, double -> {tcp_ack_timeout}")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

    def receive_data(self):
        """
        可以开始接收数据
        """
        self.file_data = []

        # 开始计时
        self.start_time = self.get_time()
        self.data_socket.settimeout(None)
        for thread in self.receive_threads:
            thread.start()

        # 启动统计线程
        self.statistic_thread.start()

    def receive_package(self, thread_id: int):
        """
        从 data socket 接收数据, 从 control socket 发送 ACK, ACK 数据包格式如下

        1                          4                          8
        +-----------------------------------------------------+
        |                                                     |
        |                      seek pos                       |
        |                                                     |
        +-----------------------------------------------------+
        """
        self.debug(f"start listening thread")
        while True:
            package_data, _ = self.data_socket.recvfrom(CHUNK_SIZE * 2 + DATA_HEADER_SIZE)
            self.status = TCPstatus.RECEIVING_DATA
            self.debug("receive data")

            seek_pos = struct.unpack("!Q", package_data[:DATA_HEADER_SIZE])[0]

            # block_pos_set bushi
            with self.lock:
                is_duplicate_package = seek_pos in self.block_pos_set
            if is_duplicate_package:
                # 已经接收过了, 这是因为 ACK 数据包丢失重发的数据
                # ACK 丢包说明网络环境可能不太好, 多次重发 ACK 数据包通知 server 数据已到达
                for _ in range(MAX_ACK_RETRIES):
                    ack_header = struct.pack("!Q", seek_pos)
                    self.control_socket.sendto(ack_header, self.server_address)

                self.debug(f"data already received, send {MAX_ACK_RETRIES} acks")
                self.info.package_duplicated_count += 1
                self.info.ack_sent_count += MAX_ACK_RETRIES
            else:
                # 正常接收的数据
                with self.lock:
                    self.block_pos_set.add(seek_pos)

                # 先回复 ACK 包再写入
                ack_header = struct.pack("!Q", seek_pos)
                self.control_socket.sendto(ack_header, self.server_address)

                data = package_data[DATA_HEADER_SIZE:]
                self.file_data.append((seek_pos, data))

                self.debug(f"[{thread_id}] send ack")
                self.info.package_received_count += 1
                self.info.ack_sent_count += 1

    def write_data(self):
        """
        对 file_data 按照 seek_pos 进行排序, 依次写入
        """
        self.log(f"start writing data to {self.file_path}")
        if len(self.file_data) > self.max_package_count:
            self.log("error!")
            self.file_data = list(set(self.file_data))

        self.file_data.sort(key=lambda x: x[0])
        with open(self.file_path, "wb") as f:
            for _, data in self.file_data:
                f.write(data)

        self.log(f"finish writing data to {self.file_path}")

    def display_statistic(self):
        while True:
            time.sleep(STATISTIC_INTERVAL)
            self.log("-" * 20)
            self.show_statistical_info()
            self.log("-" * 20)

            if self.info.package_received_count >= self.max_package_count:
                self.log("all data received")
                self.total_time = self.get_time() - self.start_time
                self.finish_event.set()
                break

    def close_connection(self):
        """
        通知 server 已经收到所有数据, 停止发送

        这里简化处理, 直接发送 FIN 包, 发完后直接关闭 socket, 这样 server 收到 FIN 包后直接关闭 socket 即可
        """
        for _ in range(TCP_FIN_RETIRES):
            self.control_socket.sendto(b"FIN", self.server_address)

        # 如果启用了压缩, 进行解压缩
        if ENABLE_PRE_ZIP:
            self.log("decompressing...")
            start_time = self.get_time()
            with ZIP_LIB.open(self.file_path, "rb") as f_in:
                with open(FILE_PATH, "wb") as f_out:
                    f_out.writelines(f_in)
            end_time = self.get_time()
            self.log(f"decompressing time: {end_time - start_time:.2f}s")

    def close_socket(self):
        # 关闭socket
        self.control_socket.close()
        self.data_socket.close()

    def debug(self, info: str):
        if LOG_MODE == "DEBUG":
            print(f"client: {info}")

    def log(self, info: str):
        print(f"client: {info}")

    def show_statistical_info(self):
        self.log(
            f"receive packages: {self.info.package_received_count}/{self.max_package_count} [{self.info.package_received_count / self.max_package_count * 100:.2f}%]"
        )
        self.log(f"duplicate packages: {self.info.package_duplicated_count}")
        self.log(f"sent acks: {self.info.ack_sent_count}")
        self.log(f"total time: {self.get_time() - self.start_time:.2f}s")

    def get_time(self):
        return time.time()

    def calculate_md5(self, block_size=8192):
        self.log("calculating md5...")
        md5_hash = hashlib.md5()
        with open(self.file_path, "rb") as file:
            for chunk in iter(lambda: file.read(block_size), b""):
                md5_hash.update(chunk)
        self.log(f"md5: {md5_hash.hexdigest()}")


def main():
    client = Client()
    try:
        client.run()
        # client.calculate_md5()
    except KeyboardInterrupt as e:
        print(e)
    finally:
        # client.show_statistical_info()
        client.close_socket()
    print("over")


if __name__ == "__main__":
    main()
