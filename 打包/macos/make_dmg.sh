#!/usr/bin/env bash
# macOS：打包 .app 并（可选）生成 .dmg
set -e
cd "$(dirname "$0")/../.."
python3 -m pip install -r requirements.txt pyinstaller
python3 打包/build.py --clean
# 未做公证时，首次打开需右键 → 打开，或：
#   xattr -dr com.apple.quarantine dist/小凌.app
hdiutil create -volname "小凌 XIAOLING" -srcfolder "dist/小凌.app" -ov -format UDZO dist/xiaoling-0.0.2.dmg || true
echo "完成：dist/小凌.app  （如需 dmg 见上）"
echo "提示：麦克风/录屏权限首次会弹窗（语音输入、看屏幕需要）"
