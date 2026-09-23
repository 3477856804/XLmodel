#!/usr/bin/env bash
# 小凌 · 融合版启动脚本（3D 数字人 + 成长型大脑，语言统一 Python）
#   ./start.sh               3D 数字人 + 对话
#   ./start.sh --no-pet      纯命令行
#   ./start.sh --avatar-only 只开 3D 数字人窗口
#   ./start.sh --growth      打印成长闭环报告
set -e
cd "$(dirname "$0")"
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
echo "== 小凌 v1.0 融合版（纯 Python：业务 + 渲染）=="
$PY - <<'PYEOF' || true
import sys
sys.path.insert(0, '.')
try:
    from core.selftest import run_all, format_report
    rep = run_all()
    if rep['health'] != 'ok':
        print(format_report(rep))
except Exception as e:
    print(f"（自检跳过：{e}）")
PYEOF
exec $PY xl.py "$@"
