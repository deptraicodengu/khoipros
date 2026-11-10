#!/usr/bin/env bash
# Gỡ khoiprOS. Cài đặt của bạn (settings.json) được giữ lại trừ khi thêm --all
DEST="${KHOIPROS_DIR:-$HOME/.config/kkkhoishell}"
pkill -f "python3 $DEST/main.py" 2>/dev/null
rm -f "$DEST/main.py" "$DEST/index.html" "$DEST/launch.sh" "$DEST/three.min.js" "$DEST/hyprlock.conf" "$DEST/wallpicker.qml" "$DEST/lock-planet.png" "$DEST"/*.bak
H="$HOME/.config/hypr"
for F in "$H/hyprland.conf" "$H/hyprland.lua"; do
    [ -f "$F" ] && sed -i '/^# khoiprOS$/d; /^-- khoiprOS$/d; /kkkhoishell\/launch.sh/d; /khoipros_colors/d' "$F"
done
rm -f "$H/khoipros_colors.lua"
[ "$1" = "--all" ] && rm -rf "$DEST"
rm -f "$DEST/uninstall.sh"
echo "Đã gỡ khoiprOS (phím tắt và tự chạy cũng đã bỏ)."
