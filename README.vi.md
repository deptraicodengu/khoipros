# khoiprOS

[English](README.md) · **Tiếng Việt**

Giao diện desktop kiểu "hệ điều hành" cho **Hyprland**: hành tinh 3D làm màn hình chính, thanh trạng thái, điều khiển nhanh, trình phát nhạc có sóng cava, menu nguồn toàn màn hình, hiệu ứng vỡ kính khi mở/đóng cửa sổ, màn hình khởi động và màn hình khoá có hiệu ứng.

> khoipr**OS** = khoipro + OS

## Cài đặt (một lệnh)

Chạy lệnh này trong terminal, **khi đang ở trong phiên Hyprland**:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
```

Bộ cài hỏi trước khi thay đổi bất cứ thứ gì, rồi:

1. **Kiểm tra Hyprland.** Nếu chưa có, nó đề nghị cài bằng trình quản lý gói của máy, rồi hướng dẫn bạn đăng nhập vào phiên Hyprland và chạy lại lệnh.
2. **Cài các gói còn thiếu** bằng `pacman`, `apt`, `dnf` hoặc `zypper`. Gói nào kho của distro không có thì bỏ qua và liệt kê ra (xem [Tương thích](#tương-thích)).
3. **Chép khoiprOS** vào `~/.config/kkkhoishell`. Khi cập nhật, cài đặt của bạn được giữ nguyên.
4. **Thêm phím tắt** vào `hyprland.conf` hoặc `hyprland.lua` (sao lưu trước; không sửa dòng nào có sẵn, chỉ thêm vào cuối):
   - **Super+O**: hiện/ẩn khoiprOS
   - **Super+L**: khoá màn hình có hiệu ứng
   - **Super+W**: mở bảng chọn hình nền
   - Phím nào đã dùng cho việc khác thì giữ nguyên; bộ cài in ra lệnh để bạn tự gắn.
   - khoiprOS tự chạy khi đăng nhập.
5. **Bật khoiprOS.**

**Cập nhật:** chạy lại đúng lệnh trên.
**Gỡ:** `~/.config/kkkhoishell/uninstall.sh` (bỏ luôn phím tắt; thêm `--all` để xoá cả cài đặt).

## Tương thích

khoiprOS cần **Linux + Hyprland**. Không chạy trên Windows hay macOS, và không chạy bên trong KDE, GNOME hay desktop khác — bạn phải đăng nhập vào phiên Hyprland.

| Hệ điều hành | Dùng được? |
|---|---|
| **Arch Linux** và distro dựa trên Arch (Manjaro, EndeavourOS, CachyOS…) | Được, đủ mọi tính năng. khoiprOS được làm và thử trên Arch. |
| **Debian / Ubuntu**, **Fedora**, **openSUSE** | Được. Một số gói tuỳ chọn có thể không có trong kho của distro — xem bảng bên dưới. |
| **Linux khác** (NixOS, Gentoo, Void…) | Cài được khoiprOS, nhưng bộ cài không tự cài gói. Tự cài Hyprland và các gói bên dưới rồi chạy lệnh. |
| **Windows / macOS** | Không. Hyprland chỉ có trên Linux. |

### Bắt buộc

Thiếu những thứ này thì khoiprOS không mở được, và bộ cài sẽ dừng lại báo rõ:

- Hyprland
- Python 3 với GObject (PyGObject), GTK 3, gtk-layer-shell
- WebKit2GTK (4.1 hoặc 4.0) và pycairo

### Tuỳ chọn — thiếu gói nào thì mất gì

| Gói | Nếu thiếu |
|---|---|
| **quickshell** | Super+W vẫn mở bảng chọn hình nền, nhưng là bản dự phòng (cùng giao diện) lướt kém mượt hơn. |
| **hyprlock** | Không có màn khoá khoiprOS (ổ khoá kính, đồng hồ, lời chào). Super+L dùng lệnh khoá đặt trong *Cài đặt › Nguồn & Thông báo*. |
| **awww** hoặc **swww** | khoiprOS không đổi được hình nền. Bảng chọn vẫn mở, nhưng chọn ảnh thì nền không đổi. |
| **cava** | Không có sóng nhạc trên thanh và quanh quả cầu. |
| **playerctl** | Thanh trên không hiện bài đang phát. |
| brightnessctl, nmcli, bluetoothctl, wpctl/pamixer, powerprofilesctl | Nút tương ứng trong điều khiển nhanh bị mờ. |

Những thứ luôn chạy: quả cầu 3D và các hành tinh app, thanh trạng thái, điều khiển nhanh, cài đặt, hiệu ứng vỡ kính, màn hình khởi động, cửa sổ nổi và cả hai ngôn ngữ.

Nếu distro của bạn thiếu gói tuỳ chọn nào, cài gói đó theo hướng dẫn của chính dự án đó rồi chạy lại lệnh cài.

## Tính năng

- **Màn hình chính hành tinh 3D:** các app ghim (Terminal, Brave, Firefox, Code, Store… — sửa trong *Cài đặt › Ứng dụng*) nằm trên vòng trong, bấm một cái là mở; mọi cửa sổ khác thành hành tinh ở vòng ngoài. Hành tinh nào cũng mang icon thật của app. Ẩn/hiện quả cầu bằng nút **Quả cầu** ở góc dưới.
- **Thanh trạng thái:** workspace, nhạc đang phát (ảnh bìa + cava), mạng, âm lượng, pin, đồng hồ.
- **Điều khiển nhanh:** Wi-Fi, Bluetooth, âm lượng, độ sáng, chế độ nguồn, không làm phiền.
- **Hiệu ứng vỡ kính** khi mở và đóng cửa sổ.
- **Màn hình khởi động:** các mảnh kính ghép thành logo khoiprOS mỗi lần bạn chuyển sang khoiprOS.
- **Màn hình khoá (Super+L):** ổ khoá ghép từ mảnh kính, rồi mờ dần sang màn khoá hyprlock theo màu nhấn và hình nền của bạn.
- **Chọn hình nền (Super+W):** dải ảnh ngang kiểu coverflow 3D, có thông tin ảnh và ô tìm kiếm. ←/→ hoặc lăn chuột để lướt, Enter để đặt, Esc hoặc Super+W để đóng. Bỏ ảnh vào **`~/Pictures/khoipros`**. Hình nền khoiprOS chỉ dùng khi đang ở khoiprOS.
- **Màu tự động:** quả cầu và quỹ đạo luôn nổi bật trên hình nền.
- **Cửa sổ nổi:** cửa sổ không bị xếp ô dính cứng. Super + kéo chuột trái để di chuyển, Super + kéo chuột phải để đổi cỡ (*Cài đặt › Hành vi*). Chuyển về giao diện Hyprland khác thì cửa sổ xếp ô lại. Cửa sổ Cài đặt cũng kéo và đổi cỡ được.
- **English / Tiếng Việt:** giao diện mặc định là tiếng Anh, trừ khi máy bạn đặt ngôn ngữ tiếng Việt. Đổi trong *Cài đặt › khoiprOS › Ngôn ngữ*.

## Gặp lỗi?

- Nhật ký: `tail -f /tmp/kkkhoishell.log`
- Nhật ký bảng chọn hình nền: `cat /tmp/khoipros-wallpicker.log`
- Màn khoá lỗi? Bấm Ctrl+Alt+F3, đăng nhập, chạy `pkill -USR1 hyprlock`, rồi tắt "Màn hình khoá khoiprOS" trong *Cài đặt › Nguồn & Thông báo*.

## Giấy phép

MIT © Khoi
