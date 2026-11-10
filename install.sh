#!/usr/bin/env bash
# Install khoiprOS — one command:
#   bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
# or, from a cloned folder:  ./install.sh
# Custom install location: KHOIPROS_DIR=/some/path
set -e
REPO="deptraicodengu/khoipros"
DEST="${KHOIPROS_DIR:-$HOME/.config/kkkhoishell}"
THREE_URL="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
L="$DEST/launch.sh"
ask() { local a; read -rp "$1 [Y/n] " a </dev/tty || a=y; [[ ! "$a" =~ ^[Nn] ]]; }

# ---------- package manager (Arch / Debian-Ubuntu / Fedora / openSUSE) ----------
PM=""
for p in pacman apt-get dnf zypper; do command -v $p >/dev/null && { PM=$p; break; }; done
# package names per distro (generic name → real name)
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
# install the packages the repositories have; report the rest instead of failing the whole install
install_pkgs() {
    local ok=() no=() n
    for x in "$@"; do n=$(pkgname "$x"); if avail "$n"; then ok+=("$n"); else no+=("$n"); fi; done
    [ ${#no[@]} -gt 0 ] && echo "   Not in your repositories: ${no[*]} — skipped (khoiprOS still runs without them; see README › Compatibility)"
    [ ${#ok[@]} -eq 0 ] && return 0
    echo "   Installing: ${ok[*]}"
    case "$PM" in
        pacman)  sudo pacman -S --needed "${ok[@]}" ;;
        apt-get) sudo apt-get install -y "${ok[@]}" ;;
        dnf)     sudo dnf install -y "${ok[@]}" ;;
        zypper)  sudo zypper install -y "${ok[@]}" ;;
    esac || echo "   ! Package install failed — install the packages above manually, then run this command again"
}

# ---------- 0. Hyprland is required ----------
if ! command -v hyprctl >/dev/null; then
    echo "khoiprOS is a desktop shell for Hyprland, and Hyprland is not installed on this system."
    if [ -n "$PM" ] && avail hyprland && ask "==> Install Hyprland with $PM now?"; then
        install_pkgs hyprland kitty
        echo
        echo "Next steps:"
        echo "  1. Log out and choose the 'Hyprland' session on the login screen (or type  Hyprland  on a TTY)."
        echo "  2. In Hyprland, open a terminal (Super+Q) and run the khoiprOS install command again."
    else
        echo "Install Hyprland for your distro first:"
        echo "  https://wiki.hypr.land/Getting-Started/Installation/"
        echo "then run this command again inside a Hyprland session."
    fi
    exit 1
fi
if [ -z "$HYPRLAND_INSTANCE_SIGNATURE" ]; then
    echo "   ! You are not in a Hyprland session — installing anyway; khoiprOS will run once you log in to Hyprland."
fi

# ---------- 1. get the source (from a cloned folder, or download from GitHub) ----------
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ ! -f "$SRC/main.py" ] || [ ! -f "$SRC/index.html" ]; then
    echo "==> Downloading khoiprOS from github.com/$REPO"
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP" --strip-components=1
    SRC="$TMP"
fi

# ---------- 2. packages ----------
echo "==> Checking packages"
miss=()
python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("GtkLayerShell","0.1")' 2>/dev/null || miss+=(gi gtk layer)
python3 -c 'import gi
try: gi.require_version("WebKit2","4.1")
except ValueError: gi.require_version("WebKit2","4.0")' 2>/dev/null || miss+=(webkit)
python3 -c 'import cairo; import gi; gi.require_foreign("cairo")' 2>/dev/null || miss+=(cairo)
for c in hyprlock playerctl cava quickshell; do command -v $c >/dev/null || miss+=($c); done
# setting the wallpaper needs awww (the new name of swww) or swww
if ! { command -v awww-daemon || command -v swww-daemon; } >/dev/null 2>&1; then
    if [ -n "$PM" ] && avail awww; then miss+=(awww); else miss+=(swww); fi
fi
if [ ${#miss[@]} -gt 0 ]; then
    if [ -n "$PM" ]; then
        echo "   Missing: $(for x in "${miss[@]}"; do printf '%s ' "$(pkgname "$x")"; done)"
        ask "   Install them with $PM now?" && install_pkgs "${miss[@]}"
    else
        echo "   Missing: ${miss[*]} — please install them with your package manager."
    fi
fi
# required — khoiprOS cannot start without these
if ! python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("GtkLayerShell","0.1")' 2>/dev/null; then
    echo "✗ Python GObject + GTK 3 + gtk-layer-shell are missing — khoiprOS cannot run. Install them and run this command again."
    exit 1
fi

# ---------- 3. copy files ----------
echo "==> Installing to $DEST"
mkdir -p "$DEST"
[ -f "$DEST/main.py" ] && cp "$DEST/main.py" "$DEST/main.py.bak" && cp "$DEST/index.html" "$DEST/index.html.bak" 2>/dev/null || true
install -m 644 "$SRC/main.py" "$SRC/index.html" "$DEST/"
[ -f "$SRC/wallpicker.qml" ] && install -m 644 "$SRC/wallpicker.qml" "$DEST/"
install -m 755 "$SRC/launch.sh" "$SRC/uninstall.sh" "$DEST/"
mkdir -p "$HOME/Pictures/khoipros"   # khoiprOS wallpaper folder (Super+W)
if [ ! -s "$DEST/three.min.js" ] || [ "$(stat -c %s "$DEST/three.min.js")" -lt 100000 ]; then
    if curl -fsSL "$THREE_URL" -o "$DEST/three.min.js.part" && [ "$(stat -c %s "$DEST/three.min.js.part")" -gt 100000 ]; then
        mv "$DEST/three.min.js.part" "$DEST/three.min.js"
    else
        rm -f "$DEST/three.min.js.part"; echo "   ! Could not download three.js — the online copy will be used"
    fi
fi

# ---------- 4. key bindings + autostart ----------
H="$HOME/.config/hypr"
if grep -qs "kkkhoishell/launch.sh" "$H/hyprland.lua" "$H/hyprland.conf" "$H"/*.lua 2>/dev/null; then
    echo "==> khoiprOS key bindings are already in your Hyprland config — leaving them as they are"
elif ask "==> Add key bindings (Super+O khoiprOS, Super+L lock, Super+W wallpaper) and start khoiprOS at login?"; then
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
    echo "   Added to $F (backup: $(basename "$F").khoipros-install.bak)"
    [ $supero = 0 ] && echo "   Super+O is already used, so it was not bound. To show/hide khoiprOS, bind:  $L"
    [ $superl = 0 ] && echo "   Super+L is already used, so it was not bound. For the animated lock screen, bind:  $L lock"
    [ $superw = 0 ] && echo "   Super+W is already used, so it was not bound. For the wallpaper picker, bind:  $L wall"
    true
fi

# ---------- 5. start ----------
if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && [ -n "$WAYLAND_DISPLAY" ]; then
    pkill -f "python3 $DEST/main.py" 2>/dev/null; sleep 0.5
    bash "$L" start
    echo "==> Starting khoiprOS…"
fi
cat <<MSG

Done! Super+O: show/hide khoiprOS · Super+L: lock · Super+W: wallpaper · Settings: the gear button on the top bar.
Wallpapers: put images in ~/Pictures/khoipros, then press Super+W.
Update: run the install command again.   Uninstall: $DEST/uninstall.sh
Logs: /tmp/kkkhoishell.log
MSG
