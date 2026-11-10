#!/usr/bin/env python3
"""
kkkhoishell — overlay hành tinh 3D cho Hyprland
GTK3 + gtk-layer-shell + WebKit2, backend là một HTTP API nhỏ chạy trong cùng tiến trình.

  index.html  <--fetch /api/*-->  main.py  --hyprctl / wpctl / nmcli ...-->  hệ thống

Thay đổi so với bản cũ:
  * Bỏ cầu nối window.webkit.messageHandlers (nguyên nhân nút bấm không chạy / có thể gây segfault).
  * Tự phục vụ file trên 127.0.0.1:8888 → không cần "python3 -m http.server" riêng nữa.
  * Mọi API đều cần token ngẫu nhiên (chèn vào index.html lúc phục vụ) → trang web lạ không gọi được.
  * Cấu hình lưu ở settings.json (sửa trong giao diện Cài đặt).
"""
import os, sys, re, json, signal, subprocess, threading, shutil, secrets, socket, time, glob, copy
import urllib.request, urllib.parse, warnings, faulthandler
import random, math, colorsys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

faulthandler.enable()                  # nếu crash (segfault) thì in vị trí ra log
warnings.simplefilter("ignore")        # bỏ các cảnh báo Deprecation làm rối log

os.environ["GDK_BACKEND"] = "wayland"
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, GtkLayerShell, WebKit2, Gdk, GLib, Pango
try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except Exception:
    GdkPixbuf = None
try:
    import cairo
except ImportError:
    cairo = None

CONF_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(CONF_DIR, "settings.json")
HOST, PORT = "127.0.0.1", 8888
TOKEN = secrets.token_hex(16)
VERSION = "2.0"


def log(*a):
    print("[kkkhoishell]", *a, flush=True)


# ====================== Cấu hình mặc định (khớp DEFAULTS trong index.html) ======================
DEFAULT_SETTINGS = {
    "apps": [
        {"id": "terminal", "name": "Terminal", "icon": ">_",  "cmd": "kitty",                          "class": "kitty",       "alwaysNew": False},
        {"id": "neovim",   "name": "Neovim",   "icon": "</>", "cmd": "kitty --class kkk-nvim -e nvim", "class": "kkk-nvim",    "alwaysNew": False},
        {"id": "audio",    "name": "Audio",    "icon": "◎",   "cmd": "pavucontrol",                    "class": "pavucontrol", "alwaysNew": False},
        {"id": "control",  "name": "Control",  "icon": "⟎",   "cmd": "kitty --class kkk-btop -e btop", "class": "kkk-btop",    "alwaysNew": False},
        {"id": "rofi",     "name": "Rofi",     "icon": "⚲",   "cmd": "rofi -show drun",                "class": "rofi",        "alwaysNew": True},
    ],
    "ignore": ["kkkhoishell"],
    "appearance": {"lang": "vi", "accent": "#70a1ff", "hyprBorder": False, "autoAccent": False, "contrastPlanet": True, "wallpaper": "", "bootSplash": True, "bootEvery": True, "osWallpaper": "/usr/share/hypr/wall1.png", "wallDir": "", "extraColor": "#ffa502", "colorful": True, "panelOpacity": 0.65, "blur": 16,
                   "dim": 0.5, "uiScale": 1, "showCard": True, "showLabels": True},
    "planet": {"show": True, "autoRotate": True, "icons": True, "fps": 60, "pauseCovered": True, "coveredFps": 0, "rotateSpeed": 1, "orbitSpeed": 1, "cameraDistance": 32, "size": 4, "ringWidth": 0.14,
               "showRings": True, "stars": False, "labelsBehind": "dim", "perWindow": False},
    "bar": {"cpu": True, "ram": True, "volume": True, "battery": True, "clock": True, "clock24": True, "seconds": True, "wsCount": 5},
    "behavior": {"floatWindows": True, "hideOnLaunch": True, "escToHide": True, "numberKeys": True, "autoShowWhenEmpty": True},
    "display": {"nightTemp": 4500},
    "weather": {"enabled": True, "location": "Tokyo", "unit": "C"},
    "power": {"lockCmd": "hyprlock", "confirm": True, "khoiLock": True},
    "tools": {"network": "nm-connection-editor", "bluetooth": "blueman-manager", "audio": "pavucontrol"},
    "perf": {"shareWeb": False},
    "colors": {"core": "#70a1ff", "ring": "#70a1ff", "ring2": "#ffa502", "shards": "#1aa3c4", "cava": "#70a1ff", "border": "#70a1ff", "bar": "#080d13", "glass": "#121629"},
    "info": {"cpu": "AMD Ryzen 9 9950X", "gpu": "NVIDIA GeForce RTX 5090", "owner": "Khoi", "device": "Khoi's Hyprland"},
    "cava": {"enabled": True, "bar": True, "ring": True, "bars": 48, "sens": 1.0},
    "fx": {"enabled": True, "sound": True, "soundVol": 0.35, "fps": 120, "hideWin": True, "revealMs": 150, "pieces": 40, "shatterMs": 1400, "assembleMs": 600, "maxRest": 140, "colorMode": "wall"},
}


def deep_merge(base, over):
    if isinstance(base, list):
        return over if isinstance(over, list) else copy.deepcopy(base)
    if isinstance(base, dict):
        over = over if isinstance(over, dict) else {}
        return {k: deep_merge(v, over.get(k)) if k in over else copy.deepcopy(v) for k, v in base.items()}
    if over is None:
        return base
    if isinstance(base, bool):
        return over if isinstance(over, bool) else base
    if isinstance(base, (int, float)):
        return over if isinstance(over, (int, float)) and not isinstance(over, bool) else base
    return over if isinstance(over, type(base)) else base


def sanitize(s):
    s = deep_merge(DEFAULT_SETTINGS, s)
    apps, seen = [], set()
    for a in s["apps"]:
        if not isinstance(a, dict):
            continue
        app = {k: str(a.get(k, "")).strip() for k in ("id", "name", "icon", "cmd", "class")}
        if re.match(r"^#[0-9a-fA-F]{6}$", str(a.get("color", ""))):
            app["color"] = a["color"]
        app["alwaysNew"] = bool(a.get("alwaysNew", False))
        app["id"] = re.sub(r"[^a-zA-Z0-9_-]", "", app["id"]) or f"app{len(apps) + 1}"
        while app["id"] in seen:
            app["id"] += "_"
        seen.add(app["id"])
        apps.append(app)
    s["apps"] = apps
    s["ignore"] = [str(x).strip().lower() for x in s["ignore"] if str(x).strip()]
    return s


BAR_EN = {
    "Ra desktop hành tinh / quay lại (Super+O)": "Planet desktop / back (Super+O)", "Trình phát nhạc": "Music player",
    "CPU — bấm để mở Control": "CPU — click to open Control", "RAM — bấm để mở Control": "RAM — click to open Control",
    "Mạng — bấm mở điều khiển nhanh": "Network — click for quick controls",
    "Âm lượng — lăn chuột để chỉnh · bấm mở điều khiển nhanh": "Volume — scroll to adjust · click for quick controls",
    "Pin — bấm mở điều khiển nhanh": "Battery — click for quick controls", "Lịch": "Calendar", "Cài đặt": "Settings", "Nguồn": "Power",
    "(trống)": "(empty)", "Desktop hành tinh · Super+O để quay lại": "Planet desktop · Super+O to go back",
    "tắt": "off", "Nhạc": "Music",
}


def _t(s):
    """Chữ trên thanh GTK theo ngôn ngữ đang chọn (Cài đặt › Giao diện › Ngôn ngữ)."""
    try:
        if SETTINGS["appearance"].get("lang") == "en":
            return BAR_EN.get(s, s)
    except Exception:
        pass
    return s


def restart_self():
    """Khởi động lại cả tiến trình (thanh GTK + 2 lớp web) — dùng khi đổi ngôn ngữ."""
    log("khởi động lại khoiprOS để đổi ngôn ngữ")
    try:
        CAVA.stop()
    except Exception:
        pass
    args = [sys.executable, os.path.abspath(__file__), "--no-boot"]   # đổi ngôn ngữ: vào thẳng, không chiếu màn khởi động
    if REOPEN:
        args.append("--open=" + REOPEN)                                 # mở lại đúng trang cài đặt đang xem
    os.execv(sys.executable, args)


REOPEN = ""
ARG_OPEN = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--open=")), "")


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return sanitize(json.load(f))
    except FileNotFoundError:
        d = copy.deepcopy(DEFAULT_SETTINGS)
        # cài lần đầu: máy để tiếng Việt thì dùng tiếng Việt, còn lại dùng tiếng Anh
        loc = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").lower()
        d["appearance"]["lang"] = "vi" if loc.startswith("vi") else "en"
        return d
    except Exception as e:
        log("settings.json lỗi, dùng mặc định:", e)
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(s):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_FILE)


SETTINGS = load_settings()
SETTINGS_VER = 0
SETTINGS_LOCK = threading.Lock()


# ====================== Lệnh hệ thống ======================
def has(x):
    return shutil.which(x) is not None


def sh(args, timeout=2):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return None


def run(args, timeout=4):
    """Chạy lệnh, trả về (thành công, output) để báo lên giao diện."""
    log("→", " ".join(args))
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip()
        log("←", r.returncode, out[:200])
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def pgrep(name):
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0


def hj(*args):
    try:
        out = subprocess.run(["hyprctl", *args, "-j"], capture_output=True, text=True, timeout=2).stdout
        return json.loads(out)
    except Exception:
        return None


LUA_MODE = None   # None = chưa biết; True = Hyprland dùng cấu hình Lua (hyprctl dispatch nhận biểu thức Lua)


def _lua_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _lua_candidates(name, arg):
    """Các cách viết Lua tương ứng lệnh dispatch kiểu cũ, thử lần lượt tới khi chạy được."""
    if name == "exec":
        return [f"hl.dsp.exec_cmd({_lua_str(arg)})", f"hl.dsp.exec({_lua_str(arg)})"]
    if name in ("focuswindow", "closewindow"):
        addr = arg.split(":", 1)[1] if arg.startswith("address:") else arg
        fn = "hl.dsp.focus" if name == "focuswindow" else "hl.dsp.window.close"
        return [f"{fn}({{ window = {_lua_str('address:' + addr)} }})", f"{fn}({{ window = {_lua_str(addr)} }})"]
    if name == "workspace":
        return [f"hl.dsp.focus({{ workspace = {_lua_str(arg)} }})"]
    if name == "exit":
        return ["hl.dsp.exit()"]
    if name == "togglefloating":
        w = _lua_str(arg)
        return [f'hl.dsp.window.float({{ action = "toggle", window = {w} }})']
    if name in ("resizewindowpixel", "movewindowpixel"):
        m = re.match(r"exact (-?\d+) (-?\d+),(address:0x[0-9a-fA-F]+)$", arg)
        if not m:
            return []
        x, y, w = m.group(1), m.group(2), _lua_str(m.group(3))
        fn = "hl.dsp.window.resize" if name == "resizewindowpixel" else "hl.dsp.window.move"
        return [f"{fn}({{ window = {w}, x = {x}, y = {y}, relative = false }})",
                f"{fn}({{ window = {w}, x = {x}, y = {y}, exact = true }})"]
    return []


def _dispatch_ok(ok, out):
    low = out.lower()
    return ok and (out == "" or low.startswith("ok")) and "error" not in low


def dispatch(name, arg=""):
    """Chạy một dispatcher Hyprland, tự hỗ trợ cả cấu hình cũ (hyprlang) lẫn cấu hình Lua."""
    global LUA_MODE
    if LUA_MODE is not True:
        ok, out = run(["hyprctl", "dispatch", name] + ([arg] if arg else []))
        if _dispatch_ok(ok, out):
            LUA_MODE = False
            return True, out
        if "hl.dispatch" not in out and "lua" not in out.lower():
            return False, out
        LUA_MODE = True
        log("Hyprland đang dùng cấu hình Lua → chuyển sang cú pháp hl.dsp.*")
    out = "không có cú pháp Lua cho " + name
    for expr in _lua_candidates(name, arg):
        ok, out = run(["hyprctl", "dispatch", expr])
        if _dispatch_ok(ok, out):
            return True, out
    return False, out



def ucolor(key, fallback):
    """Màu của một phần tử (Cài đặt › Màu sắc), dạng #rrggbb."""
    v = (SETTINGS.get("colors") or {}).get(key) or ""
    return v if re.match(r"^#[0-9a-fA-F]{6}$", v) else fallback


