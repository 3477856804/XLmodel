#!/data/data/com.termux/files/usr/bin/bash
# 小凌 · Termux（Android）安装脚本
# 说明：Termux 里没有 X11/WebView，3D 窗口无法显示。
#       小凌会自动退化：软件渲染（离屏出图）+ 命令行对话 + 平台机器人 + 成长闭环，
#       形象可用 `python -m renderer.app --showcase preview` 离线出图查看。
set -e
echo "== 1/3 系统包 =="
pkg update -y
pkg install -y python python-pip git libjpeg-turbo libpng zlib freetype libomp \
               clang rust binutils espeak
echo "== 2/3 Python 依赖（Termux 用预编译 torch） =="
pkg install -y python-numpy python-pillow || pip install --no-build-isolation numpy pillow
pkg install -y python-torch || echo "（无预编译 torch，将只启用轻量模式）"
pip install --no-build-isolation pyttsx3 sounddevice 2>/dev/null || true
echo "== 3/3 收尾 =="
python -m core.selftest || true
echo
echo "启动："
echo "  python xl.py --no-pet          # 命令行对话（3D/2D 桌宠都不支持）"
echo "  python xl.py --platform telegram   # 接消息平台当机器人用"
echo "  python -m renderer.app --showcase preview   # 离线渲染形象图"
