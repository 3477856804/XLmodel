#!/usr/bin/env bash
# 小凌 Linux 运行期系统依赖（GL / 软件光栅 / 音频 / 桌面托盘）
set -e
echo "== 安装小凌的 Linux 系统依赖 =="
SUDO=""; [ "$(id -u)" != "0" ] && SUDO="sudo"
if command -v apt-get >/dev/null; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y libgl1 libglx-mesa0 libgl1-mesa-dri libosmesa6 \
      espeak-ng alsa-utils ffmpeg libxcb-cursor0 libxkbcommon-x11-0 \
      libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-randr0 || true
elif command -v dnf >/dev/null; then
  $SUDO dnf install -y mesa-libGL mesa-dri-drivers mesa-libOSMesa espeak-ng alsa-utils ffmpeg || true
elif command -v pacman >/dev/null; then
  $SUDO pacman -Sy --noconfirm mesa osmesa espeak-ng alsa-utils ffmpeg || true
fi
echo "== 完成。运行： ./dist/xiaoling/xiaoling =="
