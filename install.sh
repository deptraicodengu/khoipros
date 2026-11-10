#!/usr/bin/env bash
# Cài khoiprOS — một lệnh:
#   bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
# hoặc trong thư mục đã clone:  ./install.sh
# Đổi chỗ cài: KHOIPROS_DIR=/đường/dẫn
set -e
REPO="deptraicodengu/khoipros"
DEST="${KHOIPROS_DIR:-$HOME/.config/kkkhoishell}"
THREE_URL="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
L="$DEST/launch.sh"
ask() { local a; read -rp "$1 [Y/n] " a </dev/tty || a=y; [[ ! "$a" =~ ^[Nn] ]]; }

# ---------- 1. lấy mã nguồn (chạy từ thư mục clone, hoặc tự tải từ GitHub) ----------
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ ! -f "$SRC/main.py" ] || [ ! -f "$SRC/index.html" ]; then
    echo "==> Tải khoiprOS từ github.com/$REPO"
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP" --strip-components=1
    SRC="$TMP"
fi

# ---------- 2. gói cần thiết ----------
echo "==> Kiểm tra gói cần thiết"
miss=()
python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("GtkLayerShell","0.1")' 2>/dev/null || miss+=(python-gobject gtk3 gtk-layer-shell)
python3 -c 'import gi
try: gi.require_version("WebKit2","4.1")
except ValueError: gi.require_version("WebKit2","4.0")' 2>/dev/null || miss+=(webkit2gtk-4.1)
python3 -c 'import cairo' 2>/dev/null || miss+=(python-cairo)
for c in hyprlock playerctl cava quickshell; do command -v $c >/dev/null || miss+=($c); done
# đặt hình nền cần awww (tên mới của swww) hoặc swww
if ! { command -v awww-daemon || command -v swww-daemon; } >/dev/null 2>&1; then
    if command -v pacman >/dev/null && pacman -Si awww >/dev/null 2>&1; then miss+=(awww); else miss+=(swww); fi
fi
command -v hyprctl >/dev/null || echo "   ! Không thấy hyprctl — khoiprOS chỉ chạy trên Hyprland"
if [ ${#miss[@]} -gt 0 ]; then
    echo "   Thiếu: ${miss[*]}"
    if command -v pacman >/dev/null; then
        ask "   Cài bằng pacman ngay?" && sudo pacman -S --needed "${miss[@]}"
    else
        echo "   Hãy cài các gói trên bằng trình quản lý gói của bạn."
    fi
fi

# ---------- 3. chép file ----------
echo "==> Cài vào $DEST"
mkdir -p "$DEST"
[ -f "$DEST/main.py" ] && cp "$DEST/main.py" "$DEST/main.py.bak" && cp "$DEST/index.html" "$DEST/index.html.bak" 2>/dev/null || true
install -m 644 "$SRC/main.py" "$SRC/index.html" "$DEST/"
[ -f "$SRC/wallpicker.qml" ] && install -m 644 "$SRC/wallpicker.qml" "$DEST/"
install -m 755 "$SRC/launch.sh" "$SRC/uninstall.sh" "$DEST/"
mkdir -p "$HOME/Pictures/khoipros"   # thư mục hình nền của khoiprOS (Super+W)
if [ ! -s "$DEST/three.min.js" ] || [ "$(stat -c %s "$DEST/three.min.js")" -lt 100000 ]; then
    if curl -fsSL "$THREE_URL" -o "$DEST/three.min.js.part" && [ "$(stat -c %s "$DEST/three.min.js.part")" -gt 100000 ]; then
        mv "$DEST/three.min.js.part" "$DEST/three.min.js"
    else
        rm -f "$DEST/three.min.js.part"; echo "   ! Không tải được three.js — sẽ dùng bản trên mạng"
    fi
fi

# ---------- 4. phím tắt + tự chạy khi đăng nhập ----------
H="$HOME/.config/hypr"
if grep -qs "kkkhoishell/launch.sh" "$H/hyprland.lua" "$H/hyprland.conf" "$H"/*.lua 2>/dev/null; then
    echo "==> Phím tắt khoiprOS đã có trong cấu hình Hyprland — giữ nguyên"
elif ask "==> Thêm phím tắt (Super+O mở khoiprOS, Super+L khoá, Super+W đổi hình nền) và tự chạy khi đăng nhập?"; then
    supero=1; superl=1; superw=1
    grep -qsE '(SUPER|mainMod|\$mod)[^#]*(\+|,) *[oO] *("|,|\))' "$H/hyprland.conf" "$H"/*.lua 2>/dev/null && supero=0
    grep -qsE '(SUPER|mainMod|\$mod)[^#]*(\+|,) *[wW] *("|,|\))' "$H/hyprland.conf" "$H"/*.lua 2>/dev/null && superw=0
    grep -qsE '(SUPER|mainMod|\$mod)[^#]*(\+|,) *[lL] *("|,|\))' "$H/hyprland.conf" "$H"/*.lua 2>/dev/null && superl=0
    if [ -f "$H/hyprland.lua" ]; then
        F="$H/hyprland.lua"; cp "$F" "$F.khoipros-install.bak"
        {
            echo ""; echo "-- khoiprOS"
            [ $supero = 1 ] && echo "hl.bind(\"SUPER + O\", hl.dsp.exec_cmd(\"$L\"))"
            [ $superl = 1 ] && echo "hl.bind(\"SUPER + L\", hl.dsp.exec_cmd(\"$L lock\"))"
            [ $superw = 1 ] && echo "hl.bind(\"SUPER + W\", hl.dsp.exec_cmd(\"$L wall\"))"
            echo "os.execute(\"$L start >/dev/null 2>&1 &\")"
        } >> "$F"
    else
        F="$H/hyprland.conf"; mkdir -p "$H"; [ -f "$F" ] && cp "$F" "$F.khoipros-install.bak"
        {
            echo ""; echo "# khoiprOS"
            [ $supero = 1 ] && echo "bind = SUPER, O, exec, $L"
            [ $superl = 1 ] && echo "bind = SUPER, L, exec, $L lock"
            [ $superw = 1 ] && echo "bind = SUPER, W, exec, $L wall"
            echo "exec-once = $L start"
        } >> "$F"
    fi
    echo "   Đã thêm vào $F (bản cũ: $(basename "$F").khoipros-install.bak)"
    [ $supero = 0 ] && echo "   Super+O đang dùng cho việc khác nên không gắn. Mở/ẩn khoiprOS:  $L"
    [ $superl = 0 ] && echo "   Super+L đang dùng cho việc khác nên không gắn. Muốn khoá có hiệu ứng: đổi lệnh đó thành  $L lock"
    [ $superw = 0 ] && echo "   Super+W đang dùng cho việc khác nên không gắn. Bảng chọn hình nền:  $L wall"
    true
fi

# ---------- 5. chạy luôn ----------
if [ -n "$WAYLAND_DISPLAY" ] && command -v hyprctl >/dev/null; then
    pkill -f "python3 $DEST/main.py" 2>/dev/null; sleep 0.5
    bash "$L" start
    echo "==> khoiprOS đang khởi động…"
fi
cat <<MSG

Xong! Super+O: mở/ẩn khoiprOS · Super+L: khoá · Super+W: hình nền · Cài đặt nằm ở nút bánh răng trên thanh trên.
Hình nền: bỏ ảnh vào ~/Pictures/khoipros rồi bấm Super+W.
Cập nhật: chạy lại đúng lệnh cài.   Gỡ: $DEST/uninstall.sh
Nhật ký lỗi: /tmp/kkkhoishell.log
MSG
