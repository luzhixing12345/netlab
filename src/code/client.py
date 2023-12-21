
import socket
from config import SERVER_IP, SERVER_PORT


def main():    
    # 创建UDP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 服务端地址
    server_address = (SERVER_IP, SERVER_PORT)

    # 发送数据
    message = "Hello, server!"
    client_socket.sendto(message.encode(), server_address)

    # 接收响应
    data, server_address = client_socket.recvfrom(1024)
    print(f"从服务器收到响应: {data.decode()}")

    # 关闭socket
    client_socket.close()


if __name__ == "__main__":
    main()