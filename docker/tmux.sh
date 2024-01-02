#!/bin/sh

# 创建一个新的tmux会话
tmux new-session -d -s mysession

# 创建上下分栏
# comment here
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

# comment here
tmux send-keys -t mysession:0.2 'export PS1="monitor:\w \$ "' C-m
tmux send-keys -t mysession:0.2 'cd' C-m
# 使用虚拟 python 环境
tmux send-keys -t mysession:0.2 '. bin/activate' C-m
tmux send-keys -t mysession:0.2 'clear' C-m

# 切换到 monitor 窗格
# tmux select-pane -t mysession:0.1
tmux select-pane -t mysession:0.2

# # 将tmux会话附加到当前终端
tmux attach-session -t mysession

