# khoiprOS

**[English](#english)** · Tiếng Việt

Giao diện desktop kiểu "hệ điều hành" cho **Hyprland**: hành tinh 3D làm màn hình chính, thanh trạng thái, trung tâm điều khiển, trình phát nhạc có cava, menu nguồn toàn màn hình, hiệu ứng vỡ kính khi mở/đóng cửa sổ, màn hình khởi động và màn hình khoá có hiệu ứng.

> khoipr**OS** = khoipro + OS

## Cài đặt — một lệnh

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
```

Lệnh này tự làm hết:

1. Kiểm tra và cài các gói cần thiết bằng pacman (hỏi bạn trước).
2. Tải khoiprOS về `~/.config/kkkhoishell`.
3. Thêm phím tắt vào cấu hình Hyprland, hỗ trợ cả `hyprland.conf` lẫn `hyprland.lua`, có sao lưu:
   - **Super+O**: mở/ẩn khoiprOS.
   - **Super+L**: khoá màn hình có hiệu ứng.
   - **Super+W**: chọn hình nền.
   - Phím nào máy đã dùng cho việc khác thì giữ nguyên, không đè.
   - Tự chạy khoiprOS khi đăng nhập.
4. Bật khoiprOS luôn.

**Cập nhật:** chạy lại đúng lệnh trên. Cài đặt của bạn được giữ nguyên.
**Gỡ:** `~/.config/kkkhoishell/uninstall.sh`. Lệnh này bỏ luôn phím tắt; thêm `--all` để xoá cả cài đặt.

## Tính năng

- **Hành tinh 3D:** mỗi cửa sổ đang mở là một hành tinh, dùng icon thật của app.
- **Thanh trạng thái:** workspace, nhạc đang phát (ảnh bìa + sóng cava), mạng, âm lượng, pin, đồng hồ.
- **Trung tâm điều khiển:** Wi-Fi, Bluetooth, âm lượng, độ sáng, chế độ nguồn, không làm phiền.
- **Hiệu ứng vỡ kính 3D** khi mở/đóng cửa sổ.
- **Màn hình khởi động:** các mảnh ghép lại thành logo.
- **Màn hình khoá:** dùng hyprlock, ổ khoá ghép từ mảnh kính, theo màu nhấn và hình nền.
- **Chọn hình nền: Super+W** mở bảng ảnh xếp kiểu coverflow 3D (←/→ hoặc lăn chuột để lướt, Enter để đặt, ảnh vỡ thành mảnh kính khi đổi). Bỏ ảnh vào thư mục **`~/Pictures/khoipros`** là có trong bảng. Cũng có trong Cài đặt › Màu sắc: lưới ảnh xem trước từ ~/Pictures, /usr/share/backgrounds…; hình nền này chỉ dùng khi đang ở khoiprOS.
- **Màu tự động theo hình nền:** quả cầu và quỹ đạo luôn nổi bật trên hình nền.
- **Cửa sổ nổi:** trong khoiprOS cửa sổ không bị xếp ô cứng; Super + kéo chuột trái để di chuyển, Super + kéo chuột phải để đổi cỡ (tắt được trong Cài đặt › Hành vi). Cửa sổ Cài đặt cũng kéo/đổi cỡ được.
- **Bật/tắt quả cầu** giữa màn hình bằng nút "Quả cầu" ở góc dưới.
- **Tiếng Việt / English:** đổi trong *Cài đặt › khoiprOS*.

## Gặp lỗi?

- Xem nhật ký: `tail -f /tmp/kkkhoishell.log`.
- Màn hình khoá lỗi? Bấm Ctrl+Alt+F3, đăng nhập, chạy `pkill -USR1 hyprlock`, rồi tắt "Màn hình khoá khoiprOS" trong Cài đặt › Nguồn.

## Giấy phép

MIT © Khoi

---

## English

khoiprOS is an OS-style desktop shell for **Hyprland**:

- a 3D planet home screen where every window is a planet;
- a status bar, quick controls, and a music player with a cava visualizer;
- glass-shatter window effects, a boot screen, and an animated lock screen.

**Install (one command):**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
```

The installer does the following:

1. Checks dependencies and offers to install them with pacman.
2. Installs khoiprOS to `~/.config/kkkhoishell`.
3. Adds key bindings to `hyprland.conf` or `hyprland.lua`, with a backup:
   - **Super+O** opens or hides khoiprOS.
   - **Super+L** locks the screen, **Super+W** opens the wallpaper picker (put images in `~/Pictures/khoipros`). Keys that are already in use are left alone.
   - khoiprOS starts automatically at login.
4. Starts khoiprOS.

In khoiprOS, windows float freely: Super + left-drag moves them, Super + right-drag resizes them (Settings › Behavior). The planet can be hidden with the "Planet" button at the bottom.

The UI starts in English unless your system locale is Vietnamese. You can switch it in *Settings › khoiprOS › Language*.

To update, run the same command again. To remove, run `~/.config/kkkhoishell/uninstall.sh`. Logs are in `/tmp/kkkhoishell.log`.