def shard_palette():
    import colorsys
    base = ucolor("shards", "#1aa3c4").lstrip("#")
    r, g, b = (int(base[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    out = []
    for dh, dl in ((0, 0), (-0.03, -0.12), (0.03, 0.1), (0.05, -0.05), (-0.05, 0.05), (0, 0.16), (0.02, -0.18)):
        rr, gg, bb = colorsys.hls_to_rgb((h + dh) % 1, min(0.8, max(0.18, l + dl)), min(1, s + 0.05))
        out.append("#%02x%02x%02x" % (round(rr * 255), round(gg * 255), round(bb * 255)))
    return out


# ====================== Icon app (cho hành tinh) ======================
# Đọc các tệp .desktop để biết class cửa sổ ↔ icon. Thư mục ứng dụng thay đổi (cài / gỡ app) → tự quét lại.
APP_DIRS = ["/usr/share/applications", "/usr/local/share/applications", os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications", os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications"]
ICON_EXT = (".png", ".svg", ".xpm")
_ICONS = {"sig": None, "map": {}, "ver": 0, "t": 0, "cache": {}}
_ICON_LOCK = threading.Lock()


def _icon_theme_dirs():
    names = []
    for f in (os.path.expanduser("~/.config/gtk-3.0/settings.ini"), os.path.expanduser("~/.config/gtk-4.0/settings.ini")):
        try:
            m = re.search(r"gtk-icon-theme-name\s*=\s*(.+)", open(f, encoding="utf-8").read())
            if m:
                names.append(m.group(1).strip().strip('"'))
        except Exception:
            pass
    names += ["Papirus-Dark", "Papirus", "breeze-dark", "breeze", "Adwaita", "hicolor"]
    roots = [os.path.expanduser("~/.local/share/icons"), os.path.expanduser("~/.icons"), "/usr/share/icons",
             "/var/lib/flatpak/exports/share/icons", os.path.expanduser("~/.local/share/flatpak/exports/share/icons")]
    out = []
    for n in dict.fromkeys(names):
        for r in roots:
            d = os.path.join(r, n)
            if os.path.isdir(d):
                out.append(d)
    return out


def _find_icon_file(name):
    if not name:
        return None
    if name.startswith("/"):
        return name if os.path.isfile(name) else None
    for d in _icon_theme_dirs():
        for sub in ("scalable/apps", "256x256/apps", "512x512/apps", "128x128/apps", "96x96/apps", "64x64/apps", "48x48/apps",
                    "apps/scalable", "apps/256", "apps/128", "apps/64", "apps/48", "256x256@2/apps"):
            for ext in (".svg", ".png"):
                p = os.path.join(d, sub, name + ext)
                if os.path.isfile(p):
                    return p
    for ext in ICON_EXT:
        p = os.path.join("/usr/share/pixmaps", name + ext)
        if os.path.isfile(p):
            return p
    return None


def _scan_desktop():
    sig = []
    for d in APP_DIRS:
        try:
            sig.append((d, os.stat(d).st_mtime))
        except Exception:
            pass
    sig = tuple(sig)
    if sig == _ICONS["sig"]:
        return
    m = {}
    for d in APP_DIRS:
        for f in glob.glob(os.path.join(d, "*.desktop")):
            try:
                txt = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            sec = txt.split("[Desktop Entry]", 1)[-1].split("\n[", 1)[0]
            kv = dict(re.findall(r"^([A-Za-z]+)=(.*)$", sec, re.M))
            icon = kv.get("Icon", "").strip()
            if not icon:
                continue
            base = os.path.basename(f)[:-8]
            keys = {base.lower(), base.split(".")[-1].lower(), kv.get("StartupWMClass", "").strip().lower(),
                    kv.get("Name", "").strip().lower()}
            ex = kv.get("Exec", "").split()
            if ex:
                keys.add(os.path.basename(ex[0]).lower())
                if ex[0] == "flatpak" and len(ex) > 2:
                    keys.add(ex[-1].lower())
            for k in keys:
                if k:
                    m.setdefault(k, icon)
    with _ICON_LOCK:
        _ICONS.update(sig=sig, map=m, ver=_ICONS["ver"] + 1, cache={})
    log(f"icon: đã đọc {len(m)} tên app từ tệp .desktop")


def icons_ver():
    if time.time() - _ICONS["t"] > 10:
        _ICONS["t"] = time.time()
        try:
            _scan_desktop()
        except Exception as e:
            log("icon lỗi:", e)
    return _ICONS["ver"]


def icon_for(key):
    """key = class cửa sổ / lệnh / tên app → đường dẫn tệp icon (hoặc None)."""
    k = re.sub(r"[^\w.+\- ]", "", (key or "").strip().lower())[:80]   # không cho "/" hay ".." → không đọc được tệp ngoài
    if not k or ".." in k:
        return None
    icons_ver()
    with _ICON_LOCK:
        if k in _ICONS["cache"]:
            return _ICONS["cache"][k]
        mp = _ICONS["map"]
    cand = [c for c in dict.fromkeys([k, k.split(".")[-1], k.split()[0] if k.split() else k]) if c]
    name = next((mp[c] for c in cand if c in mp), None) or next((c for c in cand if _find_icon_file(c)), None)
    path = _find_icon_file(name) if name else None
    if path and not path.lower().endswith(ICON_EXT):
        path = None
    with _ICON_LOCK:
        _ICONS["cache"][k] = path
    return path

# ====================== Ảnh bìa bài đang phát ======================
# playerctl cho mpris:artUrl dạng file://… (trình duyệt, mpv) hoặc https://… (Spotify) → tải về / dùng tệp sẵn có.
ART_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "khoipros-art")
_ART = {"url": None, "path": None, "h": ""}


def art_local(url):
    import hashlib
    url = (url or "").strip()
    if not url:
        return None
    if url == _ART["url"]:
        return _ART["path"]
    _ART.update(url=url, path=None, h="")
    if url.startswith("file://"):
        p = urllib.parse.unquote(url[7:])
        if os.path.isfile(p) and os.path.getsize(p) < 20 * 1024 * 1024:
            _ART.update(path=p, h=hashlib.sha1((url + str(os.path.getmtime(p))).encode()).hexdigest()[:12])
    elif url.startswith(("http://", "https://")):
        def dl():
            try:
                os.makedirs(ART_DIR, exist_ok=True)
                h = hashlib.sha1(url.encode()).hexdigest()[:12]
                dst = os.path.join(ART_DIR, h)
                if not os.path.isfile(dst):
                    req = urllib.request.Request(url, headers={"User-Agent": "khoipros"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = r.read(8 * 1024 * 1024)
                    with open(dst, "wb") as f:
                        f.write(data)
                if _ART["url"] == url:
                    _ART.update(path=dst, h=h)
                    POLLER.force.set()
            except Exception as e:
                log("ảnh bìa lỗi:", e)
        threading.Thread(target=dl, daemon=True).start()
    return _ART["path"]


# ====================== Hình nền (để lấy màu nhấn) ======================
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
_WP = {"t": 0, "v": None}


def _img_in(text):
    for p in re.findall(r"(?:~|/)[^\s\"'=,;]+", text or ""):
        p = os.path.expanduser(p.strip())
        if p.lower().endswith(IMG_EXT) and os.path.isfile(p):
            return p
    return None


WP_NS = "khoipros"   # awww chạy riêng cho khoiprOS (namespace riêng) → không đụng hình nền của etea / Hyprland


def _wp_tool():
    for t in ("awww", "swww"):
        if has(t) and has(t + "-daemon"):
            return t
    return None


def _wp_ours_running():
    return bool(sh(["pgrep", "-f", f"(awww|swww)-daemon --namespace {WP_NS}"]))


def _wp_default_running():
    out = sh(["pgrep", "-a", "-x", "awww-daemon"]) or ""
    out += "\n" + (sh(["pgrep", "-a", "-x", "swww-daemon"]) or "")
    return any(l.strip() and "--namespace" not in l for l in out.splitlines())


def os_wallpaper_start():
    """Hình nền riêng khi đang ở khoiprOS (Cài đặt › Giao diện). Chỉ bật khi bạn chưa tự chọn hình nền bằng
    awww/swww (Super+W) — chọn rồi thì tôn trọng lựa chọn đó. Thoát khoiprOS là tắt → etea/Hyprland giữ nền cũ."""
    p = os.path.expanduser(SETTINGS["appearance"].get("osWallpaper") or "")
    tool = _wp_tool()
    if not p or not os.path.isfile(p) or not tool:
        os_wallpaper_stop()
        return
    if _wp_default_running():
        log("hình nền: bạn đang dùng hình nền tự chọn → giữ nguyên, không đặt hình nền khoiprOS")
        os_wallpaper_stop()
        return
    if not _wp_ours_running():
        subprocess.Popen(["setsid", "-f", tool + "-daemon", "--namespace", WP_NS],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            time.sleep(0.1)
            if run([tool, "query", "--namespace", WP_NS])[0]:
                break
    ok, out = run([tool, "img", "--namespace", WP_NS, "--transition-type", "fade", "--transition-duration", "0.6", p])
    log("hình nền khoiprOS:", p, "" if ok else f"(lỗi: {out})")


# (thư mục, có quét thư mục con không). ~/Pictures chỉ quét cấp ngoài cùng — bên trong thường là ảnh chụp màn hình.
WALL_HOME = os.path.expanduser("~/Pictures/khoipros")   # thư mục hình nền riêng của khoiprOS: bỏ ảnh vào là có trong Super+W
WALL_DIRS = [(WALL_HOME, True), ("~/Pictures/Wallpapers", True), ("~/Pictures/wallpapers", True), ("~/Wallpapers", True), ("~/wallpapers", True),
             ("~/.local/share/wallpapers", True), ("/usr/share/hypr", False), ("/usr/share/backgrounds", True), ("~/Pictures", False)]
_NOT_WALL = re.compile(r"screenshot|screen ?shot|screencast|hyprshot|grim|scrot|flameshot|ảnh chụp|capture|lockdead", re.I)
_WALLS = []   # danh sách ảnh đã quét; ảnh xem trước chỉ được lấy theo số thứ tự trong danh sách này (không đọc tệp tuỳ ý)


def list_wallpapers():
    try:
        os.makedirs(WALL_HOME, exist_ok=True)
    except Exception:
        pass
    """Quét các thư mục hình nền quen thuộc (+ thư mục bạn thêm trong Cài đặt) → danh sách ảnh."""
    global _WALLS
    dirs = list(WALL_DIRS)
    extra = (SETTINGS["appearance"].get("wallDir") or "").strip()
    if extra:
        dirs.insert(0, (extra, True))
    seen, out = set(), []

    def add(f, d):
        if _NOT_WALL.search(f[len(d):]):
            return   # bỏ ảnh chụp màn hình, ảnh của trình khoá…
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and os.path.isfile(f):
            rf = os.path.realpath(f)
            try:
                twin = (os.path.basename(rf), os.path.getsize(rf))   # cùng tên + cùng dung lượng = bản sao
            except OSError:
                return
            if rf not in seen and twin not in seen:
                seen.add(rf); seen.add(twin)
                out.append(rf)

    real = [(os.path.realpath(os.path.expanduser(d)), deep) for d, deep in dirs]
    real = [(d, deep) for d, deep in real if os.path.isdir(d)]
    # ảnh nằm thẳng trong thư mục đứng trước, ảnh trong thư mục con (vd. anime/) xếp sau
    # → thư mục con nhiều ảnh không đẩy wall0/1/2… ra khỏi danh sách
    for d, deep in real:
        for f in sorted(glob.glob(os.path.join(d, "*")))[:600]:
            add(f, d)
    for d, deep in real:
        if deep:
            for f in sorted(glob.glob(os.path.join(d, "*", "*")))[:600]:
                if len(out) >= 300:
                    break
                add(f, d)
    out = out[:300]
    _WALLS = out
    bg(_prewarm_thumbs, list(out))
    return out


_PREWARM = threading.Lock()


def _prewarm_thumbs(lst):
    """Làm sẵn ảnh xem trước cho mọi hình nền ở nền sau — lúc lướt không phải giải mã ảnh gốc (PNG 10–30 MB) nữa."""
    if not _PREWARM.acquire(blocking=False):
        return
    try:
        for i in range(len(lst)):
            if _WALLS[:len(lst)] != lst:
                break   # danh sách đã đổi
            try:
                wall_thumb(i)
            except Exception:
                pass
    finally:
        _PREWARM.release()


_META = {}


def _img_size(f):
    """Đọc kích thước ảnh từ phần đầu tệp (PNG / JPEG / WebP) — không giải mã ảnh, chỉ vài micro giây."""
    import struct
    with open(f, "rb") as fh:
        head = fh.read(64)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            c = head[12:16]
            if c == b"VP8 ":
                w, h = struct.unpack("<HH", head[26:30]); return w & 0x3fff, h & 0x3fff
            if c == b"VP8L":
                b = head[21:25]
                return 1 + (((b[1] & 0x3f) << 8) | b[0]), 1 + (((b[3] & 0xf) << 10) | (b[2] << 2) | ((b[1] & 0xc0) >> 6))
            if c == b"VP8X":
                return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
        if head[:2] == b"\xff\xd8":
            fh.seek(2)
            while True:
                m = fh.read(2)
                if len(m) < 2 or m[0] != 0xFF:
                    break
                if m[1] in (0xD8, 0x01) or 0xD0 <= m[1] <= 0xD7:
                    continue
                ln = struct.unpack(">H", fh.read(2))[0]
                if m[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    hh, ww = struct.unpack(">xHH", fh.read(5)); return ww, hh
                fh.seek(ln - 2, 1)
    return 0, 0


def _wall_meta(f):
    """Kích thước ảnh + dung lượng (chỉ đọc phần đầu tệp, rất nhanh) — hiện dưới ảnh trong bảng Super+W."""
    try:
        st = os.stat(f)
        k = (f, st.st_mtime)
        if k not in _META:
            try:
                w, h = _img_size(f)
            except Exception:
                w = h = 0
            _META[k] = {"w": int(w), "h": int(h), "mb": round(st.st_size / 1048576, 1), "ext": f.rsplit(".", 1)[-1].upper()}
        return _META[k]
    except Exception:
        return {}


def wall_items(lst=None):
    """Danh sách hình nền kèm thông tin, đúng dạng bảng Super+W cần."""
    lst = _WALLS if lst is None else lst
    ow = SETTINGS["appearance"].get("osWallpaper")
    cur = os.path.realpath(os.path.expanduser(ow)) if ow else ""

    def same(f):
        if f == cur:
            return True
        try:
            return bool(cur) and os.path.basename(f) == os.path.basename(cur) and os.path.getsize(f) == os.path.getsize(cur)
        except OSError:
            return False
    return [dict({"i": i, "name": os.path.basename(f), "dir": os.path.basename(os.path.dirname(f)), "cur": same(f)}, **_wall_meta(f))
            for i, f in enumerate(lst)]


def wall_thumb(i):
    """Ảnh xem trước nhỏ (320 px), lưu sẵn trong ~/.cache/khoipros/thumbs."""
    if not (0 <= i < len(_WALLS)) or GdkPixbuf is None:
        return None
    src = _WALLS[i]
    import hashlib
    st = os.stat(src)
    key = hashlib.sha1(f"{src}:{st.st_mtime}:{st.st_size}:720".encode()).hexdigest()
    cdir = os.path.expanduser("~/.cache/khoipros/thumbs")
    os.makedirs(cdir, exist_ok=True)
    out = os.path.join(cdir, key + ".jpg")
    if not os.path.isfile(out):
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, 720, 405, True)   # đủ nét cho ảnh lớn ở bảng Super+W
        pb.savev(out, "jpeg", ["quality"], ["82"])
    with open(out, "rb") as f:
        return f.read()


def set_os_wallpaper(path):
    """Chọn hình nền trong khoiprOS: lưu vào Cài đặt rồi áp ngay. Nếu bạn đang dùng awww chung (Super+W)
    thì đổi luôn trên đó để hình nền hiện ra ngay."""
    global SETTINGS_VER
    with SETTINGS_LOCK:
        SETTINGS["appearance"]["osWallpaper"] = path
        SETTINGS_VER += 1
        save_settings(SETTINGS)
    tool = _wp_tool()
    if tool and _wp_default_running():
        run([tool, "img", "--transition-type", "grow", "--transition-duration", "0.8", path])
        log("hình nền (awww chung):", path)
    else:
        os_wallpaper_start()
    if SETTINGS["power"].get("khoiLock", True) and has("hyprlock"):
        bg(write_lock_conf)   # làm sẵn ảnh nền màn khoá → Super+L / tự khoá hiện ngay


def os_wallpaper_stop():
    sh(["pkill", "-f", f"(awww|swww)-daemon --namespace {WP_NS}"])


def find_wallpaper():
    """Tìm ảnh nền đang dùng: đường dẫn trong Cài đặt → swww → hyprpaper → tiến trình vẽ nền → tệp trạng thái."""
    p = os.path.expanduser(SETTINGS["appearance"].get("wallpaper") or "")
    if p and os.path.isfile(p):
        return p
    if has("awww") and _wp_default_running():
        r = _img_in(sh(["awww", "query"]))
        if r:
            return r
    q = os.path.expanduser(SETTINGS["appearance"].get("osWallpaper") or "")
    if q and os.path.isfile(q) and _wp_ours_running():
        return q
    if has("swww"):
        r = _img_in(sh(["swww", "query"]))
        if r:
            return r
    r = _img_in(sh(["hyprctl", "hyprpaper", "listactive"]))
    if r:
        return r
    try:   # swaybg -i …, mpvpaper …, hyprquickpaper …, quickshell …
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                args = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
            except Exception:
                continue
            name = os.path.basename(args[0].decode(errors="ignore")) if args and args[0] else ""
            if any(k in " ".join(a.decode(errors="ignore") for a in args[:3]) for k in ("swaybg", "mpvpaper", "paper", "wpaper", "quickshell")):
                r = _img_in(" ".join(a.decode(errors="ignore") for a in args))
                if r:
                    return r
    except Exception:
        pass
    home = os.path.expanduser("~")
    cands = []
    for d in (".cache", ".local/state", ".config"):
        for f in glob.glob(os.path.join(home, d, "*paper*")) + glob.glob(os.path.join(home, d, "*paper*", "*")) + \
                 glob.glob(os.path.join(home, d, "*wall*")) + glob.glob(os.path.join(home, d, "*wall*", "*")):
            if os.path.isfile(f) and os.path.getsize(f) < 65536 and not f.lower().endswith(IMG_EXT):
                cands.append(f)
    for f in sorted(cands, key=os.path.getmtime, reverse=True)[:30]:
        try:
            r = _img_in(open(f, encoding="utf-8", errors="ignore").read())
            if r:
                return r
        except Exception:
            pass
    return None


LOCK_CONF = os.path.join(CONF_DIR, "hyprlock.conf")


def _hx(h, a=1.0):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {a})"


LOCK_PLANET = os.path.join(CONF_DIR, "lock-planet.png")


def draw_lock_planet(acc, path, size=220):
    """Vẽ quả cầu khoiprOS (lõi phát sáng + vành quỹ đạo nghiêng) thành PNG cho màn hình khoá."""
    if cairo is None:
        return False
    h = acc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb((hh + 0.5) % 1, 0.68, max(0.6, ss))   # vành: sắc đối diện
    S_ = size
    sf = cairo.ImageSurface(cairo.FORMAT_ARGB32, S_, S_)
    c = cairo.Context(sf)
    cx = cy = S_ / 2
    R = S_ * 0.25
    glow = cairo.RadialGradient(cx, cy, R * 0.6, cx, cy, S_ * 0.5)   # quầng sáng
    glow.add_color_stop_rgba(0, r, g, b, 0.35)
    glow.add_color_stop_rgba(1, r, g, b, 0)
    c.set_source(glow); c.paint()

    def ring(front):
        c.save(); c.translate(cx, cy); c.rotate(-0.38); c.scale(1, 0.28)
        c.new_path(); c.arc(0, 0, R * 1.75, 0 if front else math.pi, math.pi if front else 2 * math.pi)   # y hướng xuống: 0→π là nửa dưới = nửa trước
        c.restore()
        c.set_line_width(S_ * 0.018)
        c.set_source_rgba(r2, g2, b2, 0.95 if front else 0.45)
        c.stroke()
    ring(False)   # nửa sau của vành nằm sau quả cầu
    sp = cairo.RadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R)
    sp.add_color_stop_rgba(0, min(1, r + 0.45), min(1, g + 0.45), min(1, b + 0.45), 1)
    sp.add_color_stop_rgba(0.55, r, g, b, 1)
    sp.add_color_stop_rgba(1, r * 0.25, g * 0.25, b * 0.3, 1)
    c.arc(cx, cy, R, 0, 2 * math.pi); c.set_source(sp); c.fill()
    c.set_line_width(1.2)   # lưới kinh/vĩ tuyến mảnh
    for k in range(1, 4):
        c.save(); c.translate(cx, cy); c.scale(math.cos(k * math.pi / 8), 1)
        c.arc(0, 0, R, 0, 2 * math.pi); c.restore()
        c.set_source_rgba(1, 1, 1, 0.16); c.stroke()
    ring(True)    # nửa trước vắt ngang quả cầu
    sf.write_to_png(path)
    return True


_LOCK_MEMO = {}
LOCK_BG = os.path.expanduser("~/.cache/khoipros/lock-bg.jpg")


def _lock_bg(src):
    """Bản thu nhỏ (1600 px, JPEG) của hình nền cho màn khoá. hyprlock phải giải mã ảnh nền trước khi hiện —
    ảnh gốc PNG 6–30 MB mất 1–2 giây (lộ desktop sau hiệu ứng ổ khoá); bản nhỏ chỉ vài chục ms.
    Đằng nào cũng làm mờ nên không thấy khác biệt."""
    try:
        st = os.stat(src)
        key = f"{src}:{st.st_mtime}:{st.st_size}"
        if _LOCK_MEMO.get("bg") == key and os.path.isfile(LOCK_BG):
            return LOCK_BG
        if GdkPixbuf is None or st.st_size < 600 * 1024:
            return src
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, 1600, 1600, True)
        os.makedirs(os.path.dirname(LOCK_BG), exist_ok=True)
        tmp = LOCK_BG + ".tmp"
        pb.savev(tmp, "jpeg", ["quality"], ["90"])
        os.replace(tmp, LOCK_BG)
        _LOCK_MEMO["bg"] = key
        return LOCK_BG
    except Exception as e:
        log("không thu nhỏ được hình nền màn khoá:", e)
        return src


def write_lock_conf():
    """Màn hình khoá khoiprOS = cấu hình hyprlock sinh theo màu nhấn, hình nền, tên chủ sở hữu, ngôn ngữ.
    hyprlock là trình khoá thật của Hyprland (ext-session-lock) → an toàn, không tự viết trình khoá riêng."""
    A = SETTINGS["appearance"]
    en = A.get("lang") == "en"
    acc = A.get("accent") if re.match(r"^#[0-9a-fA-F]{6}$", A.get("accent") or "") else "#70a1ff"
    owner = re.sub(r"[#$\n\r'\"\\]", "", (SETTINGS.get("info") or {}).get("owner") or "Khoi")[:40]
    wp = None
    try:
        wp = find_wallpaper()
    except Exception:
        pass
    bgpath = wp if wp and wp.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and "\n" not in wp else "screenshot"
    if bgpath != "screenshot":
        bgpath = _lock_bg(bgpath)
    h = acc.lstrip("#")
    ar, ag, ab = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    hh, ll, ss = colorsys.rgb_to_hls(ar / 255, ag / 255, ab / 255)
    c2 = "#%02x%02x%02x" % tuple(int(v * 255) for v in colorsys.hls_to_rgb((hh + 0.5) % 1, 0.68, max(0.6, ss)))
    planet = _LOCK_MEMO.get("planet") == acc and os.path.isfile(LOCK_PLANET)
    if not planet:
        try:
            planet = draw_lock_planet(acc, LOCK_PLANET)
            if planet:
                _LOCK_MEMO["planet"] = acc
        except Exception as e:
            log("không vẽ được quả cầu màn hình khoá:", e)
    py = "python3 -c"
    if en:
        greet = (py + ' "import time;h=time.localtime().tm_hour;print((\'Good morning\' if h<12 else \'Good afternoon\' if h<18 else \'Good evening\')+\', ' + owner + '\')"')
        date = 'date +"%A, %B %d"'
        T = {"pw": "Password…", "fail": "Wrong password, try again", "caps": "Caps Lock is on"}
    else:
        greet = (py + ' "import time;h=time.localtime().tm_hour;print((\'Chào buổi sáng\' if h<11 else \'Chào buổi trưa\' if h<13 else \'Chào buổi chiều\' if h<18 else \'Chào buổi tối\')+\', ' + owner + '\')"')
        date = (py + ' "import time;t=time.localtime();print(\'Thứ \'+[\'Hai\',\'Ba\',\'Tư\',\'Năm\',\'Sáu\',\'Bảy\',\'\'][t.tm_wday] if t.tm_wday<6 else \'Chủ nhật\', end=\'\');print(\', %d tháng %d\'%(t.tm_mday,t.tm_mon))"')
        T = {"pw": "Nhập mật khẩu…", "fail": "Sai mật khẩu, thử lại nhé", "caps": "Đang bật Caps Lock"}
    # chữ tính sẵn lúc khoá (không chạy lệnh) → hiện ngay từ khung hình đầu, không bị "nhảy" chữ khi màn khoá mờ vào
    lt = time.localtime()
    if en:
        date_s = time.strftime("%A, %B %d", lt)
        greet_s = ("Good morning" if lt.tm_hour < 12 else "Good afternoon" if lt.tm_hour < 18 else "Good evening") + ", " + owner
    else:
        date_s = ("Thứ " + ["Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy"][lt.tm_wday] if lt.tm_wday < 6 else "Chủ nhật") + f", {lt.tm_mday} tháng {lt.tm_mon}"
        greet_s = ("Chào buổi sáng" if lt.tm_hour < 11 else "Chào buổi trưa" if lt.tm_hour < 13 else "Chào buổi chiều" if lt.tm_hour < 18 else "Chào buổi tối") + ", " + owner
    planet_block = f"""
image {{
    monitor =
    path = {LOCK_PLANET}
    size = 150
    rounding = 0
    border_size = 0
    position = 0, 262
    halign = center
    valign = center
}}
""" if planet else ""
    conf = f"""# khoiprOS lock screen — tệp do khoiprOS tự tạo, mỗi lần khoá sẽ ghi lại. Đổi giao diện trong Cài đặt.
# Dùng cho hypridle:  lock_cmd = pidof hyprlock || hyprlock -c {LOCK_CONF}

general {{
    hide_cursor = true
}}

animations {{
    enabled = true
    bezier = kpOut, 0.16, 1, 0.3, 1
    bezier = kpLin, 1, 1, 0, 0
    bezier = kpFade, 0.45, 0, 0.25, 1
    animation = fadeIn, 1, 8, kpFade
    animation = fadeOut, 0
    animation = inputFieldDots, 1, 2, kpLin
    animation = inputFieldColors, 1, 7, kpOut
    animation = inputFieldFade, 1, 5, kpOut
    animation = inputFieldWidth, 1, 4, kpOut
}}

background {{
    monitor =
    path = {bgpath}
    blur_passes = 3
    blur_size = 9
    noise = 0.012
    brightness = 0.5
    contrast = 0.95
    vibrancy = 0.25
}}
{planet_block}
label {{
    monitor =
    text = <span foreground="##ffffff">khoipr</span><span foreground="##{h}">OS</span>
    font_size = 20
    font_family = Sans Bold
    position = 0, 175
    halign = center
    valign = center
}}

shape {{
    monitor =
    size = 470, 200
    color = rgba(12, 16, 28, 0.38)
    rounding = 28
    border_size = 1
    border_color = {_hx(acc, 0.55)} {_hx(c2, 0.35)} 45deg
    shadow_passes = 2
    shadow_size = 12
    shadow_color = rgba(0, 0, 0, 0.5)
    position = 0, 50
    halign = center
    valign = center
}}

label {{
    monitor =
    text = $TIME
    color = rgba(255, 255, 255, 0.97)
    font_size = 96
    font_family = Sans Light
    shadow_passes = 2
    shadow_size = 8
    shadow_color = {_hx(acc, 0.6)}
    position = 0, 75
    halign = center
    valign = center
}}

label {{
    monitor =
    text = {date_s}
    color = {_hx(acc, 1.0)}
    font_size = 16
    font_family = Sans
    position = 0, -10
    halign = center
    valign = center
}}

label {{
    monitor =
    text = {greet_s}
    color = rgba(225, 232, 248, 0.85)
    font_size = 14
    font_family = Sans
    position = 0, -78
    halign = center
    valign = center
}}

input-field {{
    monitor =
    size = 320, 54
    outline_thickness = 2
    dots_size = 0.24
    dots_spacing = 0.45
    dots_center = true
    dots_rounding = -1
    outer_color = {_hx(acc, 0.95)} {_hx(c2, 0.85)} 45deg
    inner_color = rgba(10, 14, 24, 0.7)
    font_color = rgba(240, 244, 255, 1.0)
    check_color = {_hx(c2, 1.0)} {_hx(acc, 1.0)} 120deg
    fail_color = rgba(255, 85, 110, 1.0) rgba(255, 150, 90, 1.0) 45deg
    capslock_color = rgba(255, 200, 80, 1.0)
    fade_on_empty = false
    placeholder_text = <span foreground="##aab4c8">{T['pw']}</span>
    fail_text = <b>{T['fail']}</b>
    rounding = -1
    shadow_passes = 2
    shadow_size = 10
    shadow_color = {_hx(acc, 0.35)}
    position = 0, -140
    halign = center
    valign = center
}}

label {{
    monitor =
    text = cmd[update:2000] playerctl metadata title 2>/dev/null | head -c 60 | sed 's/^/♪  /'
    color = rgba(220, 228, 245, 0.75)
    font_size = 13
    font_family = Sans
    position = 0, -205
    halign = center
    valign = center
}}

label {{
    monitor =
    text = {owner} · khoiprOS 1.0.0 Orbit
    color = rgba(200, 210, 230, 0.5)
    font_size = 11
    font_family = Sans
    position = 0, 26
    halign = center
    valign = bottom
}}
"""
    _write_if_changed(LOCK_CONF, conf)
    return LOCK_CONF


LAST_LOCK = 0.0


def watch_lock():
    """Sau khi gọi hyprlock: đợi màn khoá hiện xong rồi GỠ lớp hiệu ứng khỏi màn hình (ẩn hẳn cửa sổ),
    vì lúc khoá Hyprland ngừng vẽ khoiprOS → hình ổ khoá cuối cùng bị "đóng băng" và lộ ra khi mở khoá.
    Mở khoá xong (hyprlock thoát) mới hiện lại lớp hiệu ứng, lúc đó đã sạch."""
    def clear():
        run_js(SHELL.panel, "window.kkkLockClear && window.kkkLockClear()")
        return False
    t0, seen = time.time(), False
    while time.time() - t0 < 6:
        if sh(["pgrep", "-x", "hyprlock"]):
            seen = True
            break
        time.sleep(0.1)
    if not seen:
        GLib.idle_add(clear)
        return
    time.sleep(2.0)                       # đợi hyprlock hiện xong hẳn (ổ khoá vẫn giữ trên màn tới lúc đó)
    GLib.idle_add(clear)
    GLib.idle_add(lambda: SHELL.panel_win.hide() or False)
    log("đã khoá — tạm ẩn lớp hiệu ứng")
    while sh(["pgrep", "-x", "hyprlock"]):
        time.sleep(0.3)
    GLib.idle_add(SHELL.rebuild_panel)
    log("đã mở khoá — tạo lại lớp hiệu ứng mới (không còn ảnh ổ khoá cũ)")



def lock_with_anim():
    """Super+L (launch.sh lock): chạy hiệu ứng khoá trên lớp hiệu ứng rồi mới khoá.
    An toàn: nếu trang web không gọi khoá trong 3 giây thì tự khoá luôn."""
    t0 = time.time()
    run_js(SHELL.panel, "window.kkkLockNow ? window.kkkLockNow() : 0")

    def fallback():
        if LAST_LOCK < t0:
            log("hiệu ứng khoá không phản hồi → khoá ngay")
            dispatch("exec", lock_command())
        return False
    GLib.timeout_add(3000, fallback)


def lock_command():
    cmd = (SETTINGS["power"].get("lockCmd") or "hyprlock").strip()
    if SETTINGS["power"].get("khoiLock", True) and cmd == "hyprlock" and has("hyprlock"):
        try:
            return f"hyprlock -c {LOCK_CONF if os.path.isfile(write_lock_conf()) else ''}".strip()
        except Exception as e:
            log("màn hình khoá khoiprOS lỗi, dùng hyprlock thường:", e)
    return cmd


def wallpaper_info():
    if time.time() - _WP["t"] > 8:
        _WP["t"] = time.time()
        p = find_wallpaper()
        _WP["v"] = {"path": p, "mtime": int(os.path.getmtime(p))} if p else None
    return _WP["v"]


# ====================== Viền cửa sổ Hyprland theo màu khoiprOS ======================
HYPR_DIR = os.path.expanduser("~/.config/hypr")
HYPR_COLORS = os.path.join(HYPR_DIR, "khoipros_colors.lua")
HYPR_HOOK = '\n-- khoiprOS: viền cửa sổ theo màu nhấn (tệp khoipros_colors.lua do khoiprOS tự tạo; xoá 2 dòng này để bỏ)\npcall(require, "khoipros_colors")\n'


def _hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _shift_hue(h, deg, light=0.0):
    import colorsys
    r, g, b = (x / 255 for x in _hex_rgb(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((hh + deg / 360) % 1, min(0.85, max(0.2, ll + light)), ss)
    return "%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _write_if_changed(path, text):
    """Chỉ ghi khi nội dung khác — Hyprland tự nạp lại cấu hình mỗi khi tệp .lua đổi."""
    try:
        if open(path, encoding="utf-8").read() == text:
            return False
    except Exception:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def _rgba(hx, a):
    h = (hx or "#080d13").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        r, g, b = 8, 13, 19
    return f"rgba({r},{g},{b},{a})"


def apply_hypr_colors(acc, on, persist=False):
    """Ghi khoipros_colors.lua, gắn 1 dòng require vào cuối hyprland.lua (một lần, có sao lưu), rồi áp màu ngay."""
    main_lua = os.path.join(HYPR_DIR, "hyprland.lua")
    try:
        if on:
            a1, a2 = acc.lstrip("#"), _shift_hue(acc, 40, 0.08)
            ina = _shift_hue(acc, 0, -0.25)
            body = ('hl.config({ general = { col = {\n'
                    f'    active_border = {{ colors = {{"rgba({a1}ee)", "rgba({a2}ee)"}}, angle = 45 }},\n'
                    f'    inactive_border = "rgba({ina}88)",\n'
                    '} } })\n')
            # Chỉ ghi tệp lúc khởi động. Khi đang chạy mà ghi tệp, Hyprland tự nạp lại cấu hình
            # → chạy lại cả hyprland.lua → các lệnh khởi động trong đó chạy lại (có thể làm mất hình nền…).
            if persist:
                _write_if_changed(HYPR_COLORS, "-- Tệp này do khoiprOS tự tạo theo màu nhấn. Đừng sửa tay; tắt ở Cài đặt › Giao diện.\n" + body)
            if persist and os.path.isfile(main_lua):
                src = open(main_lua, encoding="utf-8").read()
                if "khoipros_colors" not in src:
                    bak = main_lua + ".khoipros.bak"
                    if not os.path.exists(bak):
                        shutil.copy2(main_lua, bak)
                    with open(main_lua, "a", encoding="utf-8") as f:
                        f.write(HYPR_HOOK)
                    log("viền: đã thêm dòng require vào cuối hyprland.lua (bản sao lưu: hyprland.lua.khoipros.bak)")
            # áp ngay không cần nạp lại cấu hình
            expr = "(function() " + body.replace("\n", " ") + " return hl.dsp.no_op() end)()"
            # KHÔNG gọi "hyprctl reload": nạp lại cả cấu hình sẽ chạy lại mọi lệnh trong hyprland.lua
            # (ví dụ lệnh đặt hình nền mặc định) → hình nền bị trả về mặc định.
            ok, out = run(["hyprctl", "dispatch", expr])
            if _dispatch_ok(ok, out):
                log("viền cửa sổ theo màu", acc)
            else:
                log("viền: Hyprland không nhận đổi màu trực tiếp — màu mới có hiệu lực từ lần đăng nhập sau")
        elif os.path.isfile(HYPR_COLORS):
            if persist:
                _write_if_changed(HYPR_COLORS, "-- khoiprOS: đang tắt viền theo màu nhấn\n")
            log("viền cửa sổ: đã tắt, màu gốc trong hyprland.lua có hiệu lực từ lần đăng nhập sau")
    except Exception as e:
        log("viền lỗi:", e)


def cls_match(win_cls, app_cls):
    w, a = (win_cls or "").lower(), (app_cls or "").lower()
    # "pavucontrol" khớp cả "org.pulseaudio.pavucontrol" (tên class mới của pavucontrol 6.x)
    return bool(a) and (w == a or w.endswith("." + a))


CAPS = {
    "volume": has("wpctl") or has("pamixer"),
    "brightness": has("brightnessctl"),
    "wifi": has("nmcli"),
    "bluetooth": has("bluetoothctl"),
    "profile": has("powerprofilesctl"),
    "night": has("hyprsunset"),
    "dnd": has("swaync-client") or has("makoctl"),
    "caffeine": has("hypridle"),
}


def read_info():
    info = {"host": socket.gethostname(), "kernel": os.uname().release, "gpu": None, "distro": None, "cpu": None}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    info["distro"] = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu"] = re.sub(r"\s+", " ", line.split(":", 1)[1]).strip()
                    break
    except Exception:
        pass
    out = sh(["lspci"]) if has("lspci") else None
    if out:
        gpus = [l.split(": ", 1)[1] for l in out.splitlines() if re.search(r"VGA compatible|3D controller|Display controller", l) and ": " in l]
        gpus.sort(key=lambda g: 0 if re.search(r"NVIDIA|AMD|ATI|Radeon", g) else 1)
        if gpus:
            g = gpus[0]
            m = re.search(r"\[([^\]]*(GeForce|RTX|GTX|Radeon|Arc|Iris|UHD)[^\]]*)\]", g)
            info["gpu"] = m.group(1) if m else re.sub(r"\s*\(rev .*?\)", "", g)
    # khoipros OS: thêm RAM, màn hình, phiên bản Hyprland cho trang Giới thiệu
    try:
        with open("/proc/meminfo") as f:
            kb = int(next(l for l in f if l.startswith("MemTotal")).split()[1])
        info["ram"] = f"{kb / 1048576:.1f} GB"
    except Exception:
        pass
    try:
        mons = json.loads(sh(["hyprctl", "monitors", "-j"]) or "[]")
        info["display"] = " · ".join(f"{m['width']}×{m['height']} @ {round(m.get('refreshRate', 60))} Hz" for m in mons) or None
    except Exception:
        pass
    try:
        v = json.loads(sh(["hyprctl", "version", "-j"]) or "{}")
        info["hypr"] = v.get("tag") or v.get("version")
    except Exception:
        pass
    return info


INFO = read_info()


# ====================== Thu thập trạng thái nền ======================
class Poller(threading.Thread):
    """Đọc CPU/RAM/âm lượng/wifi... mỗi 2 giây để /api/state trả về ngay lập tức."""

    def __init__(self):
        super().__init__(daemon=True)
        self.data = {}
        self.prev = None
        self.force = threading.Event()
        self.weather = None
        self.weather_key = None
        self.weather_at = 0

    def run(self):
        while True:
            try:
                self.poll()
            except Exception as e:
                log("poll lỗi:", e)
            try:
                self.poll_weather()
            except Exception as e:
                log("weather lỗi:", e)
            self.force.wait(2)
            self.force.clear()

    def poll(self):
        d = {}
        with open("/proc/stat") as f:
            p = list(map(int, f.readline().split()[1:]))
        idle, total = p[3] + p[4], sum(p)
        if self.prev and total > self.prev[0]:
            d["cpu"] = round(100 * (1 - (idle - self.prev[1]) / (total - self.prev[0])))
        else:
            d["cpu"] = self.data.get("cpu", 0)
        self.prev = (total, idle)

        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0])
        d["ramTotal"] = round(mem["MemTotal"] / 1048576, 1)
        d["ramUsed"] = round((mem["MemTotal"] - mem.get("MemAvailable", 0)) / 1048576, 1)

        d["battery"] = None
        for b in sorted(glob.glob("/sys/class/power_supply/BAT*")):
            try:
                with open(b + "/capacity") as f:
                    cap = int(f.read().strip())
                with open(b + "/status") as f:
                    stt = f.read().strip()
                d["battery"] = {"percent": cap, "status": stt}
                break
            except Exception:
                pass

        d["volume"] = d["muted"] = d["micMuted"] = None
        if has("wpctl"):
            out = sh(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]) or ""
            m = re.search(r"([\d.]+)", out)
            if m:
                d["volume"] = round(float(m.group(1)) * 100)
                d["muted"] = "MUTED" in out
            d["micMuted"] = "MUTED" in (sh(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]) or "")
        elif has("pamixer"):
            v = sh(["pamixer", "--get-volume"])
            d["volume"] = int(v) if v and v.isdigit() else None
            d["muted"] = sh(["pamixer", "--get-mute"]) == "true"
            d["micMuted"] = sh(["pamixer", "--default-source", "--get-mute"]) == "true"

        d["brightness"] = None
        if CAPS["brightness"]:
            out = sh(["brightnessctl", "-m"])
            if out:
                try:
                    d["brightness"] = int(out.split(",")[3].rstrip("%"))
                except Exception:
                    pass

        d["wifi"], d["ssid"] = False, ""
        if CAPS["wifi"]:
            d["wifi"] = (sh(["nmcli", "-t", "-f", "WIFI", "g"]) or "") == "enabled"
            for line in (sh(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"]) or "").splitlines():
                name, _, typ = line.rpartition(":")
                if typ == "802-11-wireless":
                    d["ssid"] = name.replace("\\:", ":")
                    break

        d["bluetooth"] = False
        if CAPS["bluetooth"]:
            d["bluetooth"] = "Powered: yes" in (sh(["bluetoothctl", "show"]) or "")

        d["profile"] = sh(["powerprofilesctl", "get"]) if CAPS["profile"] else None
        d["night"] = CAPS["night"] and pgrep("hyprsunset")
        d["dnd"] = False
        if has("swaync-client"):
            d["dnd"] = (sh(["swaync-client", "-D"]) or "") == "true"
        elif has("makoctl"):
            d["dnd"] = "do-not-disturb" in (sh(["makoctl", "mode"]) or "")
        d["caffeine"] = CAPS["caffeine"] and not pgrep("hypridle")
        d["media"] = None
        if has("playerctl"):
            out = sh(["playerctl", "metadata", "--format",
                      "{{status}}\t{{playerName}}\t{{artist}}\t{{title}}\t{{position}}\t{{mpris:length}}\t{{mpris:artUrl}}"])
            if out and "\t" in out:
                f = (out.split("\t") + [""] * 7)[:7]
                num = lambda x: int(x) // 1000000 if x.strip().isdigit() else 0
                if f[0] in ("Playing", "Paused"):
                    d["media"] = {"status": f[0], "player": f[1], "artist": f[2], "title": f[3],
                                  "pos": num(f[4]), "len": num(f[5]), "art": "", "artPath": ""}
                    ap = art_local(f[6])
                    if ap:
                        d["media"]["art"] = "/api/art?h=" + _ART["h"]
                        d["media"]["artPath"] = ap
        if d["media"]:
            self.last_media = (time.time(), d["media"])
        elif getattr(self, "last_media", None) and time.time() - self.last_media[0] < 6:
            d["media"] = self.last_media[1]
        self.data = d

    def poll_weather(self):
        w = SETTINGS["weather"]
        key = w["location"]
        if not w["enabled"]:
            self.weather = None
            return
        if key == self.weather_key and time.time() - self.weather_at < 900:
            return
        self.weather_key, self.weather_at = key, time.time()
        url = "https://wttr.in/" + urllib.parse.quote(key) + "?format=j1&lang=vi"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            j = json.load(r)
        cur = j["current_condition"][0]
        desc = (cur.get("lang_vi") or cur.get("weatherDesc") or [{}])[0].get("value", "")
        self.weather = {"tempC": int(cur["temp_C"]), "tempF": int(cur["temp_F"]), "desc": desc, "location": key}


POLLER = Poller()


# ====================== Trạng thái Hyprland ======================
def hypr_clients():
    cl = [c for c in (hj("clients") or []) if c.get("mapped", True) and not c.get("hidden", False)]
    cl.sort(key=lambda c: c.get("focusHistoryID", 999))   # cửa sổ focus gần nhất lên đầu
    return cl


_STATE_CACHE = {"t": 0, "v": None}
_STATE_LOCK = threading.Lock()


def get_state():
    # thanh trên và desktop cùng hỏi trạng thái → gộp lại, mỗi 0,4 giây gọi hyprctl một lần
    with _STATE_LOCK:
        if time.time() - _STATE_CACHE["t"] > 0.9 or _STATE_CACHE["v"] is None:
            _STATE_CACHE["v"] = build_state()
            _STATE_CACHE["t"] = time.time()
        v = dict(_STATE_CACHE["v"])
    v["raised"] = bool(SHELL and SHELL.raised)
    v["settingsVersion"] = SETTINGS_VER
    v["covered"] = (not v["raised"]) and v.pop("_activeWindows", 0) > 0
    return v


def build_state():
    S = SETTINGS
    clients = hypr_clients()
    running = {}
    for app in S["apps"]:
        wins = [c for c in clients if cls_match(c.get("class", ""), app["class"])]
        if wins:
            running[app["id"]] = {"address": wins[0]["address"], "count": len(wins)}

    ignore = set(S["ignore"])
    extras = {}
    for c in clients:
        k = c.get("class", "") or ""
        if not k or k.lower() in ignore or any(cls_match(k, a["class"]) for a in S["apps"]):
            continue
        key = c["address"] if S["planet"]["perWindow"] else k.lower()
        e = extras.get(key)
        if not e:
            nm = k.split(".")[-1]
            nm = nm[:1].upper() + nm[1:]
            if S["planet"]["perWindow"]:
                nm += ": " + (c.get("title") or "")[:22]
            e = extras[key] = {"id": key, "name": nm, "cls": k, "address": c["address"], "count": 0,
                               "workspace": str(c.get("workspace", {}).get("name", ""))}
        e["count"] += 1

    wss = {}
    for c in clients:
        wid = c.get("workspace", {}).get("id", 0)
        w = wss.setdefault(wid, {"id": wid, "name": c.get("workspace", {}).get("name", str(wid)), "windows": 0, "classes": []})
        w["windows"] += 1
        w["classes"].append(c.get("class", ""))
    aw = hj("activeworkspace") or {}
    act = hj("activewindow") or {}

    return {
        "running": running,
        "extras": sorted(extras.values(), key=lambda e: e["id"]),
        "workspaces": list(wss.values()),
        "activeWorkspace": aw.get("id", 1),
        "_activeWindows": aw.get("windows", 0),
        "activeWindow": {"class": act.get("class", ""), "title": act.get("title", "")} if act.get("address") else None,
        "stats": POLLER.data,
        "caps": CAPS,
        "info": dict(INFO, uptime=int(float(open("/proc/uptime").read().split()[0])),
                     **{k: v for k, v in S.get("info", {}).items() if v}),
        "weather": POLLER.weather if SETTINGS["weather"]["enabled"] else None,
        "wallpaper": wallpaper_info() if SETTINGS["appearance"].get("autoAccent") else None,
        "iconVer": icons_ver(),
    }


# ====================== Xử lý lệnh từ giao diện ======================
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]+$")


def handle_cmd(msg):
    S = SETTINGS
    t = msg.get("type")
    res = lambda ok, text, out="": {"ok": ok, "msg": text + (f" — {out}" if out and not ok else "")}
    maybe_hide = lambda: S["behavior"]["hideOnLaunch"] and GLib.idle_add(SHELL.hide)

    if t == "hide":
        GLib.idle_add(SHELL.hide)
        return res(True, "Đã hạ xuống desktop")

    if t == "toggle":
        GLib.idle_add(SHELL.toggle)
        return res(True, "Đổi nổi/chìm")

    if t == "panel":
        name = msg.get("name")
        if name not in ("settings", "power", "cal", "wallpaper"):
            return res(False, "Bảng không rõ")
        GLib.idle_add(SHELL.show, name)
        return res(True, "Mở bảng " + name)

    if t == "open":
        app = next((a for a in S["apps"] if a["id"] == msg.get("id")), None)
        if not app:
            return res(False, f"Không có app id '{msg.get('id')}'")
        if not app["cmd"]:
            return res(False, f"App {app['name']} chưa có lệnh mở")
        if not msg.get("forceNew") and not app["alwaysNew"]:
            wins = [c for c in hypr_clients() if cls_match(c.get("class", ""), app["class"])]
            if wins:
                maybe_hide()
                ok, out = dispatch("focuswindow", "address:" + wins[0]["address"])
                return res(ok, f"Chuyển tới {app['name']}", out)
        maybe_hide()
        ok, out = dispatch("exec", app["cmd"])
        return res(ok, f"hyprctl dispatch exec {app['cmd']}", out)

    if t in ("focus", "close"):
        addr = str(msg.get("address", ""))
        if not ADDR_RE.match(addr):
            return res(False, "Địa chỉ cửa sổ không hợp lệ")
        if t == "focus":
            maybe_hide()
            ok, out = dispatch("focuswindow", "address:" + addr)
            return res(ok, "Đã chuyển cửa sổ", out)
        ok, out = dispatch("closewindow", "address:" + addr)
        return res(ok, "Đã đóng cửa sổ", out)

    if t == "workspace":
        wid = str(msg.get("id", ""))
        if not re.match(r"^-?\d+$|^name:[\w-]+$", wid):
            return res(False, "Workspace không hợp lệ")
        # chỉ ẩn overlay nếu workspace đích có cửa sổ; workspace trống thì giữ overlay để dùng tiếp
        has_win = any(str(c.get("workspace", {}).get("id")) == wid or c.get("workspace", {}).get("name") == wid.replace("name:", "")
                      for c in hypr_clients())
        if has_win:
            maybe_hide()
        ok, out = dispatch("workspace", wid)
        return res(ok, f"Workspace {wid}" + ("" if has_win else " (trống)"), out)

    if t == "session":
        a = msg.get("action")
        GLib.idle_add(SHELL.hide)
        if a == "lock":
            global LAST_LOCK
            LAST_LOCK = time.time()
            ok, out = dispatch("exec", lock_command())
            bg(watch_lock)
        elif a == "logout":
            ok, out = dispatch("exit")
        elif a in ("suspend", "reboot", "shutdown"):
            ok, out = run(["systemctl", {"suspend": "suspend", "reboot": "reboot", "shutdown": "poweroff"}[a]])
        else:
            return res(False, "Hành động không rõ")
        return res(ok, f"Phiên: {a}", out)

    if t == "beat":
        global PANEL_BEAT, PANEL_LAG
        PANEL_BEAT, PANEL_LAG = time.time(), float(msg.get("lag") or 0)
        return res(True, "ok")

    if t == "jslog":
        log("[web]", str(msg.get("msg", ""))[:400])
        return res(True, "ok")

    if t == "openwalldir":
        os.makedirs(WALL_HOME, exist_ok=True)
        subprocess.Popen(["setsid", "-f", "xdg-open", WALL_HOME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res(True, "Đã mở " + WALL_HOME.replace(os.path.expanduser("~"), "~"))

    if t == "setwall":
        try:
            path = _WALLS[int(msg.get("i"))]
        except Exception:
            return res(False, "Không tìm thấy ảnh")
        bg(set_os_wallpaper, path)
        if msg.get("fx"):   # đổi từ bảng quickshell → mảnh kính vỡ ra ở giữa màn hình (lớp hiệu ứng của khoiprOS)
            GLib.idle_add(lambda: (run_js(SHELL.panel, "window.kkkWallFx && window.kkkWallFx()"), False)[1])
        return res(True, "Đang đổi hình nền…")

    if t == "reopen":
        global REOPEN
        REOPEN = re.sub(r"[^a-z]", "", str(msg.get("section") or ""))[:20]
        return res(True, "ok")

    if t == "bootshown":
        # màn hình khởi động đã bắt đầu vẽ nền tối của nó (mờ dần vào trong 0,7 s) → bỏ tấm phủ GTK sau đó
        GLib.timeout_add(150, SHELL.drop_cover)
        return res(True, "ok")

    if t == "bootdemo":
        GLib.idle_add(lambda: SHELL.boot_cover(5.5))
        GLib.timeout_add(300, lambda: (run_js(SHELL.panel, "window.kkkBoot && window.kkkBoot(true)"), False)[1])
        return res(True, "Đang chạy màn hình khởi động")

    if t == "media":
        a = msg.get("action")
        if a not in ("play-pause", "next", "previous"):
            return res(False, "Lệnh nhạc không hợp lệ")
        if not has("playerctl"):
            return res(False, "Chưa cài playerctl (sudo pacman -S playerctl)")
        ok, out = run(["playerctl", a])
        POLLER.force.set()
        return res(ok, {"play-pause": "Phát / tạm dừng", "next": "Bài tiếp", "previous": "Bài trước"}[a], out)

    if t == "fxtest":
        sw, sh = FX.sw, FX.sh + BAR_H
        FX.shatter(sw * 0.3, BAR_H + sh * 0.2, sw * 0.4, sh * 0.5, "kkk")
        return res(True, "Đã thử hiệu ứng vỡ")
    if t == "fxclear":
        FX.clear()
        return res(True, "Đã dọn hết mảnh")

    if t == "tool":
        cmd = S["tools"].get(str(msg.get("name")), "")
        if not cmd:
            return res(False, "Chưa đặt lệnh cho công cụ này")
        maybe_hide()
        ok, out = dispatch("exec", cmd)
        return res(ok, f"hyprctl dispatch exec {cmd}", out)

    # ---- các lệnh điều khiển hệ thống: chạy xong thì đọc lại trạng thái ngay ----
    r = system_cmd(t, msg, S)
    POLLER.force.set()
    return r


def system_cmd(t, msg, S):
    res = lambda ok, text, out="": {"ok": ok, "msg": text + (f" — {out}" if out and not ok else "")}
    on = bool(msg.get("on"))
    need = {"volume": "volume", "mute": "volume", "micmute": "volume", "brightness": "brightness", "wifi": "wifi",
            "bluetooth": "bluetooth", "profile": "profile", "night": "night", "dnd": "dnd", "caffeine": "caffeine"}.get(t)
    if not need:
        return res(False, f"Lệnh không rõ: {t}")
    if not CAPS[need]:
        return res(False, f"Chưa cài công cụ cho '{need}'")

    if t == "volume":
        v = max(0, min(100, int(msg.get("value", 0))))
        if has("wpctl"):
            ok, out = run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{v / 100:.2f}"])
        else:
            ok, out = run(["pamixer", "--set-volume", str(v)])
        return res(ok, f"Âm lượng {v}%", out)
    if t == "mute":
        ok, out = run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]) if has("wpctl") else run(["pamixer", "-t"])
        return res(ok, "Đổi trạng thái tắt tiếng", out)
    if t == "micmute":
        ok, out = run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]) if has("wpctl") else run(["pamixer", "--default-source", "-t"])
        return res(ok, "Đổi trạng thái mic", out)
    if t == "brightness":
        v = max(1, min(100, int(msg.get("value", 50))))
        ok, out = run(["brightnessctl", "set", f"{v}%"])
        return res(ok, f"Độ sáng {v}%", out)
    if t == "wifi":
        ok, out = run(["nmcli", "radio", "wifi", "on" if on else "off"])
        return res(ok, f"Wi-Fi {'bật' if on else 'tắt'}", out)
    if t == "bluetooth":
        if on and has("rfkill"):
            run(["rfkill", "unblock", "bluetooth"])
        ok, out = run(["bluetoothctl", "power", "on" if on else "off"], timeout=6)
        return res(ok, f"Bluetooth {'bật' if on else 'tắt'}", out)
    if t == "profile":
        v = msg.get("value")
        if v not in ("power-saver", "balanced", "performance"):
            return res(False, "Chế độ nguồn không hợp lệ")
        ok, out = run(["powerprofilesctl", "set", v])
        return res(ok, f"Chế độ nguồn: {v}", out)
    if t == "night":
        run(["pkill", "-x", "hyprsunset"])
        if on:
            temp = int(S["display"]["nightTemp"])
            ok, out = dispatch("exec", f"hyprsunset -t {temp}")
            return res(ok, f"Ánh sáng ban đêm {temp}K", out)
        return res(True, "Tắt ánh sáng ban đêm")
    if t == "dnd":
        if has("swaync-client"):
            ok, out = run(["swaync-client", "-dn" if on else "-df"])
        else:
            ok, out = run(["makoctl", "mode", "-a" if on else "-r", "do-not-disturb"])
        return res(ok, f"Không làm phiền: {'bật' if on else 'tắt'}", out)
    if t == "caffeine":
        if on:
            run(["pkill", "-x", "hypridle"])
            return res(True, "Caffeine bật (đã dừng hypridle)")
        ok, out = dispatch("exec", "hypridle")
        return res(ok, "Caffeine tắt (đã chạy lại hypridle)", out)
    return res(False, f"Lệnh không rõ: {t}")


