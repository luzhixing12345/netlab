
# docker-container-build

在 docker/ 下执行 `make build`, 可以根据 `docker-compose.yml` 构建默认的网络, 其利用 alpine 镜像分别构建了三个容器 monitor/server/client, 如下所示

> [docker-compose.yml](https://github.com/luzhixing12345/netlab/blob/main/docker/docker-compose.yml)

![20231223095601](https://raw.githubusercontent.com/learner-lu/picbed/master/20231223095601.png)

三个容器对应分配一个 cs_network 网络下的 C 类地址静态 IP, cs_network 是我们创建的一个 docker bridge 网络

> 在 Docker 中,bridge 是一种网络模式,它是 Docker 默认使用的网络模式.bridge 模式允许在 Docker 主机和容器之间创建一个虚拟的以太网桥,使得容器可以通过这个桥接口与主机及其他容器进行通信

重启容器之后就可以分别进入三个容器

```bash
docker exec -it monitor sh
docker exec -it server sh
docker exec -it client sh
```

## SSH

首先需要完成从 monitor 容器到 server/client 的 SSH 连接, 以便后续的操作

**在三个容器中都**使用 alpha 的 apk 安装 python3 和 SSH, 初始化 SSH 并启动后台守护进程

```bash
apk add python3
apk add openssh

mkdir -p /etc/ssh
ssh-keygen -A
/usr/sbin/sshd
```

在 monitor 容器中创建 SSH 密钥

```bash
ssh-keygen -t rsa -C "luzhixing12345@163.com"
```

> 邮箱地址你可以换成自己的, 不换也无所谓

公钥的默认保存地址是 ~/.ssh, 获取 monitor 的公钥

```bash
cat ~/.ssh/id_rsa.pub
```

在 server/client 中创建 `~/.ssh/authorized_keys` 实现 SSH 免密登录

```bash
mkdir ~/.ssh
vi ~/.ssh/authorized_keys
```

然后将之前的 monitor 的公钥复制进去即可

在 monitor 处使用 SSH 连接 server/client, 可以连通表明成功

```bash
# 连接 client
ssh root@202.100.10.2

# 连接 server
ssh root@202.100.10.3
```

手动输入 IP 地址有点麻烦, 可以再配置一下 SSH, 创建 `~/.ssh/config` 并将下面的配置复制进去

```txt
Host client
  HostName 202.100.10.2
  User root
  IdentityFile "~/.ssh/id_rsa"

Host server
  HostName 202.100.10.3
  User root
  IdentityFile "~/.ssh/id_rsa"
```

这样就可以更方便的连接了

```bash
# 连接 client
ssh client

# 连接 server
ssh server
```

## Tmux

在 monitor 中安装 tmux, 以便在同一个终端窗口中连接到不同的主机并执行对应的操作

```bash
apk add tmux
```

创建 `tmux.sh` 并保存下面的内容, 其中利用 tmux 构建三个窗口, 0 和 1 分别 SSH 连接到 client 和 server, 2 为本地 monitor, 稍微修改一下 PS1 以更好的区分, 最后将tmux会话附加到当前终端

```bash
#!/bin/sh

# 创建一个新的tmux会话
tmux new-session -d -s mysession

# 创建上下分栏
tmux split-window -v -t mysession:0.0

# 创建左右分栏
tmux split-window -h -t mysession:0.0

# 在新分栏中执行命令
tmux send-keys -t mysession:0.0 'ssh root@client' C-m
tmux send-keys -t mysession:0.0 'export PS1="client:\w \$ "' C-m
tmux send-keys -t mysession:0.0 'clear' C-m

tmux send-keys -t mysession:0.1 'ssh root@server' C-m
tmux send-keys -t mysession:0.1 'export PS1="server:\w \$ "' C-m
tmux send-keys -t mysession:0.1 'clear' C-m

tmux send-keys -t mysession:0.2 'export PS1="monitor:\w \$ "' C-m
tmux send-keys -t mysession:0.2 'clear' C-m


# 切换到第一个窗格
tmux select-pane -t mysession:0.2

# # 将tmux会话附加到当前终端
tmux attach-session -t mysession
```

修改 tmux.sh 添加可执行权限, 运行即可

```bash
chmod +x tmux.sh
./tmux.sh
```

![20231223103734](https://raw.githubusercontent.com/learner-lu/picbed/master/20231223103734.png)

使用 `ip a` 可以看到已经连接成功, 三个 IP

![20231223104304](https://raw.githubusercontent.com/learner-lu/picbed/master/20231223104304.png)

> 如果容器关闭之后需要手动执行一下 `/usr/sbin/sshd` 不然 SSH 连接会失败

可以在 monitor 中创建一个虚拟 Python 环境, 类似执行 GetScore.py 查看结果. 或者分别在 server 和 client 上执行对应的程序

## 检查内核配置

确保内核配置中启用了 NET_EM,可以通过查看 /boot/config-$(uname -r) 文件或 /proc/config.gz 文件来检查.使用以下命令

```bash
grep NET_EM /boot/config-$(uname -r)
```

## 打包上传和收尾工作

删除三个容器和网络在 docker/ 下执行如下指令即可

```bash
make clean
```

## 参考

- [两个奇技淫巧,将 Docker 镜像体积减小 99%](https://zhuanlan.zhihu.com/p/115845957)
- [docker network-multitool](https://hub.docker.com/r/praqma/network-multitool/)
- [docker技巧](https://47log.com/tag/docker/)
- [多机弱网络环境模拟](https://keyou.github.io/blog/2019/07/25/%E5%A4%9A%E6%9C%BA%E5%BC%B1%E7%BD%91%E7%BB%9C%E7%8E%AF%E5%A2%83%E6%A8%A1%E6%8B%9F/)
- [linux下使用tc和netem模拟网络异常(一)](https://www.cnblogs.com/little-monica/p/11459772.html)