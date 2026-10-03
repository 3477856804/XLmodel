#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 v0.0.1 - 启动入口

用法：
    python main.py          # 启动小凌
    python main.py --gui    # 启动图形界面
    python main.py --no-pet # 不启动桌宠
"""
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

if __name__ == '__main__':
    # 直接运行 xl.py（旧入口，后续会逐步拆分）
    from pathlib import Path
    xl_path = Path(__file__).parent / 'backend' / 'xl.py'
    if xl_path.exists():
        # 把 xl.py 作为脚本运行
        exec(open(xl_path, encoding='utf-8').read())
    else:
        print("错误：找不到 xl.py")
        sys.exit(1)
