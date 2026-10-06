#!/usr/bin/env bash
# 小凌 macOS DMG 打包脚本
set -e

VERSION="0.0.4"
APP_NAME="XiaoLing"

echo "=== 打包小凌 macOS DMG v${VERSION} ==="

# 1. 构建 Flutter
echo "[1/5] 构建 Flutter macOS 应用..."
cd ../frontend
flutter build macos --release
cd ../../packaging/macos

# 2. 构建 Python 后端
echo "[2/5] 构建 Python 后端..."
cd ../../
pyinstaller --onefile --name xiaoling_backend \
    --add-data "resources:resources" \
    backend/rpc/server.py

# 3. 组装 .app 包
echo "[3/5] 组装 .app 包..."
APP_PATH="build/macos/${APP_NAME}.app"
mkdir -p "${APP_PATH}/Contents/MacOS"
cp dist/xiaoling_backend "${APP_PATH}/Contents/MacOS/"
cp -r resources "${APP_PATH}/Contents/MacOS/"

# 4. 创建 DMG
echo "[4/5] 创建 DMG..."
hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${APP_PATH}" \
    -ov -format UDZO \
    "XiaoLing-${VERSION}.dmg"

# 5. 签名（如果有证书）
echo "[5/5] 签名..."
if [ -n "$APPLE_DEVELOPER_ID" ]; then
    codesign --deep --force --verify --verbose \
        --sign "$APPLE_DEVELOPER_ID" \
        "${APP_PATH}"
    echo "签名完成"
else
    echo "跳过签名（未配置开发者证书）"
fi

echo "=== 打包完成: XiaoLing-${VERSION}.dmg ==="
