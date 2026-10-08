#!/usr/bin/env bash
# 小凌 Linux AppImage 打包脚本
set -e

VERSION="0.0.4"
APP_NAME="XiaoLing"

echo "=== 打包小凌 Linux AppImage v${VERSION} ==="

# 1. 构建 Flutter
echo "[1/5] 构建 Flutter Linux 应用..."
cd ../frontend
flutter build linux --release
cd ../../packaging/linux

# 2. 构建 Python 后端
echo "[2/5] 构建 Python 后端..."
cd ../../
pyinstaller --onefile --name xiaoling_backend \
    --add-data "resources:resources" \
    backend/rpc/server.py

# 3. 创建 AppDir 结构
echo "[3/5] 创建 AppDir..."
APPDIR="AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# 复制文件
cp dist/xiaoling_backend "$APPDIR/usr/bin/"
cp -r resources "$APPDIR/usr/bin/"

# 桌面文件
cat > "$APPDIR/usr/share/applications/xiaoling.desktop" << EOF
[Desktop Entry]
Name=XiaoLing
Comment=你的专属AI伙伴
Exec=xiaoling
Icon=xiaoling
Type=Application
Categories=Utility;AI;
EOF

# AppRun
cat > "$APPDIR/AppRun" << EOF
#!/bin/bash
SELF=\$(readlink -f "\$0")
HERE=\${SELF%/*}
export PATH="\$HERE/usr/bin:\$PATH"
exec "\$HERE/usr/bin/xiaoling" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

# 4. 打包 AppImage
echo "[4/5] 打包 AppImage..."
if [ -f linuxdeploy-x86_64.AppImage ]; then
    ./linuxdeploy-x86_64.AppImage --appdir "$APPDIR" --output appimage
else
    echo "请先下载 linuxdeploy: https://github.com/linuxdeploy/linuxdeploy/releases"
fi

# 5. 重命名
echo "[5/5] 重命名..."
mv XiaoLing-"$VERSION"-x86_64.AppImage "XiaoLing-${VERSION}.AppImage" 2>/dev/null || true

echo "=== 打包完成: XiaoLing-${VERSION}.AppImage ==="
