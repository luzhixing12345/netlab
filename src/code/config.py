import gzip
import lzma
from enum import Enum
import re

CLIENT_IP = "202.100.10.2"  # 客户端 IP, 其实没有必要确定, 也不应该知道
SERVER_IP = "202.100.10.3"  # 服务端 IP
# SERVER_IP = "127.0.0.1"  # debug
SERVER_CONTROL_PORT = 8000  # 服务端端口
CLIENT_DATA_PORT = 8001
RTT_SEND_TIME = 5

FILE_PATH = "output.bin"
CHUNK_SIZE = 32 * 1024  # 32KB
SEND_THREAD_NUMBER = 8
RECEIVE_THREAD_NUMBER = 8

ENABLE_PRE_ZIP = False  # 采用预先压缩

# gzip: 更快的压缩速度
# lzma: 更小的压缩体积

ZIP_LIB = gzip  # 默认采用的压缩算法
# ZIP_LIB = lzma
ZIP_FILE_PATH = f"{FILE_PATH}.z"


class TCPstatus(Enum):
    CLOSED = "CLOSED"
    LISTENED = "LISTENED"
    SYN_SENT = "SYN_SENT"
    SYN_RCVD = "SYN_RCVD"
    ESTABLISHED = "ESTABLISHED"


# https://zhuanlan.zhihu.com/p/483856828
TCP_SYN_RETIRES = 6  # 最多重发 6 次
TCP_SYN_TIMEOUT = 1  # SYN 的超时时间, 每次超时后翻倍

SYN_PATTERN = re.compile(r"SYN (?P<syn_number>\d+) (?P<time>\d+\.\d+)")
SYN_ACK_PATTERN = re.compile(r"SYN ACK (?P<filesize>\d+)")
