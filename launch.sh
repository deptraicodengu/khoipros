#!/usr/bin/env bash
# khoiprOS
#   launch.sh         bật, hoặc ẩn/hiện nếu đang chạy (gắn vào Super+O)
#   launch.sh start   chỉ bật nếu chưa chạy (dùng khi đăng nhập)
#   launch.sh lock    khoá màn hình có hiệu ứng (gắn vào Super+L)
#   launch.sh wall    mở bảng chọn hình nền (gắn vào Super+W)
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PID=$(pgrep -f "python3 $DIR/main.py" | head -n1)
if [ "$1" = "lock" ]; then
    if [ -n "$PID" ]; then kill -HUP "$PID"
    elif [ -f "$DIR/hyprlock.conf" ]; then hyprlock -c "$DIR/hyprlock.conf" || hyprlock
    else hyprlock; fi
    exit 0
fi
if [ "$1" = "wall" ]; then
    [ -n "$PID" ] && kill -WINCH "$PID"
    exit 0
fi
if [ -n "$PID" ]; then
    [ "$1" = "start" ] && exit 0
    kill -SIGUSR1 "$PID"        # đang chạy → ẩn/hiện
else
    export GDK_BACKEND=wayland
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    nohup python3 "$DIR/main.py" >>"/tmp/kkkhoishell.log" 2>&1 &
fi
