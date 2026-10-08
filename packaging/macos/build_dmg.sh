#!/usr/bin/env bash
# 小凌 macOS DMG 本地构建脚本
#
# 说明：官方发布的 xiaoling-macos.dmg 由 .github/workflows/build-all.yml 在
# macos-latest 上产出。本脚本是本地复现：Flutter macOS + PyInstaller(main.py)
# 后端 → 塞进 .app → hdiutil 打 DMG。在仓库根目录运行：
#   bash packaging/macos/build_dmg.sh
set -euo pipefail

VERSION="0.0.1"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

echo "=== 打包小凌 macOS DMG v${VERSION} ==="

# 1. 构建 Flutter macOS 前端
echo "[1/4] 构建 Flutter macOS 应用..."
(cd frontend && flutter pub get && flutter build macos --release)

# 2. 构建 Python 后端（onefile，入口 main.py）
echo "[2/4] 构建 Python 后端..."
pyinstaller --onefile --name backend --clean main.py

# 3. 把后端塞进 .app 的 Contents/MacOS
echo "[3/4] 组装 .app..."
APP_PATH="$(find frontend/build/macos/Build/Products/Release -maxdepth 1 -name '*.app' | head -1)"
if [ -z "$APP_PATH" ]; then
  echo "找不到 .app，Flutter 构建可能失败"; exit 1
fi
cp dist/backend "$APP_PATH/Contents/MacOS/backend"
chmod +x "$APP_PATH/Contents/MacOS/backend"

# 4. 打 DMG（产物名与官网一致：xiaoling-macos.dmg）
echo "[4/4] 创建 DMG..."
OUT="$ROOT/xiaoling-macos.dmg"
hdiutil create -volname "小凌 XIAOLING" -srcfolder "$(dirname "$APP_PATH")" \
  -ov -format UDZO "$OUT"

if [ -n "${APPLE_DEVELOPER_ID:-}" ]; then
  codesign --deep --force --verify --verbose --sign "$APPLE_DEVELOPER_ID" "$APP_PATH"
  echo "签名完成"
else
  echo "跳过签名（未设置 APPLE_DEVELOPER_ID）；首次打开需右键→打开。"
fi
echo "=== 完成：$OUT ==="
