#!/usr/bin/env bash
# 小凌 Linux AppImage 本地构建脚本
#
# 说明：官方发布的 XiaoLing-x86_64.AppImage 由 .github/workflows/build-all.yml
# 在 Ubuntu 上矩阵产出。本脚本是**本地复现**用的等价流程，逻辑与 CI 对齐：
#   Flutter Linux 前端 + PyInstaller(onefile, main.py) 后端 → 合并 → linuxdeploy 打包。
# 在仓库根目录运行： bash packaging/linux/build_appimage.sh
set -euo pipefail

VERSION="0.0.1"
APP_NAME="XiaoLing"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

echo "=== 打包小凌 Linux AppImage v${VERSION} ==="

# 1. 构建 Flutter Linux 前端
echo "[1/4] 构建 Flutter Linux 应用..."
(cd frontend && flutter pub get && flutter build linux --release)
BUNDLE="$ROOT/frontend/build/linux/x64/release/bundle"

# 2. 构建 Python 后端（单文件 onefile，入口 main.py；与 CI 一致）
#    关键：必须走 packaging/backend.spec，它才会显式收集 VRM 模型、动作库、
#    resources/web 查看器、内置插件、proto 契约与 llama_cpp(GGUF) 运行时。
#    裸 `pyinstaller main.py` 会让后端缺资源：3D 黑屏、插件全废、GGUF 加载即崩。
echo "[2/4] 构建 Python 后端（backend.spec, onefile）..."
XIAOLING_ONEFILE=1 python -m PyInstaller packaging/backend.spec --noconfirm \
    --distpath dist --workpath build/pyi

# 3. 组装 AppDir（AppRun 约定主程序在 usr/bin/xiaoling/xiaoling）
echo "[3/4] 组装 AppDir..."
APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR"
APPDIR_BIN="$APPDIR/usr/bin/xiaoling"
mkdir -p "$APPDIR_BIN"
cp -r "$BUNDLE/"* "$APPDIR_BIN/"
# onedir 产物在 dist/backend/backend；onefile 产物直接是 dist/backend。
if [ -f "$ROOT/dist/backend/backend" ]; then
  cp "$ROOT/dist/backend/backend" "$APPDIR_BIN/backend"
else
  cp "$ROOT/dist/backend" "$APPDIR_BIN/backend"
fi
chmod +x "$APPDIR_BIN/backend"

cp "$HERE/xiaoling.desktop" "$APPDIR/xiaoling.desktop" 2>/dev/null || true
if [ -f "$HERE/AppRun" ]; then
  cp "$HERE/AppRun" "$APPDIR/AppRun" && chmod +x "$APPDIR/AppRun"
fi

# 4. 用 linuxdeploy 打包（未装则提示下载）
echo "[4/4] 打包 AppImage..."
if [ -f "$ROOT/linuxdeploy-x86_64.AppImage" ]; then
  (cd "$ROOT" && ./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" --output appimage)
  OUT="$ROOT/$APP_NAME-x86_64.AppImage"
  [ -f "$ROOT/${APP_NAME}-x86_64.AppImage" ] && mv "$ROOT/${APP_NAME}-x86_64.AppImage" "$OUT" 2>/dev/null || true
  echo "完成：$OUT"
else
  echo "未找到 linuxdeploy-x86_64.AppImage，跳过打包。"
  echo "下载：https://github.com/linuxdeploy/linuxdeploy/releases 放到仓库根目录后重跑。"
  echo "已就绪的 AppDir：$APPDIR"
fi
