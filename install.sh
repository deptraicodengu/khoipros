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

# ---------- trình quản lý gói (Arch / Debian-Ubuntu / Fedora / openSUSE) ----------
PM=""
for p in pacman apt-get dnf zypper; do command -v $p >/dev/null && { PM=$p; break; }; done
# tên gói theo từng distro (tên chung → tên thật; "-" = distro đó không có gói này)
pkgname() {
    case "$PM:$1" in
        pacman:gi)      echo python-gobject ;;      apt-get:gi)      echo python3-gi ;;
        dnf:gi)         echo python3-gobject ;;     zypper:gi)       echo python3-gobject ;;
        pacman:gtk)     echo gtk3 ;;                apt-get:gtk)     echo gir1.2-gtk-3.0 ;;
        dnf:gtk)        echo gtk3 ;;                zypper:gtk)      echo typelib-1_0-Gtk-3_0 ;;
        pacman:layer)   echo gtk-layer-shell ;;     apt-get:layer)   echo gir1.2-gtklayershell-0.1 ;;
        dnf:layer)      echo gtk-layer-shell ;;     zypper:layer)    echo typelib-1_0-GtkLayerShell-0_1 ;;
        pacman:webkit)  echo webkit2gtk-4.1 ;;      apt-get:webkit)  echo gir1.2-webkit2-4.1 ;;
        dnf:webkit)     echo webkit2gtk4.1 ;;       zypper:webkit)   echo typelib-1_0-WebKit2-4_1 ;;
        pacman:cairo)   echo python-cairo ;;        apt-get:cairo)   echo python3-gi-cairo ;;
        dnf:cairo)      echo python3-cairo ;;       zypper:cairo)    echo python3-gobject-cairo ;;
        *)              echo "$1" ;;               # hyprland, hyprlock, playerctl, cava, quickshell, awww, swww, kitty
    esac
}
avail() {
    case "$PM" in
        pacman)  pacman -Si "$1" >/dev/null 2>&1 ;;
        apt-get) apt-cache show "$1" 2>/dev/null | grep -q '^Package:' ;;
        dnf)     dnf -q info "$1" >/dev/null 2>&1 ;;
        zypper)  zypper -q info "$1" 2>/dev/null | grep -q '^Name' ;;
        *)       return 1 ;;
    esac
}
# cài những gói có trong kho; gói không có thì báo để tự cài (không làm hỏng cả lượt cài)
install_pkgs() {
    local ok=() no=() n
    for x in "$@"; do n=$(pkgname "$x"); if avail "$n"; then ok+=("$n"); else no+=("$n"); fi; done
    [ ${#no[@]} -gt 0 ] && echo "   Kho gói của máy không có: ${no[*]} — bỏ qua (khoiprOS vẫn chạy, chỉ thiếu phần đó)"
    [ ${#ok[@]} -eq 0 ] && return 0
    echo "   Sẽ cài: ${ok[*]}"
    case "$PM" in
        pacman)  sudo pacman -S --needed "${ok[@]}" ;;
        apt-get) sudo apt-get install -y "${ok[@]}" ;;
        dnf)     sudo dnf install -y "${ok[@]}" ;;
        zypper)  sudo zypper install -y "${ok[@]}" ;;
    esac || echo "   ! Cài gói lỗi — cài tay các gói trên rồi chạy lại lệnh này"
}

# ---------- 0. cần Hyprland ----------
if ! command -v hyprctl >/dev/null; then
    echo "khoiprOS là giao diện dành cho Hyprland — máy này chưa có Hyprland."
    if [ -n "$PM" ] && avail hyprland && ask "==> Cài Hyprland bằng $PM bây giờ?"; then
        install_pkgs hyprland kitty
        echo
        echo "Bước tiếp theo:"
        echo "  1. Đăng xuất, ở màn hình đăng nhập chọn phiên 'Hyprland' (hoặc gõ  Hyprland  ở TTY)."
        echo "  2. Trong Hyprland, mở terminal (Super+Q) và chạy lại lệnh cài khoiprOS."
    else
        echo "Kho gói của máy không có sẵn Hyprland. Xem cách cài cho distro của bạn:"
        echo "  https://wiki.hypr.land/Getting-Started/Installation/"
        echo "rồi chạy lại lệnh này trong phiên Hyprland."
    fi
    exit 1
fi
if [ -z "$HYPRLAND_INSTANCE_SIGNATURE" ]; then
    echo "   ! Bạn không ở trong phiên Hyprland — vẫn cài, nhưng khoiprOS chỉ chạy khi bạn đăng nhập vào Hyprland."
fi

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
python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("GtkLayerShell","0.1")' 2>/dev/null || miss+=(gi gtk layer)
python3 -c 'import gi
try: gi.require_version("WebKit2","4.1")
except ValueError: gi.require_version("WebKit2","4.0")' 2>/dev/null || miss+=(webkit)
python3 -c 'import cairo; import gi; gi.require_foreign("cairo")' 2>/dev/null || miss+=(cairo)
for c in hyprlock playerctl cava quickshell; do command -v $c >/dev/null || miss+=($c); done
# đặt hình nền cần awww (tên mới của swww) hoặc swww
if ! { command -v awww-daemon || command -v swww-daemon; } >/dev/null 2>&1; then
    if [ -n "$PM" ] && avail awww; then miss+=(awww); else miss+=(swww); fi
fi
if [ ${#miss[@]} -gt 0 ]; then
    if [ -n "$PM" ]; then
        echo "   Thiếu: $(for x in "${miss[@]}"; do printf '%s ' "$(pkgname "$x")"; done)"
        ask "   Cài bằng $PM ngay?" && install_pkgs "${miss[@]}"
    else
        echo "   Thiếu: ${miss[*]} — hãy cài bằng trình quản lý gói của bạn."
    fi
fi
# 4 thứ bắt buộc — thiếu thì khoiprOS không mở được
if ! python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("GtkLayerShell","0.1")' 2>/dev/null; then
    echo "✗ Chưa có Python GObject + GTK3 + gtk-layer-shell — khoiprOS không chạy được. Cài các gói này rồi chạy lại."
    exit 1
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
if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && [ -n "$WAYLAND_DISPLAY" ]; then
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
