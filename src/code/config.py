import gzip
import lzma
from enum import Enum
import re

LOG_MODE = 'DEBUG'
LOG_MODE = 'INFO'

CLIENT_IP = "202.100.10.2"  # 客户端 IP, 其实没有必要确定, 也不应该知道
SERVER_IP = "202.100.10.3"  # 服务端 IP
# SERVER_IP = "127.0.0.1"  # debug
SERVER_CONTROL_PORT = 8000  # 服务端端口
CLIENT_DATA_PORT = 8001 # 客户端端口
RTT_SEND_TIME = 5 # 发送 RTT 的次数

ADJUST_RTT_THRESHOLD = 5 # 超过 RTT 的次数阈值
MAX_RTT_MULTIPLIER = 10 # 超过 RTT 的时间倍数, 确定丢包后重传

FILE_PATH = "output.bin" # 文件路径
CHUNK_SIZE = 1 * 1024  # 32KB
MAX_UDP_BUFFER_SIZE = 425984

DEFAULT_THREAD_NUMBER = 16
SERVER_SEND_THREAD_NUMBER = DEFAULT_THREAD_NUMBER
SERVER_ACK_HANDLE_THREAD_NUMBER = DEFAULT_THREAD_NUMBER
SERVER_TIMEOUT_RESEND_THREAD_NUMBER = DEFAULT_THREAD_NUMBER // 4
CLIENT_RECEIVE_THREAD_NUMBER = 8
CLIENT_WRITE_THEAD_NUMBER = 1

# 见 server.py send_package 数据包头部格式
DATA_HEADER_SIZE = 8

ENABLE_PRE_ZIP = False  # 采用预先压缩
STATISTIC_INTERVAL = 2 # 统计信息的输出间隔
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

# 三次握手的消息格式
SYN_PATTERN = re.compile(r"SYN (?P<syn_number>\d+) (?P<time>\d+\.\d+)")
SYN_ACK_PATTERN = re.compile(r"SYN ACK (?P<filesize>\d+)")
# SYN_ACK_PATTERN = 'ACK'

# 四次挥手的消息格式

# 当客户端发送的 ACK 服务器没有收到,重发的数据包过来之后客户端多次重发 ACK 的数量
MAX_ACK_RETRIES = 2
