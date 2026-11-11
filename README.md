# khoiprOS

**English** · [Tiếng Việt](README.vi.md)

An OS-style desktop shell for **Hyprland**: a 3D planet home screen, a status bar, quick controls, a music player with a cava visualizer, a full-screen power menu, glass-shatter window effects, and animated boot and lock screens.

> khoipr**OS** = khoipro + OS

## Install (one command)

Run this in a terminal **inside a Hyprland session**:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/deptraicodengu/khoipros/main/install.sh)
```

The installer asks before changing anything and then:

1. **Checks for Hyprland.** If it is missing, it offers to install it with your package manager and tells you to log in to a Hyprland session and run the command again.
2. **Installs missing packages** with `pacman`, `apt`, `dnf` or `zypper`. Packages your distro does not have are skipped and listed (see [Compatibility](#compatibility)).
3. **Copies khoiprOS** to `~/.config/kkkhoishell`. Your settings are kept on update.
4. **Adds key bindings** to `hyprland.conf` or `hyprland.lua` (a backup is made first; nothing existing is edited, lines are only appended):
   - **Super+O**: show or hide khoiprOS
   - **Super+L**: lock the screen with the animated lock screen
   - **Super+W**: open the wallpaper picker
   - Keys you already use for something else are left alone; the installer prints the command so you can bind it yourself.
   - khoiprOS starts automatically when you log in.
5. **Starts khoiprOS.**

**Update:** run the same command again.
**Uninstall:** `~/.config/kkkhoishell/uninstall.sh` (removes the key bindings too; add `--all` to also delete your settings).

## Compatibility

khoiprOS needs **Linux + Hyprland**. It does not run on Windows or macOS, and it does not run inside KDE, GNOME or other desktops — you must log in to a Hyprland session.

| System | Works? |
|---|---|
| **Arch Linux** and Arch-based (Manjaro, EndeavourOS, CachyOS…) | Yes, every feature. This is where khoiprOS is developed and tested. |
| **Debian / Ubuntu**, **Fedora**, **openSUSE** | Yes. Some optional packages may not be in your distro's repositories — see the table below. |
| **Other Linux** (NixOS, Gentoo, Void…) | khoiprOS installs, but the installer cannot install packages for you. Install Hyprland and the packages below yourself, then run the command. |
| **Windows / macOS** | No. Hyprland only exists on Linux. |

### Required

Without these khoiprOS cannot start, and the installer stops with a clear message:

- Hyprland
- Python 3 with GObject (PyGObject), GTK 3, gtk-layer-shell
- WebKit2GTK (4.1 or 4.0) and pycairo

### Optional — what you lose without each one

| Package | Without it |
|---|---|
| **quickshell** | Super+W still opens the wallpaper picker, but the fallback version (same look) scrolls less smoothly. |
| **hyprlock** | No khoiprOS lock screen (glass padlock, clock, greeting). Super+L uses the lock command set in *Settings › Power & Notifications*. |
| **awww** or **swww** | khoiprOS cannot change the wallpaper. The picker opens, but choosing an image does nothing. |
| **cava** | No music visualizer on the bar or around the planet. |
| **playerctl** | The bar does not show the song that is playing. |
| brightnessctl, nmcli, bluetoothctl, wpctl/pamixer, powerprofilesctl | The matching button in quick controls is greyed out. |

Everything else always works: the 3D planet and app planets, the status bar, quick controls, settings, glass-shatter effects, the boot screen, floating windows and both languages.

If your distro lacks an optional package, install it from that project's own instructions and run the install command again.

## Features

- **3D planet home screen:** pinned apps (Terminal, Brave, Firefox, Code, Store… — edit them in *Settings › Apps*) sit on the inner orbit and launch with one click; every other open window becomes a planet on the outer orbit. All planets use the app's real icon. Hide or show the planet with the **Planet** button at the bottom.
- **Status bar:** workspaces, now playing (cover art + cava), network, volume, battery, clock.
- **Quick controls:** Wi-Fi, Bluetooth, volume, brightness, power profile, do not disturb.
- **Glass-shatter effects** when windows open and close.
- **Boot screen:** shards assemble into the khoiprOS logo every time you switch to khoiprOS.
- **Lock screen (Super+L):** a padlock assembles from glass shards, then fades into a hyprlock screen themed with your accent color and wallpaper.
- **Wallpaper picker (Super+W):** a 3D coverflow of landscape cards with image info and search. ←/→ or the mouse wheel to browse, Enter to apply, Esc or Super+W to close. Put images in **`~/Pictures/khoipros`**. The khoiprOS wallpaper is only used while khoiprOS is running.
- **Automatic colors:** the planet and orbits always stand out from the wallpaper.
- **Floating windows:** windows are not locked into tiles. Super + left-drag moves a window, Super + right-drag resizes it (*Settings › Behavior*). Switching back to another Hyprland setup tiles them again. The Settings window can also be dragged and resized.
- **English / Tiếng Việt:** the UI starts in English unless your system locale is Vietnamese. Change it in *Settings › khoiprOS › Language*.

## Troubleshooting

- Logs: `tail -f /tmp/kkkhoishell.log`
- Wallpaper picker log: `cat /tmp/khoipros-wallpicker.log`
- Lock screen broken? Press Ctrl+Alt+F3, log in, run `pkill -USR1 hyprlock`, then turn off "khoiprOS lock screen" in *Settings › Power & Notifications*.

## License

MIT © Khoi
