apk add openssh
mkdir -p /etc/ssh
ssh-keygen -A
/usr/sbin/sshd
ssh-keygen -t rsa -C "luzhixing12345@163.com"

cat ~/.ssh/id_rsa.pub
vi ~/.ssh/authorized_keys

apk add python3-dev