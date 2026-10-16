#!/usr/bin/env bash
# macOS：构建并生成 DMG（入口与 packaging/macos/build_dmg.sh 保持一致）
# 历史版本这里调用 build.py 产出 dist/小凌.app，但当前统一打包配置
# (packaging/backend.spec) 不再生成 .app bundle，故统一转交 build_dmg.sh。
set -e
cd "$(dirname "$0")/../.."
exec bash packaging/macos/build_dmg.sh
