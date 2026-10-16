#!/usr/bin/env bash
# 小凌 Linux 运行期系统依赖（GL / 软件光栅 / 音频 / 桌面托盘 / 3D WebView）
set -e
echo "== 安装小凌的 Linux 系统依赖 =="
SUDO=""; [ "$(id -u)" != "0" ] && SUDO="sudo"
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y libgl1 libglx-mesa0 libgl1-mesa-dri libosmesa6 \
      espeak-ng alsa-utils ffmpeg libxcb-cursor0 libxkbcommon-x11-0 \
      libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-randr0 || true
  # 真 3D：flutter_inappwebview 的 Linux 实现走 WPE WebKit。
  # 缺了它，桌面端会退化成 2D 占位（不会崩，但看不到 3D 形象）。
  $SUDO apt-get install -y libwebkit2gtk-4.1-0 libwpewebkit-1.1-3 \
      libwpe-1.0-1 wpebackend-fdo || echo "  [提示] WPE WebKit 未装上，3D 将降级为 2D"
elif command -v dnf >/dev/null; then
  $SUDO dnf install -y mesa-libGL mesa-dri-drivers mesa-libOSMesa espeak-ng alsa-utils ffmpeg || true
  $SUDO dnf install -y webkit2gtk4.1 wpewebkit libwpe wpebackend-fdo || \
      echo "  [提示] WPE WebKit 未装上，3D 将降级为 2D"
elif command -v pacman >/dev/null; then
  $SUDO pacman -Sy --noconfirm mesa osmesa espeak-ng alsa-utils ffmpeg || true
  $SUDO pacman -Sy --noconfirm webkit2gtk-4.1 wpewebkit libwpe wpebackend || \
      echo "  [提示] WPE WebKit 未装上，3D 将降级为 2D"
fi
echo "== 完成。运行： ./dist/xiaoling/xiaoling =="
