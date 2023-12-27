import socket
import time
from config import *
import threading
from typing import List, Set, Tuple
import struct
import sys

FILE_DATA = []


class Client:
    def __init__(self) -> None:
        self.status = TCPstatus.CLOSED  # 客户端的状态, 仿照 TCP 三次握手
        self.rtt = 0
        self.package_received_number = 0
        self.ack_sent_number = 0
        self.init_socket()
        self.init_thread()
        
        self.file_path = ZIP_FILE_PATH if ENABLE_PRE_ZIP else FILE_PATH
        self.file_data_blocks: Set[Tuple[int, int]] = set()

    def run(self):
        self.establish_connection()

        for thread in self.threads:
            thread.join()

    def init_socket(self):
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 服务端地址
        self.server_address = (SERVER_IP, SERVER_CONTROL_PORT)
        self.data_socket.bind((CLIENT_IP, CLIENT_DATA_PORT))

    def init_thread(self):
        """
        初始化所有接收线程
        """
        self.threads: List[threading.Thread] = []
        for thread_id in range(CLIENT_RECEIVE_THREAD_NUMBER):
            thread = threading.Thread(target=self.receive_package, args=(thread_id,))
            thread.daemon = True
            self.threads.append(thread)

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
            syn_data = f"SYN {syn_retry_time} {start_time}"
            self.control_socket.sendto(syn_data.encode(), self.server_address)

            self.status = TCPstatus.SYN_SENT
            self.log("send SYN")
            try:
                syn_ack_data, _ = self.data_socket.recvfrom(1024)
                syn_ack_data = SYN_ACK_PATTERN.match(syn_ack_data.decode())
                end_time = self.get_time()
                self.rtt = end_time - start_time
                self.file_size = syn_ack_data.group("filesize")
                self.log(f"receive SYN ACK, file size = [{self.file_size}] rtt = [{self.rtt}]")
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
        tcp_ack_timeout = self.rtt * 10
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
                self.rtt *= 2
                self.log("ACK timeout, double")

        if syn_retry_time >= TCP_SYN_RETIRES:
            self.log("fail to connect\n")
            self.close_socket()
            exit(1)

    def create_empty_file(self):
        '''
        创建一个大小为 filesize 的空文件, 以便后续的进程可以直接在对应位置写入
        '''
        
        
    def create_file_func(self):
        with open(self.file_path, 'wb') as file:
        # 将文件指针移动到指定大小
            file.seek(self.file_size - 1)
            # 写入一个空字节,这样文件就会扩展到指定大小
            file.write(b'\0')

    def receive_data(self):
        """
        可以开始接收数据
        """
        self.data_socket.settimeout(None)
        for thread in self.threads:
            thread.start()

    def receive_package(self, thread_id):
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
            package_data, _ = self.data_socket.recvfrom(CHUNK_SIZE + DATA_HEADER_SIZE)
            self.status = TCPstatus.RECEIVING_DATA

            send_thread_id, sequence_number, send_time, start_offset, block_size = struct.unpack(
                "!IIdQQ", package_data[:DATA_HEADER_SIZE]
            )
            self.log(f"{thread_id}: receive data {len(package_data)}")
            self.package_received_number += 1
            
            data_block_id = (send_thread_id, sequence_number)
            if data_block_id in self.file_data_blocks:
                # 已经接收过了, 这是因为 ACK 数据包丢失重发的数据
                self.log(f'already received')
            else:
                data = package_data[DATA_HEADER_SIZE:]
                with open(self.file_path, 'wb') as f:
                    ...
            receive_time = self.get_time()
            ack_header = struct.pack("!IId", send_thread_id, sequence_number, receive_time)
            self.control_socket.sendto(ack_header, self.server_address)
            self.log(f"[{thread_id}] send ack {send_thread_id} {sequence_number} {send_time}")
            self.ack_sent_number += 1

    def close_socket(self):
        # 关闭socket
        self.control_socket.close()
        self.data_socket.close()

    def log(self, info: str):
        sys.stderr.write(f"client: {info}\n")

    def show_statistical_info(self):
        self.log(f"receive {self.package_received_number} packages")
        self.log(f"sent    {self.ack_sent_number} acks")

    def get_time(self):
        return time.time()


def main():
    client = Client()
    try:
        client.run()
    except KeyboardInterrupt as e:
        print(e)
        client.show_statistical_info()
    finally:
        client.close_socket()
    print("over")


if __name__ == "__main__":
    main()
