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
# 自检入口已统一为 main.py --selftest（旧架构的 python -m core.selftest 已删除）
python main.py --selftest || true
echo
echo "启动（Termux 无 X11/WebView，3D 窗口不可显示，自动退化为轻量模式）："
echo "  python main.py --no-web            # 命令行对话（gRPC 端口默认 50051）"
echo "  python main.py --status            # 打印引擎状态后退出"
echo "  消息平台机器人请在应用内「设置 → 通道」配置 Telegram/Discord 等，"
echo "  无需额外命令行参数；成长闭环与离线出图在轻量模式下仍可用。"
