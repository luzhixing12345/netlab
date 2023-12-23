import gzip
import lzma

CLIENT_IP = "202.100.10.2"  # 客户端 IP, 其实没有必要确定, 也不应该知道
SERVER_IP = "202.100.10.3"  # 服务端 IP
# SERVER_IP = "127.0.0.1"  # debug
SERVER_CONTROL_PORT = 8000  # 服务端端口
SERVER_DATA_PORT = 8001
RTT_SEND_TIME = 500

FILE_PATH = "output.bin"
CHUNK_SIZE = 32 * 1024  # 32KB
THREAD_NUMBER = 8

ENABLE_PRE_ZIP = False  # 采用预先压缩

# gzip: 更快的压缩速度
# lzma: 更小的压缩体积

ZIP_LIB = gzip  # 默认采用的压缩算法
# ZIP_LIB = lzma
ZIP_FILE_PATH = f'{FILE_PATH}.z'