# ====================== HTTP server ======================
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=CONF_DIR, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _host_ok(self):
        # chặn DNS-rebinding: chỉ chấp nhận Host là địa chỉ local
        return (self.headers.get("Host") or "").rsplit(":", 1)[0] in ("127.0.0.1", "localhost")

    def _authed(self):
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-KKK-Token", ""), TOKEN)

    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(os.path.join(CONF_DIR, "index.html"), encoding="utf-8") as f:
                html = f.read().replace("__KKK_TOKEN__", TOKEN)
            return self._send(html.encode(), "text/html; charset=utf-8")
        if path == "/api/art":   # chỉ trả ảnh bìa của bài đang phát
            ap = _ART.get("path")
            if not ap or not os.path.isfile(ap):
                return self._json({"ok": False}, 404)
            with open(ap, "rb") as f:
                data = f.read()
            ct = "image/png" if data[:4] == b"\x89PNG" else "image/webp" if data[8:12] == b"WEBP" else "image/jpeg"
            return self._send(data, ct)
        if path == "/api/icon":   # chỉ trả icon trong thư mục icon hệ thống, không đọc tệp tuỳ ý
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ip = None
            for k in q.get("k", [])[:3]:
                ip = icon_for(k)
                if ip:
                    break
            if not ip:
                return self._json({"ok": False}, 404)
            ext = ip.lower().rsplit(".", 1)[-1]
            with open(ip, "rb") as f:
                return self._send(f.read(), {"svg": "image/svg+xml", "png": "image/png", "xpm": "image/x-xpixmap"}.get(ext, "application/octet-stream"))
        if path == "/api/wpthumb":   # ảnh xem trước: chỉ theo số thứ tự trong danh sách đã quét
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                data = wall_thumb(int((q.get("i") or ["-1"])[0]))
            except Exception as e:
                log("ảnh xem trước lỗi:", e)
                data = None
            if not data:
                return self._json({"ok": False}, 404)
            return self._send(data, "image/jpeg")
        if path.startswith("/api/"):
            if not self._authed():
                return self._json({"ok": False, "msg": "unauthorized"}, 403)
            if path == "/api/ping":
                return self._json({"kkk": True, "version": VERSION})
            if path == "/api/state":
                return self._json(get_state())
            if path == "/api/settings":
                return self._json(SETTINGS)
            if path == "/api/wallpapers":
                lst = list_wallpapers()
                return self._json({"ok": True, "home": WALL_HOME.replace(os.path.expanduser("~"), "~"), "items": wall_items(lst)})
            if path == "/api/wallpaper":
                wp = find_wallpaper()
                if not wp:
                    return self._json({"ok": False, "msg": "không tìm thấy hình nền"}, 404)
                ext = wp.lower().rsplit(".", 1)[-1]
                with open(wp, "rb") as f:
                    return self._send(f.read(), {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/" + ext))
            return self._json({"ok": False, "msg": "not found"}, 404)
        if re.search(r"\.(json|py|sh|bak|tmp)$", path):
            return self.send_error(404)   # không phục vụ file cấu hình / mã nguồn
        return super().do_GET()

    def do_POST(self):
        if not self._authed():
            return self._json({"ok": False, "msg": "unauthorized"}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 512 * 1024:
                return self._json({"ok": False, "msg": "quá lớn"}, 413)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json({"ok": False, "msg": "JSON lỗi"}, 400)
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/cmd":
                return self._json(handle_cmd(body))
            if path == "/api/settings":
                global SETTINGS, SETTINGS_VER
                with SETTINGS_LOCK:
                    new = sanitize(body)
                    loc_changed = new["weather"] != SETTINGS["weather"]
                    lang_changed = new["appearance"].get("lang") != SETTINGS["appearance"].get("lang")
                    wp_changed = new["appearance"].get("osWallpaper") != SETTINGS["appearance"].get("osWallpaper")
                    fl_changed = bool(new["behavior"].get("floatWindows", True)) != bool(SETTINGS["behavior"].get("floatWindows", True))
                    SETTINGS = new
                    SETTINGS_VER += 1
                    save_settings(new)
                if lang_changed:
                    GLib.timeout_add(700, restart_self)
                if wp_changed:
                    bg(os_wallpaper_start)
                if fl_changed:
                    bg(float_all if _float_on() else unfloat_ours)
                if loc_changed:
                    POLLER.weather_key = None
                    POLLER.force.set()
                return self._json({"ok": True})
        except Exception as e:
            log("lỗi xử lý", path, e)
            return self._json({"ok": False, "msg": f"Lỗi backend: {e}"}, 500)
        return self._json({"ok": False, "msg": "not found"}, 404)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ====================== Cửa sổ layer-shell ======================
# Hai lớp, giống cách waybar / ETEA hoạt động:
#   * thanh trên  (namespace "kkkhoishell-bar"): lớp TOP, giữ chỗ phía trên → Hyprland xếp cửa sổ xuống dưới
#   * desktop     (namespace "kkkhoishell")    : lớp BOTTOM, nằm DƯỚI các cửa sổ, ngay trên hình nền
#     Super+O đưa desktop lên lớp OVERLAY (nổi trên app), nhấn lại hoặc Esc thì hạ xuống.
# Không bao giờ gỡ cửa sổ (window.hide) vì WebKitGTK hay segfault khi layer-surface bị gỡ rồi gắn lại.
BAR_H = 58
LS = GtkLayerShell
KB = LS.KeyboardMode


def set_kb(win, mode):
    try:
        LS.set_keyboard_mode(win, mode)
    except Exception:
        LS.set_keyboard_interactivity(win, mode == KB.EXCLUSIVE)


_WV_FIRST = None
try:
    _mp = WebKit2.MemoryPressureSettings.new(); _mp.set_memory_limit(180); _mp.set_kill_threshold(0)
    WebKit2.WebContext.set_memory_pressure_settings(_mp)
except Exception as _e:
    pass
try:
    WebKit2.WebContext.get_default().set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
except Exception:
    pass


def _no_gesture(win, wv):
    """Chặn chụm 2 ngón (zoom) / vuốt touchpad để giao diện không bị phóng to như trang web."""
    blocked = {getattr(Gdk.EventType, n) for n in ("TOUCHPAD_PINCH", "TOUCHPAD_SWIPE") if hasattr(Gdk.EventType, n)}

    def eat(_w, ev):
        try:
            return ev.type in blocked
        except Exception:
            return False
    for w in (win, wv):
        for sig in ("captured-event", "event"):
            try:
                w.connect(sig, eat)
            except Exception:
                pass
    try:   # nếu WebKit vẫn đổi mức phóng to thì đưa về 100%
        wv.connect("notify::zoom-level", lambda v, *_: v.get_zoom_level() != 1.0 and v.set_zoom_level(1.0))
    except Exception:
        pass


def make_surface(namespace, layer, edges, exclusive, height, kb, url, gpu=True):
    win = Gtk.Window()
    LS.init_for_window(win)
    LS.set_layer(win, layer)
    LS.set_namespace(win, namespace)
    for e in edges:
        LS.set_anchor(win, e, True)
    LS.set_exclusive_zone(win, exclusive)
    set_kb(win, kb)
    if height:
        win.set_size_request(-1, height)
    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)
    win.set_app_paintable(True)

    global _WV_FIRST
    # Tiết kiệm RAM (Cài đặt › Hệ thống): các bề mặt dùng chung 1 tiến trình WebKit → bớt ~100 MB
    # "Tiết kiệm RAM" (dùng chung 1 tiến trình WebKit) đã bỏ: quả cầu 3D chiếm hết tiến trình chung → lớp hiệu ứng
    # bị bỏ đói, mảnh vỡ / màn hình khởi động chạy chậm như đứng hình. Mỗi bề mặt luôn có tiến trình riêng.
    share = False
    wv = WebKit2.WebView(related_view=_WV_FIRST) if (share and _WV_FIRST is not None) else WebKit2.WebView()
    _WV_FIRST = _WV_FIRST or wv
    wv.connect("context-menu", lambda *a: True)   # chặn menu chuột phải của WebKit

    def on_crash(view, reason=None):
        # tiến trình WebKit của bề mặt này chết → màn hình giữ nguyên hình cuối (đứng hình). Nạp lại cho sống lại.
        log(f"WebKit [{namespace}] bị dừng ({reason}) → nạp lại")
        GLib.timeout_add(400, lambda: (view.load_uri(url.replace("&boot=1", "")), False)[1])   # nạp lại: không chiếu lại màn khởi động
    try:
        wv.connect("web-process-terminated", on_crash)
    except TypeError:
        wv.connect("web-process-crashed", lambda v: on_crash(v, "crash") or False)
    _no_gesture(win, wv)
    st = wv.get_settings()
    st.set_enable_webgl(gpu)
    st.set_enable_developer_extras(False)   # không cần công cụ dev → đỡ RAM
    try:   # cho phép phát âm thanh hiệu ứng mà không cần bấm chuột trước
        st.set_media_playback_requires_user_gesture(False)
    except Exception:
        pass
    if not gpu:   # thanh trên không cần 3D; tắt GPU để WebKit không vẽ chập chờn
        try:
            st.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
        except Exception:
            pass
    bg = Gdk.RGBA()
    bg.parse("rgba(0,0,0,0)")
    wv.set_background_color(bg)
    wv.load_uri(url)
    win.add(wv)
    win.show_all()
    return win, wv


def run_js(wv, code):
    try:
        if hasattr(wv, "evaluate_javascript"):
            wv.evaluate_javascript(code, -1, None, None, None, None, None)
        else:
            wv.run_javascript(code, None, None, None)
    except Exception as e:
        log("run_js lỗi:", e)


_JS_Q = {}   # (id webview, khoá) → [đang chạy?, mã chờ gửi]


def run_js_latest(wv, key, code):
    """Gửi JS kiểu "chỉ lấy bản mới nhất": nếu lần gửi trước WebKit chưa chạy xong thì bỏ các khung ở giữa.
    Không có cái này, sóng nhạc (cava) bắn ~60 lệnh/giây → hàng đợi của WebKit dồn ứ, mọi hiệu ứng khác
    (mảnh vỡ, màn hình khởi động) bị trễ cả mấy giây, trông như đứng hình."""
    k = (id(wv), key)
    st = _JS_Q.setdefault(k, [False, None])
    if st[0]:
        st[1] = code
        return

    def done(view, result, *a):
        try:
            if hasattr(view, "evaluate_javascript_finish"):
                view.evaluate_javascript_finish(result)
            else:
                view.run_javascript_finish(result)
        except Exception:
            pass
        nxt, st[1] = st[1], None
        st[0] = False
        if nxt:
            run_js_latest(view, key, nxt)
    st[0] = True
    try:
        if hasattr(wv, "evaluate_javascript"):
            wv.evaluate_javascript(code, -1, None, None, None, done, None)
        else:
            wv.run_javascript(code, None, done, None)
    except Exception as e:
        st[0] = False
        log("run_js lỗi:", e)


# ====================== Thanh trên (GTK thuần) ======================
def bg(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


BAR_CSS = """
@define-color accent %(accent)s;
window.kkk-bar { background-color: transparent; }
.kbar { background-color: %(barbg_a)s; border: 1px solid alpha(@accent, 0.22);
        border-radius: 14px; margin: 6px 8px; padding: 0 6px 0 10px; }
.kbar label { color: #dce8ee; font-family: Inter, "Noto Sans", "Segoe UI", sans-serif; font-size: 11px; }
.kbar button { background: none; background-image: none; border: none; box-shadow: none;
               padding: 4px 9px; border-radius: 8px; min-height: 0; min-width: 0; color: #8fa3b3; }
.kbar button:hover { background-color: alpha(@accent, 0.16); }
.kbar button label { color: #b9c7d1; }
.kbar button image { color: #b9c7d1; }
.kbar .brand-name { font-weight: 800; font-size: 14px; letter-spacing: 1px; color: #eef6f8; }
.kbar .ws { background-color: rgba(255,255,255,0.04); border-radius: 9px; padding: 3px; }
.kbar .ws button { padding: 2px 9px; border-radius: 7px; }
.kbar .ws button label { font-size: 11px; font-weight: 600; }
.kbar .ws button.empty label { color: #55677a; }
.kbar .ws button.active { background-color: @accent; padding: 2px 16px; }
.kbar .ws button.active label { color: #071014; font-weight: 800; }
.kbar .title { color: #7d93a3; padding: 4px 12px; font-size: 11px; }
.kbar .chip label { font-weight: 600; }
.kbar .chip.warn label { color: #eaba53; }
.kbar .media { background-color: alpha(@accent, 0.12); border: 1px solid alpha(@accent, 0.28); }
.kbar .media label { color: #eef6f8; }
.kbar .cluster { background-color: rgba(255,255,255,0.05); border-radius: 9px; }
.kbar .cluster button { border-radius: 9px; }
"""


class GtkBar:
    # ---- sóng nhạc nhỏ trên thanh ----
    def cava_widget(self):
        self.cava_da = Gtk.DrawingArea()
        self.cava_da.set_size_request(66, 18)
        self.cava_da.set_valign(Gtk.Align.CENTER)
        self.cava_da.connect("draw", self.cava_paint)
        self.cava_da.set_no_show_all(True)
        return self.cava_da

    def cava_draw(self):
        da = getattr(self, "cava_da", None)
        if da is None:
            return False
        show = SETTINGS.get("cava", {}).get("enabled", True) and SETTINGS.get("cava", {}).get("bar", True) and not CAVA.silent
        if show != da.get_visible():
            da.set_visible(show)
        if show:
            da.queue_draw()
        return False

    def cava_paint(self, da, cr):
        v = CAVA.vals
        if not v:
            return False
        W, H = da.get_allocated_width(), da.get_allocated_height()
        n = 12
        step = max(1, len(v) // n)
        acc = ucolor("cava", self.accent or "#2bd4c0").lstrip("#")
        try:
            r, g, b = (int(acc[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except Exception:
            r, g, b = 0.17, 0.83, 0.75
        bw = W / n
        for i in range(n):
            e = max(v[i * step:(i + 1) * step] or [0])
            h = max(2.0, e * H)
            cr.set_source_rgba(r, g, b, 0.55 + 0.45 * e)
            cr.rectangle(i * bw + bw * 0.2, (H - h) / 2, bw * 0.6, h)
            cr.fill()
        return False

    def __init__(self, shell):
        self.shell = shell
        self.accent = None
        self.ws_sig = None
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.load_css()

        w = self.win = Gtk.Window()
        w.get_style_context().add_class("kkk-bar")
        LS.init_for_window(w)
        LS.set_layer(w, LS.Layer.TOP)
        LS.set_namespace(w, "kkkhoishell-bar")
        for e in (LS.Edge.TOP, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, BAR_H)
        set_kb(w, KB.NONE)
        w.set_size_request(-1, BAR_H)
        visual = w.get_screen().get_rgba_visual()
        if visual:
            w.set_visual(visual)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.get_style_context().add_class("kbar")
        w.add(box)

        # --- trái: tên + workspace
        left = Gtk.Box(spacing=8)
        brand = Gtk.Button()
        bb = Gtk.Box(spacing=8)
        orb = Gtk.DrawingArea()
        orb.set_size_request(14, 14)
        orb.set_valign(Gtk.Align.CENTER)
        orb.connect("draw", self.orb_paint)
        self.brand_lbl = Gtk.Label()
        self.brand_lbl.get_style_context().add_class("brand-name")
        self.set_brand()
        bb.pack_start(orb, False, False, 0)
        bb.pack_start(self.brand_lbl, False, False, 0)
        brand.add(bb)
        brand.set_tooltip_text(_t("Ra desktop hành tinh / quay lại (Super+O)"))
        brand.connect("clicked", lambda *_: GLib.idle_add(self.shell.toggle))
        self.ws = Gtk.Box(spacing=3)
        self.ws.get_style_context().add_class("ws")
        left.pack_start(brand, False, False, 0)
        left.pack_start(self.ws, False, False, 0)
        box.pack_start(left, False, False, 0)

        # --- giữa: cửa sổ đang focus
        self.title = Gtk.Label(label="")
        self.title.get_style_context().add_class("title")
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(36)
        box.set_center_widget(self.title)

        # --- phải: chip + nút
        right = Gtk.Box(spacing=6)
        # chip nhạc: sóng cava + tên bài → bấm mở trình phát
        self.media_btn = Gtk.Button()
        self.media_btn.get_style_context().add_class("media")
        mb = Gtk.Box(spacing=6)
        self.art_da = Gtk.DrawingArea()
        self.art_da.set_size_request(20, 20)
        self.art_da.set_valign(Gtk.Align.CENTER)
        self.art_da.connect("draw", self.art_paint)
        self.art_da.set_no_show_all(True)
        self.art_pb, self.art_src = None, None
        mb.pack_start(self.art_da, False, False, 0)
        mb.pack_start(self.cava_widget(), False, False, 0)
        self.media_lbl = Gtk.Label(label="")
        self.media_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.media_lbl.set_max_width_chars(22)
        self.media_lbl.set_width_chars(10)
        mb.pack_start(self.media_lbl, False, False, 0)
        self.media_btn.add(mb)
        self.media_btn.set_tooltip_text(_t("Trình phát nhạc"))
        self.media_btn.set_no_show_all(True)
        mb.show_all()
        self.media_btn.connect("clicked", lambda *_: GLib.idle_add(self.shell.show, "media"))
        right.pack_start(self.media_btn, False, False, 2)
        self.chips = {}
        for key, tip in (("cpu", "CPU — bấm để mở Control"), ("ram", "RAM — bấm để mở Control")):
            b = Gtk.Button(label="")
            b.get_style_context().add_class("chip")
            b.set_tooltip_text(_t(tip))
            right.pack_start(b, False, False, 0)
            self.chips[key] = b
        # cụm mạng · âm lượng · pin → bảng điều khiển nhanh
        cl = Gtk.Box(spacing=0)
        cl.get_style_context().add_class("cluster")
        for key, tip in (("net", "Mạng — bấm mở điều khiển nhanh"),
                         ("vol", "Âm lượng — lăn chuột để chỉnh · bấm mở điều khiển nhanh"),
                         ("bat", "Pin — bấm mở điều khiển nhanh")):
            b = Gtk.Button(label="")
            b.get_style_context().add_class("chip")
            b.set_tooltip_text(_t(tip))
            b.connect("clicked", lambda *_: GLib.idle_add(self.shell.show, "cc"))
            cl.pack_start(b, False, False, 0)
            self.chips[key] = b
        right.pack_start(cl, False, False, 0)
        b = Gtk.Button(label="")
        b.get_style_context().add_class("chip")
        b.set_tooltip_text(_t("Lịch"))
        right.pack_start(b, False, False, 0)
        self.chips["clock"] = b
        self.chips["cpu"].connect("clicked", lambda *_: bg(handle_cmd, {"type": "open", "id": "control"}))
        self.chips["ram"].connect("clicked", lambda *_: bg(handle_cmd, {"type": "open", "id": "control"}))
        self.chips["vol"].add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.chips["vol"].connect("scroll-event", self.on_scroll)
        self.chips["clock"].connect("clicked", lambda *_: GLib.idle_add(self.shell.show, "cal"))
        for icon, fallback, tip, panel in (("preferences-system-symbolic", "⚙", "Cài đặt", "settings"),
                                           ("system-shutdown-symbolic", "⏻", "Nguồn", "power")):
            b = Gtk.Button()
            if Gtk.IconTheme.get_default().has_icon(icon):
                b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU))
            else:
                b.set_label(fallback)
            b.set_tooltip_text(_t(tip))
            b.connect("clicked", lambda _b, p=panel: GLib.idle_add(self.shell.show, p))
            right.pack_start(b, False, False, 0)
        box.pack_end(right, False, False, 0)

        w.show_all()
        GLib.timeout_add(1000, self.tick_clock)
        self.tick_clock()
        bg(self.loop)

    # ---- ảnh bìa nhỏ trên chip nhạc (bo góc) ----
    def set_art(self, path):
        if path == self.art_src:
            return
        self.art_src, self.art_pb = path, None
        if path and GdkPixbuf is not None:
            try:
                sc = max(1, self.art_da.get_scale_factor())
                self.art_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 20 * sc, 20 * sc, False)
            except Exception as e:
                log("ảnh bìa thanh lỗi:", e)
        self.art_da.set_visible(self.art_pb is not None)
        self.art_da.queue_draw()

    def art_paint(self, da, cr):
        pb = self.art_pb
        if pb is None:
            return False
        w, h, r = da.get_allocated_width(), da.get_allocated_height(), 5
        cr.new_sub_path()
        cr.arc(w - r, r, r, -1.5708, 0); cr.arc(w - r, h - r, r, 0, 1.5708)
        cr.arc(r, h - r, r, 1.5708, 3.1416); cr.arc(r, r, r, 3.1416, 4.7124)
        cr.close_path(); cr.clip()
        sc = pb.get_width() / max(1, w)
        cr.scale(1 / sc, 1 / sc)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        return False

    # ---- tên khoiprOS: "OS" trong khoipros tô màu nhấn ----
    def set_brand(self):
        lbl = getattr(self, "brand_lbl", None)
        if lbl is not None:
            acc = self.accent or "#70a1ff"
            lbl.set_markup(f'khoipr<span foreground="{acc}">OS</span>')

    def orb_paint(self, da, cr):
        acc = (self.accent or "#70a1ff").lstrip("#")
        try:
            r, g, b = (int(acc[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except Exception:
            r, g, b = 0.44, 0.63, 1.0
        w, h = da.get_allocated_width(), da.get_allocated_height()
        R = min(w, h) / 2 - 1
        if cairo is not None:
            grad = cairo.RadialGradient(w / 2 - R * 0.35, h / 2 - R * 0.35, R * 0.1, w / 2, h / 2, R)
            grad.add_color_stop_rgb(0, 1, 1, 1)
            grad.add_color_stop_rgb(0.4, r, g, b)
            grad.add_color_stop_rgb(1, r * 0.35, g * 0.35, b * 0.35)
            cr.set_source(grad)
        else:
            cr.set_source_rgb(r, g, b)
        cr.arc(w / 2, h / 2, R, 0, 6.2832)
        cr.fill()
        return False

    def load_css(self):
        acc = SETTINGS["appearance"].get("accent", "#70a1ff")
        if not re.match(r"^#[0-9a-fA-F]{6}$", acc):
            acc = "#70a1ff"
        barbg = ucolor("bar", "#080d13")
        if (acc, barbg) != (self.accent, getattr(self, "barbg", None)):
            self.accent, self.barbg = acc, barbg
            self.css.load_from_data((BAR_CSS % {"accent": acc, "barbg": barbg, "barbg_a": _rgba(barbg, 0.92)}).encode())
            self.set_brand()
        hb = (bool(SETTINGS["appearance"].get("hyprBorder")), ucolor("border", acc))
        if hb != getattr(self, "hypr_sig", None):
            first = getattr(self, "hypr_sig", None) is None
            self.hypr_sig = hb
            if hb[0] or not first:
                bg(apply_hypr_colors, hb[1], hb[0], first)

    def on_scroll(self, _w, ev):
        v = (POLLER.data or {}).get("volume")
        if v is None:
            return True
        d = 0
        if ev.direction == Gdk.ScrollDirection.UP:
            d = 5
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            d = -5
        elif ev.direction == Gdk.ScrollDirection.SMOOTH:
            d = -5 if ev.delta_y > 0 else 5 if ev.delta_y < 0 else 0
        if d:
            nv = max(0, min(100, v + d))
            POLLER.data["volume"] = nv
            bg(handle_cmd, {"type": "volume", "value": nv})
            self.chips["vol"].set_label(f"VOL {nv}%")
        return True

    def cycle_profile(self):
        order = ["power-saver", "balanced", "performance"]
        cur = (POLLER.data or {}).get("profile")
        nxt = order[(order.index(cur) + 1) % 3] if cur in order else "balanced"
        handle_cmd({"type": "profile", "value": nxt})

    def loop(self):
        while True:
            try:
                st = get_state()
                GLib.idle_add(self.apply, st)
            except Exception as e:
                log("bar lỗi:", e)
            time.sleep(1)

    def tick_clock(self):
        b = SETTINGS["bar"]
        fmt = ("%H:%M" if b["clock24"] else "%I:%M") + (":%S" if b["seconds"] else "") + ("" if b["clock24"] else " %p")
        self.chips["clock"].set_label(time.strftime(fmt))
        self.chips["clock"].set_visible(b["clock"])
        return True

    def apply(self, st):
        self.load_css()
        B = SETTINGS["bar"]
        # workspace
        wss = {w["id"]: w for w in st.get("workspaces", []) if isinstance(w.get("id"), int) and w["id"] > 0}
        active = st.get("activeWorkspace")
        top = max([B["wsCount"]] + list(wss) + ([active] if isinstance(active, int) and active > 0 else []))
        sig = (top, active, tuple(sorted((k, v["windows"]) for k, v in wss.items())))
        if sig != self.ws_sig:
            self.ws_sig = sig
            for c in self.ws.get_children():
                self.ws.remove(c)
            for i in range(1, top + 1):
                n = wss.get(i, {}).get("windows", 0)
                b = Gtk.Button(label=f"{i} " + "•" * min(n, 3) if n else str(i))
                ctx = b.get_style_context()
                if i == active:
                    ctx.add_class("active")
                if not n:
                    ctx.add_class("empty")
                b.set_tooltip_text(f"Workspace {i}: " + ", ".join(wss[i]["classes"]) if n else f"Workspace {i} " + _t("(trống)"))
                b.connect("clicked", lambda _b, k=i: bg(handle_cmd, {"type": "workspace", "id": k}))
                self.ws.pack_start(b, False, False, 0)
            self.ws.show_all()
        # tiêu đề
        aw = st.get("activeWindow")
        self.title.set_text(f"{aw['class']} — {aw['title']}" if aw else _t("Desktop hành tinh · Super+O để quay lại"))
        # chip
        s = st.get("stats") or {}
        cpu = s.get("cpu")
        self.chips["cpu"].set_label(f"CPU {cpu if cpu is not None else '--'}%")
        ctx = self.chips["cpu"].get_style_context()
        (ctx.add_class if (cpu or 0) >= 80 else ctx.remove_class)("warn")
        self.chips["ram"].set_label(f"RAM {s.get('ramUsed', '--')}GB")
        vol = s.get("volume")
        self.chips["vol"].set_label("VOL " + _t("tắt") if s.get("muted") else f"VOL {vol}%")
        bat = s.get("battery")
        if bat:
            self.chips["bat"].set_label(("⚡" if bat.get("status") == "Charging" else "PIN ") + f"{bat['percent']}%")
        self.chips["cpu"].set_visible(B["cpu"])
        self.chips["ram"].set_visible(B["ram"])
        self.chips["vol"].set_visible(B["volume"] and vol is not None)
        self.chips["bat"].set_visible(B["battery"] and bool(bat))
        # mạng
        if CAPS.get("wifi"):
            ssid = s.get("ssid") or ""
            self.chips["net"].set_label(("WIFI " + (ssid[:12] + "…" if len(ssid) > 13 else ssid)) if s.get("wifi") and ssid
                                        else "WIFI" if s.get("wifi") else "WIFI " + _t("tắt"))
        self.chips["net"].set_visible(bool(CAPS.get("wifi")))
        # nhạc
        m = s.get("media")
        if m:
            self.media_lbl.set_text(("▶ " if m.get("status") == "Playing" else "⏸ ") + (m.get("title") or m.get("player") or _t("Nhạc")))
        self.media_lbl.set_visible(bool(m))
        self.set_art((m or {}).get("artPath") or None)
        self.media_btn.set_visible(bool(m) or not CAVA.silent)
        return False



PANEL_BEAT = 0.0      # lần cuối lớp hiệu ứng báo "còn sống"
PANEL_LAG = 0.0       # khung hình mới nhất của lớp đó cách đây bao lâu (ms)
PANEL_BORN = 0.0


def panel_watchdog():
    """Lớp hiệu ứng (OVERLAY) đôi khi đứng hình: trang không chạy nữa, hoặc vẫn chạy nhưng không được vẽ
    → màn hình kẹt hình cuối (mảnh vỡ, logo…). Phát hiện bằng nhịp tim từ trang và tự tạo lại lớp mới."""
    while True:
        time.sleep(2)
        try:
            now = time.time()
            if _wp_ours_running() and _wp_default_running():
                log("hình nền: bạn vừa chọn hình nền khác → tắt hình nền khoiprOS")
                os_wallpaper_stop()
            if SHELL is None or now - PANEL_BORN < 20 or now - LAST_LOCK < 8 or sh(["pgrep", "-x", "hyprlock"]):
                continue
            silent = now - PANEL_BEAT if PANEL_BEAT else 0
            if silent > 8 or PANEL_LAG > 6000:
                log(f"lớp hiệu ứng đứng hình (im lặng {silent:.0f}s, khung hình trễ {PANEL_LAG:.0f}ms) → tạo lại")
                GLib.idle_add(SHELL.rebuild_panel)
                time.sleep(10)
        except Exception as e:
            log("watchdog lỗi:", e)


WALL_QML = os.path.join(CONF_DIR, "wallpicker.qml")
_QML = {"proc": None, "t": 0.0, "bad": False}


def open_qml_picker():
    """Bảng hình nền bằng quickshell (Qt Quick, card đồ hoạ vẽ thẳng → mượt như bảng của Hyprland).
    Bấm Super+W lần nữa → đóng. Trả False nếu không dùng được (thiếu quickshell / tệp QML / lỗi lần trước)."""
    qs = shutil.which("quickshell") or shutil.which("qs")
    if not qs or not os.path.isfile(WALL_QML) or _QML["bad"]:
        return False
    p = _QML["proc"]
    if p is not None and p.poll() is None:
        p.terminate()   # đang mở → đóng
        _QML["proc"] = None
        return True
    if not _WALLS:
        list_wallpapers()
    try:
        walls = json.dumps(wall_items(), ensure_ascii=False, separators=(",", ":"))
    except Exception:
        walls = "[]"
    # danh sách đã quét sẵn được đưa thẳng cho bảng → hiện ngay, không phải chờ hỏi máy chủ
    env = dict(os.environ, KHOIPROS_PORT=str(PORT), KHOIPROS_TOKEN=TOKEN, KHOIPROS_WALLS=walls,
               KHOIPROS_LANG=SETTINGS["appearance"].get("lang", "vi"),
               KHOIPROS_ACCENT=SETTINGS["appearance"].get("accent") or "#70a1ff")
    logf = open("/tmp/khoipros-wallpicker.log", "w")
    _QML["proc"] = subprocess.Popen([qs, "-p", WALL_QML], env=env, stdout=logf, stderr=subprocess.STDOUT)
    _QML["t"] = time.time()

    def check():
        pr = _QML["proc"]
        if pr is not None and pr.poll() is not None and time.time() - _QML["t"] < 3 and pr.returncode not in (0, None):
            log("bảng hình nền quickshell lỗi (xem /tmp/khoipros-wallpicker.log) → dùng bảng WebKit")
            _QML["bad"] = True
            _QML["proc"] = None
            SHELL.show("wallpaper")
        return False
    GLib.timeout_add(2500, check)
    return True


def first_boot_of_session():
    """Màn hình khởi động chỉ chạy lần đầu trong mỗi phiên đăng nhập — bật/tắt giao diện về sau thì vào thẳng,
    không chiếu lại (lúc khởi động máy đang bận nạp desktop nên hiệu ứng dễ bị giật)."""
    if "--no-boot" in sys.argv:
        return False
    if SETTINGS["appearance"].get("bootEvery"):
        return True
    rd = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    mark = os.path.join(rd, f"khoipros-boot.{os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', 'x')}")
    if os.path.exists(mark):
        return False
    try:
        open(mark, "w").close()
    except Exception:
        pass
    return True


# ====================== Cửa sổ nổi (kéo thả tự do như máy tính thường) ======================
# Chỉ khi đang ở khoiprOS: cửa sổ mới mở ra là nổi (không bị xếp ô dính cứng). Rời khoiprOS / tắt tuỳ chọn
# → những cửa sổ khoiprOS đã thả nổi được xếp lại như cũ (etea / Hyprland vẫn xếp ô bình thường).
# Di chuyển: Super + kéo chuột trái · Đổi cỡ: Super + kéo chuột phải (phím có sẵn của Hyprland).
FLOAT = {"ours": set(), "lock": threading.Lock()}


def _float_on():
    return bool(SETTINGS["behavior"].get("floatWindows", True))


def _monitor_box(mid=None):
    for m in hj("monitors") or []:
        if (mid is None and m.get("focused")) or m.get("id") == mid:
            sc = float(m.get("scale") or 1) or 1
            res = m.get("reserved") or [0, 0, 0, 0]   # trái, trên, phải, dưới (thanh trên giữ chỗ)
            W, H = int(m["width"] / sc), int(m["height"] / sc)
            return m["x"] + res[0], m["y"] + res[1], W - res[0] - res[2], H - res[1] - res[3]
    return None


def float_window(c):
    """Thả nổi 1 cửa sổ đang xếp ô; nếu nó gần như chiếm cả màn hình thì thu lại 70 % và đặt giữa."""
    addr = c.get("address")
    if not addr or c.get("floating") or c.get("fullscreen") or str((c.get("workspace") or {}).get("name", "")).startswith("special"):
        return
    ok, _ = dispatch("togglefloating", "address:" + addr)
    if not ok:
        return
    with FLOAT["lock"]:
        FLOAT["ours"].add(addr)
    box = _monitor_box(c.get("monitor"))
    if not box:
        return
    bx, by, bw, bh = box
    w, h = (c.get("size") or [0, 0])
    if w * h < 0.6 * bw * bh and w > 200 and h > 150:
        return   # cỡ vừa phải → giữ nguyên chỗ
    nw, nh = int(bw * 0.7), int(bh * 0.75)
    # mỗi cửa sổ lệch nhau một chút để không chồng khít lên nhau
    k = len(FLOAT["ours"]) % 5
    nx, ny = bx + (bw - nw) // 2 + (k - 2) * 28, by + (bh - nh) // 2 + (k - 2) * 22
    dispatch("resizewindowpixel", f"exact {nw} {nh},address:{addr}")
    dispatch("movewindowpixel", f"exact {nx} {ny},address:{addr}")


def float_new_window(addr):
    if not _float_on() or SHELL is None:
        return
    time.sleep(0.1)   # đợi Hyprland xếp chỗ xong cho cửa sổ mới
    for c in hj("clients") or []:
        if c.get("address", "").lower() == addr.lower():
            float_window(c)
            break


def float_all():
    for c in hj("clients") or []:
        if c.get("mapped", True) and not c.get("hidden"):
            float_window(c)
    log("cửa sổ nổi: đã thả nổi các cửa sổ đang mở")


def unfloat_ours():
    """Xếp lại ô những cửa sổ do khoiprOS thả nổi (cửa sổ bạn tự thả nổi thì để nguyên)."""
    with FLOAT["lock"]:
        ours, FLOAT["ours"] = set(FLOAT["ours"]), set()
    if not ours:
        return
    for c in hj("clients") or []:
        if c.get("address") in ours and c.get("floating"):
            dispatch("togglefloating", "address:" + c["address"])
    log(f"cửa sổ nổi: đã xếp lại {len(ours)} cửa sổ")


class KkkhoiShell:
    """Thanh trên (TOP) · desktop quả cầu (BOTTOM, không bao giờ bị kéo lên) · lớp bảng (OVERLAY, bấm xuyên qua khi nghỉ)."""
    def __init__(self):
        base = f"http://{HOST}:{PORT}/index.html"
        E = LS.Edge
        boot = SETTINGS["appearance"].get("bootSplash", True) and first_boot_of_session()
        self.cover = self._make_cover() if boot else None   # màn tối phủ kín NGAY LẬP TỨC, trước cả thanh trên
        self.panel_win, self.panel = make_surface("kkkhoishell-panel", LS.Layer.OVERLAY if cairo else LS.Layer.BACKGROUND,
                                                  (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT), 0, None, KB.NONE,
                                                  base + "?surface=panel" + ("&boot=1" if boot else "")
                                                  + (f"&open={ARG_OPEN}" if ARG_OPEN else ""))
        self.bar = GtkBar(self)   # thanh trên tạo sau lớp hiệu ứng → trang màn khởi động bắt đầu nạp sớm hơn
        # desktop (quả cầu 3D, nặng) tạo SAU lớp hiệu ứng → trang màn hình khởi động được nạp trước, hiện sớm hơn
        self.window, self.webview = make_surface("kkkhoishell", LS.Layer.BOTTOM, (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT),
                                                 0, None, KB.ON_DEMAND, base + "?surface=desk")
        self.raised = False
        self._passthrough(True)
        global PANEL_BORN
        PANEL_BORN = time.time()
        if boot:
            self.boot_cover(8)

    def _make_cover(self):
        """Tấm phủ tối GTK thuần: hiện ngay khi khoiprOS vừa chạy (WebKit cần ~1–2 s mới vẽ được), che hình nền
        và thanh trên để màn hình khởi động là thứ ĐẦU TIÊN người dùng thấy. Bỏ đi khi màn hình khởi động đã lên."""
        w = Gtk.Window()
        LS.init_for_window(w)
        LS.set_namespace(w, "kkkhoishell-cover")
        LS.set_layer(w, LS.Layer.OVERLAY)
        for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
            LS.set_anchor(w, e, True)
        LS.set_exclusive_zone(w, -1)
        # tự tô màu bằng cairo (không phụ thuộc theme GTK — có theme làm nền cửa sổ trong suốt)
        w.set_app_paintable(True)
        da = Gtk.DrawingArea()

        def paint(widget, cr):
            cr.set_source_rgb(0x05 / 255, 0x08 / 255, 0x0c / 255)
            cr.paint()
            return True
        da.connect("draw", paint)
        w.add(da)
        prov = Gtk.CssProvider()
        prov.load_from_data(b"window, window * { background-color: #05080c; background-image: none; }")
        for ctx in (w.get_style_context(), da.get_style_context()):
            ctx.add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        mon = Gdk.Display.get_default().get_monitor(0)
        if mon is not None:
            g = mon.get_geometry()
            w.set_default_size(g.width, g.height)
        w.show_all()
        log("tấm phủ khởi động: đã hiện")
        # vẽ tấm phủ NGAY bây giờ, trước khi tạo thanh trên và 2 lớp WebKit (mất ~1 s) → không lộ hình nền/thanh trên
        t_end = time.time() + 0.25
        while time.time() < t_end:
            for _ in range(200):
                if Gtk.events_pending() is not True:
                    break
                Gtk.main_iteration_do(False)
            time.sleep(0.01)
        GLib.timeout_add(7000, self.drop_cover)   # phòng khi màn hình khởi động không chạy được
        return w

    def drop_cover(self):
        if self.cover is not None:
            log("tấm phủ khởi động: bỏ")
            self.cover.destroy()
            self.cover = None
        return False

    def boot_cover(self, secs):
        """Màn hình khởi động phủ TOÀN màn hình, đè cả thanh trên: tạm cho lớp hiệu ứng bỏ qua vùng thanh trên chiếm,
        hết hiệu ứng thì trả lại (để các bảng cài đặt, điều khiển nhanh vẫn nằm dưới thanh trên)."""
        win = self.panel_win
        LS.set_exclusive_zone(win, -1)
        GLib.timeout_add(int(secs * 1000), lambda: LS.set_exclusive_zone(win, 0) or False)
        return False

    def rebuild_panel(self):
        global PANEL_BORN, PANEL_BEAT, PANEL_LAG
        PANEL_BORN, PANEL_BEAT, PANEL_LAG = time.time(), 0.0, 0.0
        """Tạo lại lớp hiệu ứng mới tinh sau khi mở khoá. Lớp cũ (đã ẩn lúc khoá) giữ ảnh ổ khoá cuối cùng
        trong bộ đệm WebKit — hiện lại nó là thấy ổ khoá "đứng hình" ~0,5 s, nên bỏ hẳn, thay bằng lớp mới."""
        old = self.panel_win
        E = LS.Edge
        self.panel_win, self.panel = make_surface("kkkhoishell-panel", LS.Layer.OVERLAY if cairo else LS.Layer.BACKGROUND,
                                                  (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT), 0, None, KB.NONE,
                                                  f"http://{HOST}:{PORT}/index.html?surface=panel")
        self.raised = False
        self.cur_panel = None
        self._passthrough(True)
        GLib.timeout_add(3000, lambda: old.destroy() or False)   # để các lệnh đang gửi tới lớp cũ chạy xong
        return False

    def _passthrough(self, on):
        if cairo:
            self.panel_win.input_shape_combine_region(cairo.Region() if on else None)
        else:
            LS.set_layer(self.panel_win, LS.Layer.BACKGROUND if on else LS.Layer.OVERLAY)
        set_kb(self.panel_win, KB.NONE if on else KB.EXCLUSIVE)

    def show(self, panel=None):
        if not panel:
            return False
        self._passthrough(False)
        self.raised = True
        self.cur_panel = panel
        self.panel.grab_focus()
        run_js(self.panel, f"window.kkkOpenPanel && window.kkkOpenPanel({json.dumps(panel)})")
        log(f"mở bảng {panel}")
        return False

    def hide(self):
        if self.raised:
            self.raised = False
            self.cur_panel = None
            run_js(self.panel, "window.kkkHidden && window.kkkHidden()")
            self._passthrough(True)
            log("đóng bảng")
        return False

    def toggle(self):
        if self.raised:
            return self.hide()
        aw = hj("activeworkspace") or {}
        cur, wins = aw.get("id"), aw.get("windows", 0)
        if wins > 0:
            used = {c.get("workspace", {}).get("id") for c in hypr_clients()}
            target = next(i for i in range(1, 100) if i not in used)
            self.back = cur
            log(f"Super+O: workspace {cur} → workspace trống {target}")
            dispatch("workspace", str(target))
        elif getattr(self, "back", None) is not None:
            log(f"Super+O: quay về workspace {self.back}")
            dispatch("workspace", str(self.back))
            self.back = None
        return False



# ====================== Hiệu ứng mảnh vỡ 3D ======================
# Nghe socket sự kiện của Hyprland (tức thì). Đóng app → cửa sổ vỡ thành mảnh, văng ra rồi nằm lại
# trên desktop. Mở app → các mảnh đang nằm bay về ghép thành cửa sổ.
# Mảnh đang bay vẽ ở lớp bảng (OVERLAY), mảnh nằm lại vẽ ở desktop (BOTTOM, dưới cửa sổ app).
FX_PALETTE = ["#0fb5a8", "#1aa3c4", "#0d7f8f", "#2bd4c0", "#1b6fa8", "#1497b8", "#12c2b0"]


def _r(a, b):
    return random.uniform(a, b)


def _app_color(cls):
    h = 0
    for ch in cls or "":
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, 0.62, 0.78)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


class FxEngine(threading.Thread):
    # v5: mảnh tam giác (2 tam giác / ô), vỡ ra liền mạch không mất mảnh
    def __init__(self):
        super().__init__(daemon=True)
        self.geo, self.active_ws, self.rest, self.nid = {}, None, [], 0
        self.sw, self.sh = 1366, 710
        self.lock = threading.Lock()

    # ---- vị trí cửa sổ ----
    def refresh(self):
        g = {}
        for c in hypr_clients():
            g[c["address"].lower()] = (c["at"][0], c["at"][1], c["size"][0], c["size"][1],
                                       c.get("workspace", {}).get("id"), c.get("class", ""))
        aw = hj("activeworkspace") or {}
        mons = hj("monitors") or []
        m = next((x for x in mons if x.get("focused")), mons[0] if mons else None)
        with self.lock:
            self.geo, self.active_ws = g, aw.get("id")
            if m:
                sc = m.get("scale", 1) or 1
                self.sw, self.sh = int(m["width"] / sc), int(m["height"] / sc) - BAR_H

    def _tick(self):
        while True:
            try:
                self.refresh()
            except Exception as e:
                log("fx refresh lỗi:", e)
            time.sleep(2.0)   # đã cập nhật ngay theo sự kiện, đây chỉ là dự phòng

    def sock_path(self):
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        rt = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        for p in (f"{rt}/hypr/{sig}/.socket2.sock", f"/tmp/hypr/{sig}/.socket2.sock"):
            if sig and os.path.exists(p):
                return p
        return None

    def run(self):
        threading.Thread(target=self._tick, daemon=True).start()
        while True:
            p = self.sock_path()
            if not p:
                log("fx: không tìm thấy socket sự kiện của Hyprland")
                time.sleep(5)
                continue
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(p)
                log("fx: đang nghe sự kiện Hyprland (v5)")
                buf = b""
                while True:
                    d = s.recv(4096)
                    if not d:
                        break
                    buf += d
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            self.on_event(line.decode(errors="ignore"))
                        except Exception as e:
                            log("fx lỗi sự kiện:", e)
            except Exception as e:
                log("fx socket lỗi:", e)
            time.sleep(1)

    @staticmethod
    def _addr(a):
        a = a.strip().lower()
        return a if a.startswith("0x") else "0x" + a

    def on_event(self, line):
        name, _, data = line.partition(">>")
        if name == "closewindow":
            with self.lock:
                g, aws = self.geo.pop(self._addr(data), None), self.active_ws
            if g and g[4] == aws:
                self.shatter(*g[:4], g[5])
        elif name == "openwindow":
            addr = self._addr(data.split(",")[0])
            hid = SETTINGS["fx"]["enabled"] and SETTINGS["fx"].get("hideWin", True) and self.hide(addr)
            if _float_on() and SHELL is not None:
                # thả nổi + đặt chỗ trước, rồi mới ghép mảnh đúng vị trí mới (không bị "nhảy" sau hiệu ứng)
                def go():
                    try:
                        float_new_window(addr)
                    finally:
                        self._opened(addr, hid)
                bg(go)
            else:
                threading.Timer(0.12, self._opened, args=(addr, hid)).start()
        elif name in ("movewindow", "movewindowv2", "changefloatingmode", "workspace", "workspacev2", "fullscreen"):
            bg(self.refresh)

    # ---- giấu cửa sổ thật trong lúc mảnh đang ghép ----
    _HIDE_WAYS = [
        # Hyprland 0.57 (cấu hình Lua): prop "opacity", giá trị là số
        lambda a, v: ["hyprctl", "dispatch", 'hl.dsp.window.set_prop({ window = "address:%s", prop = "opacity", value = %s })'
                      % (a, v if v.replace(".", "", 1).isdigit() else '"%s"' % v)],
        lambda a, v: ["hyprctl", "setprop", "address:" + a, "alpha", v],
        lambda a, v: ["hyprctl", "dispatch", "setprop", "address:" + a, "alpha", v],
        lambda a, v: ["hyprctl", "dispatch", 'hl.dsp.window.set_prop({ window = "address:%s", prop = "alpha", value = "%s" })' % (a, v)],
        lambda a, v: ["hyprctl", "dispatch", 'hl.dsp.window.setprop({ window = "address:%s", prop = "alpha", value = "%s" })' % (a, v)],
    ]
    _hide_way = None
    _hide_bad = False
    _unset_bad = False

    @staticmethod
    def _ok(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            return r.returncode == 0 and r.stdout.strip().lower() == "ok"
        except Exception:
            return False

    # tắt hoạt ảnh riêng cho cửa sổ trong lúc ghép → lúc hiện là hiện ngay, không mờ dần chậm
    _NOANIM = [("no_anim", "true"), ("noanim", "true"), ("no_anim", "1")]
    _noanim_way = None       # None = chưa thử, -1 = máy không hỗ trợ

    def _set_noanim(self, addr, on):
        cands = range(len(self._NOANIM)) if FxEngine._noanim_way is None else ([FxEngine._noanim_way] if FxEngine._noanim_way >= 0 else [])
        for i in cands:
            name, val = self._NOANIM[i]
            v = val if on else ("false" if val == "true" else "0")
            if self._ok(["hyprctl", "dispatch", 'hl.dsp.window.set_prop({ window = "address:%s", prop = "%s", value = %s })' % (addr, name, v)]):
                if FxEngine._noanim_way is None:
                    log("fx: tắt hoạt ảnh cửa sổ bằng", name)
                FxEngine._noanim_way = i
                return True
        if FxEngine._noanim_way is None and on:
            FxEngine._noanim_way = -1
            log("fx: không tắt được hoạt ảnh cửa sổ — cửa sổ sẽ hiện mờ dần theo cài đặt Hyprland")
        return False

    def hide(self, addr):
        if FxEngine._hide_bad:
            return False
        ways = [FxEngine._hide_way] if FxEngine._hide_way is not None else range(len(self._HIDE_WAYS))
        for i in ways:
            if self._ok(self._HIDE_WAYS[i](addr, "0")):
                if FxEngine._hide_way is None:
                    log("fx: giấu cửa sổ bằng cách", i + 1)
                FxEngine._hide_way = i
                self._set_noanim(addr, True)
                return True
        if FxEngine._hide_way is None:
            FxEngine._hide_bad = True
            log("fx: KHÔNG giấu được cửa sổ (hyprctl không nhận setprop)")
        return False

    def reveal(self, addr):
        mk = self._HIDE_WAYS[FxEngine._hide_way or 0]
        if FxEngine._unset_bad or not self._ok(mk(addr, "unset")):
            FxEngine._unset_bad = True
            self._ok(mk(addr, "1"))
        if FxEngine._noanim_way is not None and FxEngine._noanim_way >= 0:   # bật lại hoạt ảnh (để lúc đóng vẫn có)
            threading.Timer(0.4, self._set_noanim, args=(addr, False)).start()
        return False

    def _opened(self, addr, hid=False):
        self.refresh()
        F = SETTINGS["fx"]
        with self.lock:
            g, aws = self.geo.get(addr), self.active_ws
        if g and g[4] == aws and F["enabled"]:
            ms = int(F["assembleMs"])
            if hid:
                # mảnh vừa ghép kín thì cửa sổ hiện ngay bên dưới; mảnh che thêm một chút rồi mờ đi để lộ cửa sổ
                fast = FxEngine._noanim_way is not None and FxEngine._noanim_way >= 0
                cover = 120 if fast else max(120, int(F.get("revealMs", 400)))
                self.assemble(*g[:4], g[5], hold=cover)
                threading.Timer(max(0.05, (ms - 40) / 1000), self.reveal, args=(addr,)).start()
            else:
                self.assemble(*g[:4], g[5])
        elif hid:
            self.reveal(addr)

    # ---- chia cửa sổ thành tam giác ----
    # Mỗi ô lưới = 2 tam giác vuông ghép theo đường chéo (đường chéo chọn ngẫu nhiên → nhìn như mảnh vỡ).
    # Đáy tam giác gốc trong shader: (-.5,-.5) (.5,-.5) (-.5,.5); xoay rz 180 = nửa còn lại của ô.
    def _tris(self, x, y, w, h):
        # "Số mảnh" tính cho cửa sổ cỡ 800×500; cửa sổ to hơn thì nhiều mảnh hơn để mảnh không quá khổ
        n = max(4, int(SETTINGS["fx"]["pieces"]))
        n = int(min(160, n * max(1.0, (w * h) / (800 * 500)) ** 0.85))
        cells = max(2, n // 2)
        cols = max(1, round(math.sqrt(cells * w / max(h, 1))))
        rows = max(1, math.ceil(cells / cols))
        cw, ch = w / cols, h / rows
        th = 0.45 * min(cw, ch)                  # độ cao chóp
        kA = [round(ch / cw, 4), round(th / cw, 4)]
        kB = [round(cw / ch, 4), round(th / ch, 4)]
        out = []
        for i in range(cols):
            for j in range(rows):
                # đường chéo ngẫu nhiên: xoay 0/180 hoặc 90/270 (đổi chiều rộng/cao) → mặt chóp luôn hướng ra ngoài
                if random.random() < 0.5:
                    s, k, rzs = cw, kA, (0, 180)
                else:
                    s, k, rzs = ch, kB, (90, 270)
                for rz in rzs:
                    out.append({"x": x + (i + 0.5) * cw, "y": y + (j + 0.5) * ch, "s": s, "k": k, "ry": 0, "rz": rz})
        return out, max(cw, ch)

    def _color(self, cls):
        return _app_color(cls) if SETTINGS["fx"].get("colorMode") == "app" else random.choice(shard_palette())

    def _send(self, kind, shards, **extra):
        if SHELL:
            payload = json.dumps(dict(kind=kind, shards=shards, **extra))
            GLib.idle_add(lambda: (run_js(SHELL.panel, f"window.kkkFx && window.kkkFx({payload})"), False)[1],
                          priority=GLib.PRIORITY_HIGH)

    def _sweep(self, ms):
        # sau khi hiệu ứng chắc chắn đã xong: bảo lớp hiệu ứng vẽ lại một lần → không còn mảnh "đứng hình"
        def go():
            if SHELL:
                run_js(SHELL.panel, "window.kkkFxSweep && window.kkkFxSweep()")
            return False
        GLib.timeout_add(int(ms), go)

    def push_rest(self):
        if SHELL:
            with self.lock:
                payload = json.dumps(self.rest)
            GLib.idle_add(lambda: (run_js(SHELL.webview, f"window.kkkRestSet && window.kkkRestSet({payload})"), False)[1])

    def shatter(self, x, y, w, h, cls=""):
        F = SETTINGS["fx"]
        if not F["enabled"]:
            return
        y -= BAR_H
        tris, big = self._tris(x, y, w, h)
        shrink = min(1.0, 44 / max(big, 1))
        shards, longest = [], 0
        cx, cy, R = x + w / 2, y + h / 2, max(1.0, math.hypot(w, h) / 2)
        # chỗ nằm rải đều khắp màn hình (lưới có xáo trộn), rồi ghép mỗi mảnh với chỗ nằm cùng hướng tính từ
        # tâm cửa sổ: mảnh gần tâm → chỗ gần, mảnh ở mép → chỗ xa. Vừa bung ra tự nhiên vừa phủ đều màn hình.
        N = len(tris)
        gc = max(1, round(math.sqrt(N * self.sw / max(self.sh, 1))))
        gr = max(1, math.ceil(N / gc))
        gw, gh = (self.sw - 60) / gc, (self.sh - 60) / gr
        cellsxy = [(i, j) for i in range(gc) for j in range(gr)]
        random.shuffle(cellsxy)
        spots = [(30 + (i + _r(0.15, 0.85)) * gw, 30 + (j + _r(0.15, 0.85)) * gh) for i, j in cellsxy[:N]]
        ang = lambda px, py: math.atan2(py - cy, px - cx)
        rad = lambda px, py: math.hypot(px - cx, py - cy)
        order = sorted(range(N), key=lambda k: ang(tris[k]["x"], tris[k]["y"]))
        spots.sort(key=lambda p: ang(*p))
        dest = [None] * N
        G = 6
        for c0 in range(0, N, G):
            grp = sorted(order[c0:c0 + G], key=lambda k: rad(tris[k]["x"], tris[k]["y"]))
            sp = sorted(spots[c0:c0 + G], key=lambda p: rad(*p))
            for k, p in zip(grp, sp):
                dest[k] = p
        for t, (tx, ty) in zip(tris, dest):
            self.nid += 1
            rn = min(1.0, rad(t["x"], t["y"]) / R)                       # 0 = giữa cửa sổ, 1 = mép
            ms = int(F["shatterMs"] * _r(0.8, 1.1))
            longest = max(longest, ms)
            sgn = random.choice((-1, 1))
            shards.append({
                # vết nứt lan từ giữa ra mép: mảnh giữa bung trước, mảnh mép bung sau vài chục ms
                "id": self.nid, "c": self._color(cls), "k": t["k"], "ms": ms, "d": int(rn * 70 + _r(0, 25)),
                "frm": {"x": t["x"], "y": t["y"], "s": t["s"] * 1.02, "rx": 0, "ry": t["ry"], "rz": t["rz"]},
                "to": {"x": tx, "y": ty, "s": t["s"] * shrink * _r(0.75, 1.15),
                       # lộn nhào 1-2 vòng rồi nằm ngửa mặt chóp lên
                       "rx": sgn * 360 * random.randint(1, 2) + _r(-40, 40), "ry": t["ry"] + 360 * random.randint(-1, 1) + _r(-40, 40),
                       "rz": t["rz"] + _r(-540, 540)},
            })
        hold_end = longest + 350          # mảnh bay giữ nguyên tới khi desktop đã vẽ mảnh nằm → không bị mất rồi hiện lại
        self._send("shatter", shards, holdEnd=hold_end)
        self._sweep(hold_end + 400)

        def land():
            with self.lock:
                for s in shards:
                    self.rest.append(dict(s["to"], id=s["id"], c=s["c"], k=s["k"]))
                lim = max(0, int(F["maxRest"]))
                self.rest = self.rest[-lim:] if lim else []
            self.push_rest()
            return False
        GLib.timeout_add(longest + 40, land)

    def assemble(self, x, y, w, h, cls="", hold=0):
        F = SETTINGS["fx"]
        if not F["enabled"]:
            return
        y -= BAR_H
        tris, big = self._tris(x, y, w, h)
        with self.lock:
            random.shuffle(self.rest)
            take = self.rest[:len(tris)]
            self.rest = self.rest[len(tris):]
        self.push_rest()
        shards = []
        ms = int(F["assembleMs"])
        for t in tris:
            if take:
                src = take.pop()
                frm, c, kf, sid = {kk: src[kk] for kk in ("x", "y", "s", "rx", "ry", "rz")}, src["c"], src["k"], src["id"]
            else:
                self.nid += 1
                e = random.randrange(4)
                frm = {"x": -60 if e == 0 else self.sw + 60 if e == 1 else _r(0, self.sw),
                       "y": -60 if e == 2 else self.sh + 60 if e == 3 else _r(0, self.sh),
                       "s": t["s"] * 0.4, "rx": _r(-360, 360), "ry": _r(-360, 360), "rz": _r(-360, 360)}
                c, kf, sid = self._color(cls), t["k"], self.nid
            shards.append({"id": sid, "c": c, "k": t["k"], "kf": kf, "ms": ms, "d": int(ms * _r(0, 0.35)), "frm": frm,
                           "to": {"x": t["x"], "y": t["y"], "s": t["s"] * 1.01, "rx": 0, "ry": t["ry"], "rz": t["rz"]}})
        self._send("assemble", shards, hold=hold)
        self._sweep(int(SETTINGS["fx"]["assembleMs"]) + hold + 700)

    def clear(self):
        with self.lock:
            self.rest = []
        self.push_rest()


FX = FxEngine()



# ====================== Sóng nhạc (cava) ======================
# Chạy `cava` ở chế độ raw, đọc mức âm từng cột (0..100). Vẽ trên thanh trên (GTK) và gửi vòng quanh quả cầu.
CAVA_CONF = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "khoipros-cava.conf")


class CavaEngine(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.vals, self.bars, self.proc, self.silent = [], 0, None, True
        self.last_desk = 0.0

    def _conf(self, bars):
        with open(CAVA_CONF, "w") as f:
            f.write("[general]\nbars = %d\nframerate = 30\nsleep_timer = 2\n"
                    "[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\n"
                    "ascii_max_range = 100\nbar_delimiter = 59\nframe_delimiter = 10\n"
                    "[smoothing]\nnoise_reduction = 70\n" % bars)

    def stop(self):
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None

    def run(self):
        if not shutil.which("cava"):
            log("cava: chưa cài cava → không có sóng nhạc (sudo pacman -S cava)")
            return
        while True:
            C = SETTINGS.get("cava", {})
            if not C.get("enabled", True):
                self.stop(); self.push([0] * max(1, self.bars)); time.sleep(1.5); continue
            bars = max(8, min(128, int(C.get("bars", 48)) // 2 * 2))
            t_start = time.time()
            try:
                self._conf(bars)
                self.bars = bars
                self.proc = subprocess.Popen(["cava", "-p", CAVA_CONF], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                t_start = time.time()
                if not getattr(self, "logged", False):
                    log("cava: đang chạy,", bars, "cột"); self.logged = True
                for line in self.proc.stdout:
                    C = SETTINGS.get("cava", {})
                    if not C.get("enabled", True) or max(8, min(128, int(C.get("bars", 48)) // 2 * 2)) != bars:
                        break                           # tắt hoặc đổi số cột → chạy lại cava
                    try:
                        v = [int(x) / 100 for x in line.strip().strip(";").split(";") if x != ""]
                    except ValueError:
                        continue
                    if v:
                        self.push(v)
            except Exception as e:
                log("cava lỗi:", e)
            self.stop()
            # cava thoát ngay (không có âm thanh / lỗi) → đợi lâu hơn rồi mới thử lại
            time.sleep(1 if time.time() - t_start > 5 else 15)

    def push(self, v):
        sens = float(SETTINGS.get("cava", {}).get("sens", 1.0))
        v = [min(1.0, x * sens) for x in v]
        silent = max(v) < 0.02
        if silent and self.silent:
            return                                       # im lặng → không vẽ gì, đỡ tốn máy
        self.silent, self.vals = silent, v
        C = SETTINGS.get("cava", {})
        if SHELL and C.get("bar", True):
            GLib.idle_add(SHELL.bar.cava_draw)
        if SHELL and C.get("ring", True):
            payload = json.dumps([round(x, 2) for x in v])
            GLib.idle_add(lambda: (run_js_latest(SHELL.webview, "cava", f"window.kkkCava && window.kkkCava({payload})"), False)[1])
        if SHELL and getattr(SHELL, "raised", False) and getattr(SHELL, "cur_panel", None) in ("media", "cc"):
            pl = json.dumps([round(x, 2) for x in v])
            GLib.idle_add(lambda: (run_js_latest(SHELL.panel, "cava", f"window.kkkCava && window.kkkCava({pl})"), False)[1])


CAVA = CavaEngine()

SHELL = None


def _free_port_from_old():
    """Cổng đang bị một khoiprOS cũ giữ (vd. chạy tay bằng "python3 main.py") → tắt bản cũ để bản mới chạy được.
    Chỉ tắt tiến trình là main.py của khoiprOS, không đụng chương trình khác."""
    out = sh(["ss", "-ltnpH", f"sport = :{PORT}"]) or ""
    pids = set(re.findall(r"pid=(\d+)", out))
    if not pids:   # không có ss → tự tìm qua /proc
        inodes = set()
        for tf in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                for line in open(tf).read().splitlines()[1:]:
                    f = line.split()
                    if len(f) > 9 and f[3] == "0A" and int(f[1].rsplit(":", 1)[1], 16) == PORT:
                        inodes.add(f[9])
            except Exception:
                pass
        for d in os.listdir("/proc"):
            if d.isdigit() and inodes:
                try:
                    for fd in os.listdir(f"/proc/{d}/fd"):
                        ln = os.readlink(f"/proc/{d}/fd/{fd}")
                        if ln.startswith("socket:[") and ln[8:-1] in inodes:
                            pids.add(d)
                except Exception:
                    pass
    killed = False
    for pid in pids:
        if int(pid) == os.getpid():
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="ignore")
            cwd = os.path.realpath(f"/proc/{pid}/cwd")
        except Exception:
            continue
        if "main.py" in cmd and ("kkkhoishell" in cmd or os.path.realpath(cwd) == os.path.realpath(CONF_DIR)):
            log(f"cổng {PORT} đang bị khoiprOS cũ (pid {pid}) giữ → tắt bản cũ")
            try:
                os.kill(int(pid), signal.SIGTERM)
                killed = True
            except Exception:
                pass
    return killed


def main():
    global SHELL
    httpd = None
    for attempt in range(3):
        try:
            httpd = Server((HOST, PORT), Handler)
            break
        except OSError as e:
            err = e
            if attempt < 2 and _free_port_from_old():
                time.sleep(1.0)
                continue
            break
    if httpd is None:
        e = err
        log(f"Không mở được cổng {PORT}: {e}")
        log("Có thể http.server của bản cũ còn chạy. Tắt bằng:  pkill -f 'http.server 8888'")
        sys.exit(1)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    POLLER.start()
    SHELL = KkkhoiShell()
    FX.start()
    CAVA.start()
    bg(panel_watchdog)
    if SETTINGS["power"].get("khoiLock", True) and has("hyprlock"):
        bg(write_lock_conf)   # để hypridle cũng dùng được ngay

    def on_usr1(*a):
        log("nhận SIGUSR1 (Super+O)")
        SHELL.toggle()
        return True
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, on_usr1)

    def on_usr2(*a):
        log("nhận SIGUSR2 (Super+S) → bật/tắt thẻ Planet Core")
        run_js(SHELL.webview, "window.kkkToggleCard && window.kkkToggleCard()")
        return True
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, on_usr2)
    def on_term(*a):
        try:
            unfloat_ours()   # rời khoiprOS → cửa sổ xếp ô lại như cũ cho etea / Hyprland
        except Exception:
            pass
        os_wallpaper_stop()   # rời khoiprOS → trả hình nền về như cũ cho etea / Hyprland
        os._exit(0)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, on_term)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, on_term)
    bg(os_wallpaper_start)

    if _float_on():
        bg(lambda: (time.sleep(3), float_all()))

    def _warm_walls():
        time.sleep(4)   # để khởi động xong đã
        wall_items(list_wallpapers())   # quét sẵn danh sách + kích thước + ảnh xem trước cho Super+W
    bg(_warm_walls)

    def on_winch(*a):
        log("nhận SIGWINCH (launch.sh wall) → mở bảng chọn hình nền")
        if not open_qml_picker():
            SHELL.show("wallpaper")   # không có quickshell → dùng bảng trong WebKit
        return True
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGWINCH, on_winch)

    def on_hup(*a):
        log("nhận SIGHUP (launch.sh lock) → khoá màn hình có hiệu ứng")
        lock_with_anim()
        return True
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, on_hup)
    log(f"Sẵn sàng trên http://{HOST}:{PORT} — công cụ có sẵn: {', '.join(k for k, v in CAPS.items() if v) or 'không'}")
    Gtk.main()


if __name__ == "__main__":
    main()
