import socket


def main():
    # 创建UDP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 绑定到特定的IP地址和端口
    server_address = ("localhost", 12345)
    server_socket.bind(server_address)

    print(f"UDP 服务端启动,监听 {server_address}")

    try:
        while True:
            # 接收数据
            data, client_address = server_socket.recvfrom(1024)
            print(f"接收到来自 {client_address} 的数据: {data.decode()}")

            # 发送响应
            response = "Hello, client!"
            server_socket.sendto(response.encode(), client_address)

    except KeyboardInterrupt:
        # 捕获Ctrl+C中断信号
        print("接收到中断信号,关闭服务端.")

    finally:
        # 关闭socket
        server_socket.close()


if __name__ == "__main__":
    main()
