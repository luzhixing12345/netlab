#coding=utf8
import paramiko,getpass
import argparse
import os
from scp import SCPClient
import threading
import prettytable as pt
import time
import json

client_ssh = ''
server_ssh = ''
client_scp = '' 
server_scp = ''
tb = pt.PrettyTable()
tb.field_names = ["测试文件大小(G)", "耗时(s)", "server端文件md5", "client端文件md5", "md5检测"]

def ssh_connect(host_ip, user_name, password):
    '''
    host_ip = '192.168.0.150'
    user_name = 'root'
    host_port ='22'

    # 待执行的命令
    sed_command = "sed -i 's/123/abc/g' /root/test/test.txt"
    ls_command = "ls /root/test/"

    # 注意:依次执行多条命令时,命令之间用分号隔开
    command = sed_command+";"+ls_command
    '''
    # SSH远程连接
    ssh = paramiko.SSHClient()   
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  #AutoAddPolicy表示自动在对方主机保存下本机的秘钥
    ssh.connect(host_ip, '22000', user_name, password)
    
    return ssh

def exec_command(ssh_connection, command):
    # 执行命令并获取执行结果
    stdin, stdout, stderr = ssh_connection.exec_command(command)
    out = stdout.read()
    err = stderr.read()
    return (out, err)


def close_ssh(ssh_connection):
    ssh_connection.close()


# 执行一次测试(将该目录下文件夹的个数作为测试的数目,文件夹的名字作为一个组的标识名称)
def one_test():

    # 读出run.json中的文件信息/执行命令等
    global client_ssh, server_ssh, client_scp, server_scp, tb, config
    # upload student's code to the client and server
    print("Running: ")

    
    # 利用scp将client.py等三个文件分别传输到对应服务器上
    try:
        client_scp.put(config['client_file'], './client.py')
        server_scp.put("./chunk_generator.py", "~/chunk_generator.py")
        server_scp.put(config['server_file'], './server.py')
    except FileNotFoundError as e:
        print("Cannot find the file" + e)
    else:
        print("File upload successfully")

    # 在服务器端运行chunk_generator.py 产生一个 0.2G大小的文件
    exec_command(server_ssh, "python3 chunk_generator.py "+ config['generate_type'] + " -s " + config['size'])
    print("Generate bins successfully")
    # 启用一个线程,在server端运行server.py进行监听
    def server_run():
        server_out = exec_command(server_ssh, config['server_exec_cmd'])
    server_thread = threading.Thread(target=server_run)
    server_thread.start()
    
    
    # 在client端运行client.py连接server传输文件
    time.sleep(1)
    start = time.perf_counter()
    client_exec_result = exec_command(client_ssh, config['client_exec_cmd'])
    end = time.perf_counter()
    
    # 计算传输时间
    time_spent = end - start

    # 如果client连接server失败,则报错退出
    if client_exec_result[1] != b'':
        print("Connection error:")
        print(client_exec_result)
        exec_command(server_ssh, "pkill python3")
        exec_command(client_ssh, "pkill python3")
        print("Failed")
        exit(0)
    print("Consumed time: ", time_spent)

    # 计算服务器和客户端的md5值
    file_md5_on_client = exec_command(client_ssh, "md5sum ~/output.bin")[0].split()[0]
    file_md5_on_server = exec_command(server_ssh, "md5sum ~/output.bin")[0].split()[0]

    # 利用prettytable记录结果
    tb.add_row([config['size'], str(time_spent), file_md5_on_server, file_md5_on_client, file_md5_on_server == file_md5_on_client])
    print(tb)
    f = open("./result.txt", 'w')
    f.write(str(tb))
    f.close()


def main():
    global client_ssh, server_ssh, client_scp, server_scp, config
    config = json.load(open('run.json', 'r'))
    client_ssh = ssh_connect('202.100.10.2', 'st', '123')
    server_ssh = ssh_connect('202.100.10.3', 'st', '123')

    client_scp = SCPClient(client_ssh.get_transport(),socket_timeout=15.0)
    server_scp = SCPClient(server_ssh.get_transport(),socket_timeout=15.0)
    exec_command(server_ssh, "pkill python3")
    exec_command(client_ssh, "pkill python3")

    one_test()

    exec_command(server_ssh, "pkill python3")
    exec_command(client_ssh, "pkill python3")
    exec_command(server_ssh, "rm ~/chunk_generator.py")
    exec_command(server_ssh, "rm ~/server.py")
    exec_command(server_ssh, "rm ~/output.bin")
    exec_command(client_ssh, "rm ~/client.py")
    exec_command(client_ssh, "rm ~/output.bin")


if __name__ == '__main__':
    # parser = argparse.ArgumentParser('Automanager')
    # parser.add_argument('--client_ip', type = str, required = True)
    # parser.add_argument('--client_password', type = str, required = True)
    # parser.add_argument('--client_username', type = str, required = True)
    # parser.add_argument('--client_file', type=str, required=True)
    # parser.add_argument('--server_ip', type = str, required = True)
    # parser.add_argument('--server_port', type=str, required=True)
    # parser.add_argument('--server_password', type = str, required = True)
    # parser.add_argument('--server_username', type = str, required = True)
    # parser.add_argument('--server_file', type=str, required=True)
    # parser.add_argument('--generate_type', type = str, default=False, choices = ['generate_same_char', 'generate_random_char'])
    # parser.add_argument('-s','--size', help = 'type in 1 for 1G', type = float, default=2)
    # args = parser.parse_args()
    # main(args.client_ip, args.client_username, args.client_password, args.server_ip, args.server_port, args.server_username, args.server_password, args.client_file, args.server_file, args.generate_type, args.size)
    main()
    # main('192.168.43.131', 'jhon', '123456', '192.168.43.130', '49999', 'jhon', '123456', './demos/baseline/client.py', './demos/baseline/server.py', 'generate_random_char', 1)