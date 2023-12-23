
# wsl2 内核重编译

在绝大多数的 Linux 发行版中都可以直接使用 tc, 但是在 WSL2 中执行会报错

```bash
# 报错 1
Error: Specified qdisc kind is unknown.
# 报错 2
RTNETLINK answers :No such file or directory error
```

原因是 tc 需要使用 netem, netem是linux内核提供的Network emulation服务,可以用来模拟广域网下的延迟/丢包/重复/损坏和乱序等问题, 2.6版本后的大多数 linux 发行版都已经在内核中启用了netem, **但 WSL2 的 Linux Kernel 没有**

需要在编译时启用 `CONFIG_NET_EMATCH` (即Network emulator), 并安装网卡驱动 `sch_netem`, WSL2 的默认配置 [config-wsl](https://github.com/microsoft/WSL2-Linux-Kernel/blob/860d9514d04e5ec0c759decde7d4591b15dfcef1/Microsoft/config-wsl) 未开启此选项

我们可以通过如下命令查看

```bash
$ zcat /proc/config.gz | grep NET_EM
# CONFIG_NET_EMATCH is not set
```

WSL2 社区中有关于该问题的讨论: [WSL2 seems not support traffic control by tc qdisc](https://github.com/microsoft/WSL/issues/6065), 最后解决办法是按照 [iproute2 Linux 配置选项](https://tldp.org/HOWTO/html_single/Traffic-Control-HOWTO/#s-kernel) 去修改内核编译选项并重新编译 WSL2 内核

> 暂时没有官方支持的 config, 只有手动修改

## WSL2 Linux Kernel 内核编译 & 安装

```bash
git clone https://github.com/microsoft/WSL2-Linux-Kernel.git
cd WSL2-Linux-Kernel
```

安装依赖

```bash
sudo apt install build-essential flex bison dwarves libssl-dev libelf-dev
```

接着您可以按照 iproute2 推荐的配置去修改 [Linux 配置选项](https://tldp.org/HOWTO/html_single/Traffic-Control-HOWTO/#s-kernel), 或者在这里下载笔者修改后的 [config-wsl-net](https://github.com/luzhixing12345/netlab/blob/main/config-wsl-net)

```bash
wget https://raw.githubusercontent.com/luzhixing12345/netlab/main/config-wsl-net
```

编译

```bash
# 假设在根目录下下载的 config-wsl-net 配置文件
make KCONFIG_CONFIG=config-wsl-net -j`nproc`
make KCONFIG_CONFIG=config-wsl-net -j`nproc` modules
sudo make KCONFIG_CONFIG=config-wsl-net -j`nproc` modules_install
sudo make KCONFIG_CONFIG=config-wsl-net -j`nproc` install
```

编译得到 `arch/x86/boot/bzImage`, 将其移动到 C 盘, 假设用户名为 `luzhi`, 读者请使用自己的 Windows 用户名

```bash
cp arch/x86/boot/bzImage /mnt/c/Users/luzhi/
```

修改 .wsl_config 的 kernel 位置

```bash
vim /mnt/c/Users/luzhi/.wslconfig
```

```txt
[wsl2]
kernel=C:\\Users\\luzhi\\bzImage
```

重启即可完成更新

```bash
wsl --shutdown
wsl
```

```bash
(base) kamilu@LZX:~$ uname -a
Linux LZX 5.15.137.3-microsoft-standard-WSL2+ #3 SMP Sat Dec 23 19:01:04 CST 2023 x86_64 x86_64 x86_64 GNU/Linux
```

## 测试 tc

编译时驱动以 module 形式安装, 需要手动加载到内核中执行

```bash
sudo modprobe sch_netem
```

使用 tc 不再报错即说明成功

```bash
sudo tc qdisc add dev eth0 root netem delay 100ms 10ms
```

可以 ping 一下 "www.baidu.com" 发现添加 tc 延迟规则之后的时长增加了 100 ms 左右

![20231223191239](https://raw.githubusercontent.com/learner-lu/picbed/master/20231223191239.png)

最后关闭规则即可

```bash
sudo tc qdisc del dev eth0 root netem
```

## 参考

- [WSL2 - qdisc netem 支持](https://learn.microsoft.com/en-us/answers/questions/48142/wsl2-qdisc-netem-support)
- [WSL2 seems not support traffic control by tc qdisc](https://github.com/microsoft/WSL/issues/6065)
- [iproute2 Linux 配置选项](https://tldp.org/HOWTO/html_single/Traffic-Control-HOWTO/#s-kernel)
- [recompile wsl2 kernel, add modules](https://gist.github.com/charlie-x/96a92aaaa04346bdf1fb4c3621f3e392)