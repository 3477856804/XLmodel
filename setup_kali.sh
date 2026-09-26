#!/usr/bin/env bash
# ============================================================================
#  小凌 · 环境预检 / 部署脚本  v3.6（**可选**）
#
#  定位变化（v3.6）：小凌现在支持「零配置直接启动」——直接 `python xl.py`
#  就会在缺依赖 / 缺 API Key / 缺模型时弹出图形化的「环境配置向导」
#  （renderer/wizard.py），所以本脚本**不再是必须步骤**，而是：
#      · 想一次性把系统依赖 + venv + 权限都准备好的用户
#      · CI / 无人值守部署
#      · 帮别人远程排查环境（配合 --check-only 之类的体检）
#  用法：bash setup_kali.sh
#  日志：<脚本目录>/build.log
#
#  适用：Kali / Debian / Ubuntu（原生或 WSL2）/ Termux
#  支持：NVIDIA 30/40/50 系、AMD(ROCm)、纯 CPU 回退
#  特性：全量体检、系统依赖、venv、进度条直连终端、API 预配置
#
#  注意：v3.6 起**不再修改 xl.py 源码**（旧的"代码补丁"已内建进源码，
#        见 XL_ALLOW_UPDATE / XL_NO_AUTO_DEPS / sys.stdin.reconfigure）。
# ============================================================================
set -uo pipefail

# ─────────────────────────── 常量 ───────────────────────────
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
SCRIPT_NAME="$(basename "$SCRIPT_PATH")"
LOG_FILE="$SCRIPT_DIR/build.log"

PROJECT_DIR="${PROJECT_DIR:-}"
PROFILE_OVERRIDE="${XL_PROFILE:-}"
XL_BIN="${XL_BIN:-/usr/local/bin/xl}"

OFFICIAL_URL="https://xiaoling-4o6.pages.dev/update/xiaoling_latest.zip"
VERSION_URL="https://xiaoling-4o6.pages.dev/update/version.json"

VENV_REL=".venv"
# 基底权重：目录必须与 xl.py 的 MODEL_DIR 一致（.star_core/XLmodel）；
# 但**文件名不限定**——xl.py 接受任意 *.safetensors / *.bin（含 com 分片
# model-00000-of-00001.safetensors）。旧脚本只认 model.safetensors，
# 结果用户放官方分片权重时“程序能跑、脚本却报未找到”。
MODEL_DIR_REL=".star_core/XLmodel"
# 与 xl.py:6892 的“已有模型”判定保持一致（10MB）。
# 旧值是 100MB，会把 10–100MB 的真实权重误判成占位文件。
MODEL_MIN_SIZE=10485760

ZIP_CANDIDATES=("XL-main.zip" "xiaoling-app-main.zip" "xiaoling.zip" "XL.zip" "XLmodel-main.zip")
MODEL_CANDIDATES=("model.safetensors" "model-00000-of-00001.safetensors"
                  "model-00001-of-00001.safetensors" "pytorch_model.bin")

declare -A TORCH_INDEXES=(
    [cu130]="https://download.pytorch.org/whl/cu130"
    [cu129]="https://download.pytorch.org/whl/cu129"
    [cu128]="https://download.pytorch.org/whl/cu128"
    [cu124]="https://download.pytorch.org/whl/cu124"
    [cu121]="https://download.pytorch.org/whl/cu121"
    [cu118]="https://download.pytorch.org/whl/cu118"
    [rocm6.2]="https://download.pytorch.org/whl/rocm6.2"
    [cpu]="https://download.pytorch.org/whl/cpu"
)

# ─────────────────────────── 状态 ───────────────────────────
STEP_TOTAL=20
STEP_CURRENT=0
HAS_NVIDIA=0; HAS_AMD=0
GPU_NAME=""; GPU_DRIVER=""; COMPUTE_CAP=""
TORCH_VARIANT=""; TORCH_INDEX=""
PLATFORM_KIND=""; OS_NAME=""; PY_VER=""
BACKUP_DIR=""
WARN_COUNT=0; ERR_COUNT=0
VENV_DIR=""; MODEL_FILE=""
API_CONFIGURED=0
MODEL_CHOICE=""

# 体检标志
VENV_ALREADY_OK=0
TORCH_ALREADY_OK=0
ML_DEPS_ALREADY_OK=0
API_ALREADY_OK=0

# ─────────────────────────── 颜色 ───────────────────────────
CLR_BLUE=$'\033[34m'
CLR_YELLOW=$'\033[33m'
CLR_RED=$'\033[31m'
CLR_GREEN=$'\033[32m'
CLR_CYAN=$'\033[36m'
CLR_DIM=$'\033[2m'
CLR_RESET=$'\033[0m'

# ─────────────────────────── 日志 ───────────────────────────
# fd 3 = 原始终端 stdout（安装命令专用，保留进度条）
# fd 4 = 原始终端 stderr
log_init() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    exec 3>&1 4>&2
    exec > >(tee >(sed -u 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE")) 2>&1
    {
        printf "\n"
        printf "################################################################\n"
        printf "#  小凌一键部署  %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
        printf "#  用户：%s@%s   PID：%s\n" "$(id -un)" "$(hostname)" "$$"
        printf "#  脚本：%s\n" "$SCRIPT_PATH"
        printf "#  工作目录：%s\n" "$SCRIPT_DIR"
        printf "#  日志：%s\n" "$LOG_FILE"
        printf "################################################################\n"
    } >> "$LOG_FILE"
}

log_close() { exec 1>&3 2>&4; sleep 0.3; }

# 状态输出（彩色 printf）
info()   { printf "${CLR_BLUE}[INFO]${CLR_RESET} %s\n" "$*"; }
warn()   { WARN_COUNT=$((WARN_COUNT+1)); printf "${CLR_YELLOW}[WARN]${CLR_RESET} %s\n" "$*"; }
err()    { ERR_COUNT=$((ERR_COUNT+1));  printf "${CLR_RED}[ERROR]${CLR_RESET} %s\n" "$*" >&2; }
ok()     { printf "${CLR_GREEN}[OK]${CLR_RESET} %s\n" "$*"; }
dim()    { printf "${CLR_DIM}%s${CLR_RESET}\n" "$*"; }
config_prompt() { printf "${CLR_GREEN}[CONFIG]${CLR_RESET} %s" "$*"; }

# 纯文本提示（echo）
echo_sep()   { echo "──────────────────────────────────────────────────────────────"; }
echo_cmd()   { echo "  \$ $*"; }
echo_blank() { echo ""; }

step() {
    STEP_CURRENT=$((STEP_CURRENT+1))
    printf "\n"
    printf "${CLR_BLUE}════════════════════════════════════════════════════════════════${CLR_RESET}\n"
    printf "${CLR_BLUE}  [%s/%s] %s${CLR_RESET}\n" "$STEP_CURRENT" "$STEP_TOTAL" "$*"
    printf "${CLR_BLUE}════════════════════════════════════════════════════════════════${CLR_RESET}\n"
}

die() {
    printf "\n"
    printf "${CLR_RED}╔════════════════════════════════════════════════════════════════╗${CLR_RESET}\n"
    printf "${CLR_RED}║                    配置中止（严重错误）                        ║${CLR_RESET}\n"
    printf "${CLR_RED}╚════════════════════════════════════════════════════════════════╝${CLR_RESET}\n"
    printf "${CLR_RED}[ERROR]${CLR_RESET} %s\n" "$*"
    printf "  时间：%s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
    printf "  日志：%s\n" "$LOG_FILE"
    printf "\n  诊断：\n    tail -100 \"%s\"\n    把整个日志文件发给开发者\n\n" "$LOG_FILE"
    log_close
    exit 1
}

run_or_die() { "$@" || die "命令执行失败：$*"; }

is_wsl() {
    [ -n "${WSL_DISTRO_NAME:-}" ] && return 0
    grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null
}

human_size() {
    local b="$1"
    if [ "$b" -ge 1073741824 ]; then awk -v b="$b" 'BEGIN{printf "%.2f GB", b/1073741824}'
    elif [ "$b" -ge 1048576 ]; then awk -v b="$b" 'BEGIN{printf "%.1f MB", b/1048576}'
    else echo "${b} B"; fi
}

file_owner() { stat -c '%U' "$1" 2>/dev/null; }

# ─────────────────────────── 安装执行辅助 ───────────────────────────
# 安装命令输出直连 fd 3（真实终端）→ 进度条正常
run_install() {
    local desc="$1"; shift
    printf "${CLR_BLUE}[INFO]${CLR_RESET} %s\n" "$desc"
    echo_cmd "$*"
    echo_sep
    local rc=0
    "$@" >&3 2>&3 || rc=$?
    echo_sep
    return $rc
}

# ─────────────────────────── Phase 0：root 检测 ───────────────────────────
check_root() {
    if [ "$(id -u)" -eq 0 ]; then
        printf "\n"
        printf "${CLR_YELLOW}╔════════════════════════════════════════════════════════════════╗${CLR_RESET}\n"
        printf "${CLR_YELLOW}║                 请勿用 root 运行本脚本！                        ║${CLR_RESET}\n"
        printf "${CLR_YELLOW}╚════════════════════════════════════════════════════════════════╝${CLR_RESET}\n"
        printf "  原因：root 创建的 venv 和文件属主会是 root，\n"
        printf "        普通用户之后无法读写、无法启动小凌。\n\n"
        printf "  正确做法：用普通用户重新登录，然后：\n"
        printf "      bash %s\n\n" "$SCRIPT_NAME"
        exit 1
    fi
    ok "用户：$(id -un)（非 root，安全）"
}

# ─────────────────────────── Phase 0.5：sudo 校验 ───────────────────────────
check_sudo() {
    step "sudo 权限校验"
    if ! command -v sudo >/dev/null 2>&1; then
        warn "未检测到 sudo。需要管理员权限的步骤可能会失败。"
        return 0
    fi
    if sudo -v; then
        ok "sudo 权限验证成功，后续 sudo 将免密执行。"
    else
        warn "sudo 验证失败或被取消，后续安装可能失败。"
    fi
}

# ─────────────────────────── Phase 0.8：选择模型大小 ───────────────────────────
select_model_size() {
    step "选择模型大小"
    echo_blank
    echo "  根据你的设备选择想自研的模型大小："
    echo_blank
    echo "    [1] 自研 2B 模型（默认）  MiniCPM5-2B  约 4.8GB  手机/电脑流畅"
    echo "    [2] 自研 1B 模型          MiniCPM5-1B  约 2.1GB  低配设备，轻量"
    echo_blank
    config_prompt "请输入序号 [1-2，默认 1]："
    read -r choice
    case "${choice:-1}" in
        2) MODEL_CHOICE="自研1B模型" ;;
        *) MODEL_CHOICE="自研2B模型" ;;
    esac
    ok "已选择：$MODEL_CHOICE"
}

# ─────────────────────────── Phase 1：环境检测 ───────────────────────────
detect_env() {
    step "环境检测"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_NAME="${PRETTY_NAME:-unknown}"
    fi
    info "操作系统：$OS_NAME"
    info "内核：$(uname -r)"

    if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
        PLATFORM_KIND="termux"
        info "运行环境：Termux（安卓）"
    elif is_wsl; then
        PLATFORM_KIND="wsl2"
        info "运行环境：WSL2（$WSL_DISTRO_NAME）"
        if [ -x /usr/lib/wsl/lib/nvidia-smi ] && ! command -v nvidia-smi >/dev/null 2>&1; then
            export PATH="/usr/lib/wsl/lib:$PATH"
            info "已把 /usr/lib/wsl/lib 加入 PATH"
        fi
    else
        PLATFORM_KIND="linux"
        info "运行环境：原生 Linux"
    fi

    info "CPU：$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)（$(nproc) 核）"
    command -v free >/dev/null 2>&1 && info "内存：$(free -h | awk '/^Mem:/ {print $2" 总量 / "$7" 可用"}')"

    local avail
    avail=$(df -B1 "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
    [ -n "${avail:-}" ] && {
        info "脚本目录可用磁盘：$(human_size "$avail")"
        [ "$avail" -lt 5368709120 ] && warn "磁盘可用 < 5GB，可能空间不足"
    }

    command -v python3 >/dev/null 2>&1 || die "找不到 python3。请先：sudo apt install -y python3 python3-venv python3-full"
    PY_VER=$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    info "系统 Python：$PY_VER（$(command -v python3)）"
    case "$PY_VER" in
        3.10|3.11|3.12) ok "Python 版本适配良好" ;;
        3.13)
            # 实测结论（2026-09）：3.13 上 torch 2.11.0+cu128 可正常安装并在
            # RTX 50 系（sm_120）跑通，6 个回归测试全部通过。
            # 所以不再建议用户额外装 3.12（那会多装一份 Python 却未必需要）。
            ok "Python 3.13：已验证可用（torch 2.11+cu128 / PySide6 6.11 实测通过）"
            info "  若系统里存在 python3.12，本脚本会自动优先用它创建 venv"
            echo "  ╭──────────────────────────────────────────────────────────╮"
            echo "  │  注意：Kali 默认就是 3.13，无需另装 3.12。                │"
            echo "  │  只有遇到具体的 wheel 缺失时，才建议：                     │"
            echo "  │    sudo apt install -y python3.12 python3.12-venv         │"
            echo "  ╰──────────────────────────────────────────────────────────╯"
            echo_blank
            ;;
        *) warn "Python $PY_VER 未在测试范围内" ;;
    esac
    python3 -c "import venv" >/dev/null 2>&1 || die "Python 缺 venv 模块。请：sudo apt install -y python3-venv python3-full"

    detect_gpu
}

detect_gpu() {
    echo_blank
    echo "  ── GPU 检测 ──"
    if command -v nvidia-smi >/dev/null 2>&1; then
        local out
        if out=$(nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv,noheader 2>/dev/null); then
            HAS_NVIDIA=1
            GPU_NAME=$(echo "$out" | head -1 | awk -F',' '{print $1}' | xargs)
            GPU_DRIVER=$(echo "$out" | head -1 | awk -F',' '{print $2}' | xargs)
            COMPUTE_CAP=$(echo "$out" | head -1 | awk -F',' '{print $3}' | xargs)
            ok "NVIDIA GPU：$GPU_NAME"
            info "  驱动 $GPU_DRIVER / 计算能力 sm_${COMPUTE_CAP//./}"
            local cc_major drv_major
            cc_major=$(echo "$COMPUTE_CAP" | cut -d. -f1)
            drv_major=$(echo "$GPU_DRIVER" | cut -d. -f1)
            if [ "$cc_major" -ge 12 ] && [ "$drv_major" -lt 570 ]; then
                die "检测到 Blackwell(50系) 但驱动 $GPU_DRIVER < 570。请升级驱动后重启 WSL。"
            fi
        else
            warn "nvidia-smi 存在但查询失败"
        fi
    elif is_wsl; then
        warn "WSL 中未找到 nvidia-smi（Windows 侧 NVIDIA 驱动未装或 < 570）"
    fi

    if [ "$HAS_NVIDIA" = "0" ] && command -v lspci >/dev/null 2>&1; then
        local amd
        amd=$(lspci 2>/dev/null | grep -iE 'vga|3d|display' | grep -iE 'amd|radeon|advanced micro' | head -1)
        if [ -n "$amd" ]; then
            HAS_AMD=1
            GPU_NAME=$(echo "$amd" | sed 's/.*: //')
            ok "AMD GPU：$GPU_NAME"
            command -v rocminfo >/dev/null 2>&1 && info "  ROCm 已安装" || warn "  ROCm 未安装"
        fi
    fi

    [ "$HAS_NVIDIA" = "0" ] && [ "$HAS_AMD" = "0" ] && warn "未检测到独立显卡，将使用 CPU"
}

# ─────────────────────────── Phase 2：选择方案 ───────────────────────────
select_profile() {
    step "选择安装方案"
    if [ -n "$PROFILE_OVERRIDE" ]; then
        info "用户指定 XL_PROFILE=$PROFILE_OVERRIDE"
        case "$PROFILE_OVERRIDE" in
            nvidia-blackwell|cuda128)         TORCH_VARIANT="cu128" ;;
            nvidia-ada|nvidia-ampere|cuda124) TORCH_VARIANT="cu124" ;;
            cuda121) TORCH_VARIANT="cu121" ;;
            cuda118) TORCH_VARIANT="cu118" ;;
            amd-rocm|rocm62) TORCH_VARIANT="rocm6.2" ;;
            cpu) TORCH_VARIANT="cpu" ;;
            *) die "未知 XL_PROFILE=$PROFILE_OVERRIDE" ;;
        esac
    elif [ "$HAS_NVIDIA" = "1" ]; then
        local cc_major drv_major
        cc_major=$(echo "$COMPUTE_CAP" | cut -d. -f1)
        drv_major=$(echo "$GPU_DRIVER" | cut -d. -f1)
        if [ "$cc_major" -ge 12 ]; then
            TORCH_VARIANT="cu128"; info "50 系（sm_120）→ cu128"
        elif [ "$drv_major" -ge 550 ]; then
            TORCH_VARIANT="cu124"; info "30/40 系 + 驱动 $GPU_DRIVER → cu124"
        elif [ "$drv_major" -ge 525 ]; then
            TORCH_VARIANT="cu121"; info "30/40 系 + 老驱动 → cu121"
        else
            TORCH_VARIANT="cu118"; warn "驱动 $GPU_DRIVER 较旧 → cu118"
        fi
    elif [ "$HAS_AMD" = "1" ]; then
        TORCH_VARIANT="rocm6.2"; warn "AMD 方案 ROCm 6.2"
    else
        TORCH_VARIANT="cpu"; info "纯 CPU 模式"
    fi
    TORCH_INDEX="${TORCH_INDEXES[$TORCH_VARIANT]:-}"
    [ -z "$TORCH_INDEX" ] && die "内部错误：未知 TORCH_VARIANT=$TORCH_VARIANT"
    ok "方案：$TORCH_VARIANT  ($TORCH_INDEX)"
}

# ─────────────────────────── Phase 3：部署项目 ───────────────────────────
find_project_dir() {
    if [ -n "${PROJECT_DIR:-}" ] && [ -f "$PROJECT_DIR/xl.py" ]; then return 0; fi
    if [ -f "$SCRIPT_DIR/xl.py" ]; then PROJECT_DIR="$SCRIPT_DIR"; return 0; fi
    local d
    for d in "$SCRIPT_DIR"/*/; do
        [ -d "$d" ] || continue
        [ -f "$d/xl.py" ] && { PROJECT_DIR="${d%/}"; return 0; }
    done
    return 1
}

find_zip() {
    local name z
    for name in "${ZIP_CANDIDATES[@]}"; do
        [ -f "$SCRIPT_DIR/$name" ] && { echo "$SCRIPT_DIR/$name"; return 0; }
    done
    z=$(find "$SCRIPT_DIR" -maxdepth 1 -type f \( -name 'xiaoling_v*.zip' -o -name 'XLmodel*.zip' \) 2>/dev/null | head -1)
    [ -n "$z" ] && { echo "$z"; return 0; }
    z=$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name '*.zip' 2>/dev/null | head -1)
    [ -n "$z" ] && { echo "$z"; return 0; }
    return 1
}

download_official() {
    info "本地没有 zip，尝试从官网自动下载..."
    command -v curl >/dev/null 2>&1 || { warn "无 curl"; return 1; }
    command -v unzip >/dev/null 2>&1 || { warn "无 unzip"; return 1; }

    local ver
    ver=$(curl -s --max-time 10 "$VERSION_URL" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("version",""))' 2>/dev/null)
    info "官网最新版本：${ver:-未知}"

    local zip_path="$SCRIPT_DIR/xiaoling_latest_download.zip"
    info "下载中：$OFFICIAL_URL"
    curl -sL --max-time 300 -o "$zip_path" "$OFFICIAL_URL" || { warn "下载失败"; rm -f "$zip_path"; return 1; }
    [ -s "$zip_path" ] || { warn "下载为空文件"; rm -f "$zip_path"; return 1; }
    info "下载完成：$(human_size "$(stat -c%s "$zip_path")")"

    local before after newdir
    before=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    (cd "$SCRIPT_DIR" && unzip -q -o "$zip_path") || { warn "解压失败"; rm -f "$zip_path"; return 1; }
    after=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    newdir=$(comm -13 <(echo "$before") <(echo "$after") | head -1)
    rm -f "$zip_path"

    if [ -n "$newdir" ] && [ -f "$SCRIPT_DIR/$newdir/xl.py" ]; then
        PROJECT_DIR="$SCRIPT_DIR/$newdir"; ok "官网下载并解压 → $PROJECT_DIR"; return 0
    fi
    if find_project_dir; then ok "官网下载解压后找到项目 → $PROJECT_DIR"; return 0; fi
    warn "官网包解压后未找到 xl.py"; return 1
}

deploy_project() {
    step "部署项目"
    if find_project_dir; then ok "已找到项目目录：$PROJECT_DIR"; return 0; fi

    warn "未找到已解压的项目，尝试从 zip 解压"
    local zip
    if ! zip=$(find_zip); then
        download_official && return 0
        die "未找到项目或 zip。"
    fi
    info "找到 zip：$zip"

    if ! command -v unzip >/dev/null 2>&1; then
        warn "未安装 unzip，尝试安装"
        run_install "安装 unzip" sudo apt install -y unzip || die "安装 unzip 失败"
    fi

    local before after newdir
    before=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    info "解压中..."
    (cd "$SCRIPT_DIR" && unzip -q -o "$zip") || die "解压失败：$zip"
    after=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    newdir=$(comm -13 <(echo "$before") <(echo "$after") | head -1)

    if [ -n "$newdir" ] && [ -f "$SCRIPT_DIR/$newdir/xl.py" ]; then
        PROJECT_DIR="$SCRIPT_DIR/$newdir"; ok "解压完成 → $PROJECT_DIR"
    elif find_project_dir; then
        ok "解压完成 → $PROJECT_DIR"
    else
        die "解压成功但未找到 xl.py"
    fi
}

# ─────────────────────────── Phase 4：环境体检（关键新增） ───────────────────────────
preflight_check() {
    step "环境体检（避免重复安装）"

    cd "$PROJECT_DIR" || die "无法进入项目目录"
    VENV_DIR="$PROJECT_DIR/$VENV_REL"
    # 权重文件名不固定：用与 xl.py 相同的判定（任意 *.safetensors / *.bin，>10MB）
    MODEL_FILE=$(find_weight_in "$PROJECT_DIR/$MODEL_DIR_REL") || MODEL_FILE=""

    # ── 1. venv 检查（含属主 + 版本） ──
    echo_blank
    echo "  ── 虚拟环境 ──"
    if [ -e "$VENV_DIR" ]; then
        local owner; owner=$(file_owner "$VENV_DIR")
        local cur_user; cur_user=$(id -un)

        if [ "$owner" != "$cur_user" ]; then
            warn "venv 属主是 $owner（当前用户 $cur_user），将自动修复"
            if sudo chown -R "$cur_user:$cur_user" "$VENV_DIR" 2>/dev/null; then
                ok "属主已修复：$cur_user"
            else
                warn "自动修复失败，将删除重建"
                sudo rm -rf "$VENV_DIR" 2>/dev/null || rm -rf "$VENV_DIR" 2>/dev/null || true
            fi
        fi
    fi

    if [ -x "$VENV_DIR/bin/python" ]; then
        local venv_py
        venv_py=$("$VENV_DIR/bin/python" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        # 允许 3.12 优先级高于 3.13
        local want_py="$PY_VER"
        if [ "$PY_VER" = "3.13" ] && command -v python3.12 >/dev/null 2>&1; then
            want_py="3.12"
        fi

        if [ "$venv_py" = "$want_py" ] || [ "$venv_py" = "$PY_VER" ]; then
            if "$VENV_DIR/bin/python" -c "print(1)" >/dev/null 2>&1; then
                ok "已有 venv：Python $venv_py（属主正确，可复用）"
                VENV_ALREADY_OK=1
            else
                warn "已有 venv 但无法运行，将重建"
            fi
        else
            warn "已有 venv Python $venv_py ≠ 期望 $want_py，将重建"
        fi
    else
        info "未发现 venv，将新建"
    fi

    # 若能复用，激活它做后续检查
    if [ "$VENV_ALREADY_OK" = "1" ]; then
        source "$VENV_DIR/bin/activate"
        info "已临时激活：$(which python)"
    fi

    # ── 2. PyTorch 检查 ──
    echo_blank
    echo "  ── PyTorch 方案（目标：$TORCH_VARIANT） ──"
    if [ "$VENV_ALREADY_OK" = "1" ] && python -c "import torch" 2>/dev/null; then
        local torch_ver cuda_avail cuda_ver
        torch_ver=$(python -c "import torch;print(torch.__version__)" 2>/dev/null)
        cuda_avail=$(python -c "import torch;print(torch.cuda.is_available())" 2>/dev/null)
        cuda_ver=$(python -c "import torch;print(torch.version.cuda or 'cpu')" 2>/dev/null)
        info "已装 torch $torch_ver（CUDA=$cuda_ver，可用=$cuda_avail）"

        case "$TORCH_VARIANT" in
            cpu)
                ok "目标=CPU，已装 torch 接受，跳过下载"
                TORCH_ALREADY_OK=1 ;;
            rocm6.2)
                if echo "$cuda_ver" | grep -qiE 'rocm|hip'; then
                    ok "已装 ROCm 版，跳过下载"; TORCH_ALREADY_OK=1
                else
                    warn "目标=ROCm 但已装非 ROCm 版，将重装"
                fi ;;
            cu*)
                local want_major="12"
                [ "$TORCH_VARIANT" = "cu118" ] && want_major="11"
                if [ "$cuda_avail" = "True" ]; then
                    local have_major; have_major=$(echo "$cuda_ver" | cut -d. -f1)
                    if [ "$have_major" = "$want_major" ]; then
                        ok "已装 CUDA $cuda_ver 与目标 $TORCH_VARIANT 匹配，跳过下载"
                        TORCH_ALREADY_OK=1
                    else
                        warn "已装 CUDA major=$have_major ≠ 目标 major=$want_major，将重装"
                    fi
                else
                    warn "已装 torch 不支持 CUDA，但目标要求 $TORCH_VARIANT，将重装"
                fi ;;
        esac

        if [ "$TORCH_ALREADY_OK" = "1" ]; then
            python -c "import torchvision" 2>/dev/null || { warn "缺 torchvision，将补装"; TORCH_ALREADY_OK=0; }
            python -c "import torchaudio"  2>/dev/null || { warn "缺 torchaudio，将补装";   TORCH_ALREADY_OK=0; }
        fi
    else
        info "未检测到 torch，将全新安装"
    fi

    # ── 3. ML 依赖检查 ──
    echo_blank
    echo "  ── ML 依赖 ──"
    if [ "$VENV_ALREADY_OK" = "1" ]; then
        local ml_ok=1 pkg ver
        for pkg in transformers peft accelerate safetensors; do
            if python -c "import $pkg" 2>/dev/null; then
                ver=$(python -c "import $pkg;print(getattr($pkg,'__version__','?'))" 2>/dev/null)
                ok "  $pkg $ver"
            else
                warn "  缺 $pkg"
                ml_ok=0
            fi
        done
        [ "$ml_ok" = "1" ] && ML_DEPS_ALREADY_OK=1
    else
        info "venv 不可用，ML 依赖待安装"
    fi

    # ── 4. 模型权重 ──
    echo_blank
    echo "  ── 模型文件 ──"
    if [ -n "$MODEL_FILE" ] && [ -f "$MODEL_FILE" ]; then
        local sz; sz=$(stat -c%s "$MODEL_FILE" 2>/dev/null || echo 0)
        ok "已就位：$(basename "$MODEL_FILE")（$(human_size "$sz")）"
    else
        info "尚未放置基底权重（目录：$PROJECT_DIR/$MODEL_DIR_REL）"
        info "  可放进任意 *.safetensors / *.bin；或让程序首次启动自动下载"
    fi

    # ── 5. API 配置 ──
    # 甲-1：以**程序真正读取的位置**为准（.star_core/xiaoling_config.json 的
    # deepseek_api_key），不再 grep .env —— 那会让用户拿到假阳性的"已配置"。
    # core.config 只依赖 stdlib，所以用系统 python3 就能读，不需要 venv。
    echo_blank
    echo "  ── API 配置 ──"
    local key_len=0 env_file="$PROJECT_DIR/.env"
    if [ -f "$PROJECT_DIR/core/config.py" ]; then
        key_len=$(cd "$PROJECT_DIR" && python3 -c \
            "from core import config;k=str(config.load().get('deepseek_api_key') or '');print(0 if k in ('','暂未填入') else len(k))" \
            2>/dev/null || echo 0)
    fi
    if [ "${key_len:-0}" -gt 0 ] 2>/dev/null; then
        ok "已配置 DeepSeek API Key（长度 ${key_len}，来自 xiaoling_config.json）"
        API_ALREADY_OK=1
    elif [ -f "$env_file" ] && grep -q "^DEEPSEEK_API_KEY=" "$env_file"; then
        info "检测到历史 .env 里有 Key（程序启动时会自动迁移到 xiaoling_config.json）"
        API_ALREADY_OK=1
    else
        info "尚未配置 API Key（可在程序「环境向导 → API」里填）"
    fi

    # ── 6. 启动命令 ──
    echo_blank
    echo "  ── 启动命令 ──"
    if [ -f "$XL_BIN" ] && grep -qF "$VENV_DIR" "$XL_BIN" && grep -qF "$PROJECT_DIR" "$XL_BIN"; then
        ok "$XL_BIN 已指向当前项目"
    else
        info "$XL_BIN 未配置或指向其他项目"
    fi

    # ── 7. 代码补丁 ──
    echo_blank
    echo "  ── 代码补丁 ──"
    local xlfile="$PROJECT_DIR/xl.py"
    local petfile="$PROJECT_DIR/pet.py"
    if [ -f "$xlfile" ]; then
        # 这些能力现在**内建在源码里**（乙-4 / 乙-5），脚本不再打补丁，只做检查。
        grep -q 'XL_ALLOW_UPDATE' "$xlfile" \
            && ok "  自动更新开关：源码已内建" || warn "  自动更新开关：源码里没有（旧版 xl.py？）"
        grep -q 'sys.stdin.reconfigure' "$xlfile" \
            && ok "  UTF-8 容错：源码已内建" || warn "  UTF-8 容错：源码里没有"
        grep -q 'XL_NO_AUTO_DEPS' "$xlfile" \
            && ok "  依赖安装开关：源码已内建" || warn "  依赖安装开关：源码里没有"
    fi

    # ── 8. 其他常用包 ──
    echo_blank
    echo "  ── 其他已装组件 ──"
    if [ "$VENV_ALREADY_OK" = "1" ]; then
        local others=(numpy scipy pillow psutil)
        local found=0
        for pkg in "${others[@]}"; do
            if python -c "import $pkg" 2>/dev/null; then
                ok "  $pkg $(python -c "import $pkg;print(getattr($pkg,'__version__','?'))" 2>/dev/null)"
                found=1
            fi
        done
        [ "$found" = "0" ] && dim "    （无）"
    fi

    # ── 体检总结 ──
    echo_blank
    echo_sep
    printf "  ${CLR_CYAN}体检结论：${CLR_RESET}\n"
    printf "    venv          : %s\n" "$([ "$VENV_ALREADY_OK" = 1 ] && echo '✅ 可复用（跳过创建）' || echo '⏬ 需新建')"
    printf "    PyTorch       : %s\n" "$([ "$TORCH_ALREADY_OK" = 1 ] && echo '✅ 已装且匹配（跳过下载）' || echo '⏬ 需安装/重装')"
    printf "    ML 依赖       : %s\n" "$([ "$ML_DEPS_ALREADY_OK" = 1 ] && echo '✅ 已齐（跳过安装）' || echo '⏬ 需安装')"
    printf "    API Key       : %s\n" "$([ "$API_ALREADY_OK" = 1 ] && echo '✅ 已配置' || echo '❓ 待配置')"
    echo_sep

    # 退出临时激活（后续 setup_venv 会正式激活）
    if [ "$VENV_ALREADY_OK" = "1" ]; then
        deactivate 2>/dev/null || true
    fi
}

# ─────────────────────────── Phase 4.5：放置模型 ───────────────────────────
# 在目录里找第一个"有效"权重：任意 *.safetensors / *.bin 且 > MODEL_MIN_SIZE。
# 与 xl.py 的 _find_base_model_file 口径一致——不看文件名，只看扩展名与体积。
#
# ★ 但必须**排除 adapter***：适配器是 LoRA（十几 MB），基底是数 GB 的完整权重。
#   兜底的 `find ... -name '*.safetensors' -size +10M` 会搜进 .star_core/，
#   把 17.6MB 的 adapter_model.safetensors 当成基底权重复制进 .star_core/XLmodel/，
#   程序随后误判"基底已就位"、跳过真正权重的下载（日志表现为「基底 17.6MB / 100%」）。
find_weight_in() {
    local dir="$1" p
    [ -d "$dir" ] || return 1
    for p in "$dir"/*.safetensors "$dir"/*.bin; do
        [ -f "$p" ] || continue
        case "$(basename "$p")" in adapter* | ADAPTER*) continue ;; esac
        [ "$(stat -c%s "$p" 2>/dev/null || echo 0)" -gt "$MODEL_MIN_SIZE" ] && { echo "$p"; return 0; }
    done
    return 1
}

find_model_source() {
    local name p d
    for name in "${MODEL_CANDIDATES[@]}"; do
        p="$SCRIPT_DIR/$name"
        [ -f "$p" ] && [ "$(stat -c%s "$p" 2>/dev/null || echo 0)" -gt "$MODEL_MIN_SIZE" ] && { echo "$p"; return 0; }
    done
    for d in "$SCRIPT_DIR"/*/; do
        p=$(find_weight_in "$d") && { echo "$p"; return 0; }
    done
    for d in "$HOME/xiaoling1/.star_core/XLmodel" "$HOME/xiaoling/.star_core/XLmodel" \
             "$HOME/xiaoling1" "$HOME/xiaoling"; do
        p=$(find_weight_in "$d") && { echo "$p"; return 0; }
    done
    # 兜底：浅层搜索，但**剪掉** .star_core / .git / .venv / build / dist，并排除 adapter*，
    # 否则会把适配器或缓存里的权重当成基底（见上面的说明）。
    p=$(find "$SCRIPT_DIR" -maxdepth 3 \
            \( -name '.star_core' -o -name '.git' -o -name '.venv' -o -name 'build' -o -name 'dist' \) -prune -o \
            -type f \( -name '*.safetensors' -o -name '*.bin' \) \
            ! -name 'adapter*' -size +"$((MODEL_MIN_SIZE / 1024 / 1024))M" -print 2>/dev/null | head -1)
    [ -n "$p" ] && { echo "$p"; return 0; }
    return 1
}

place_model() {
    step "放置模型权重"
    local mdir="$PROJECT_DIR/$MODEL_DIR_REL"
    mkdir -p "$mdir" 2>/dev/null || true

    # 就位判定与 xl.py 一致：目录里有任意 >10MB 权重就算有，不要求特定文件名
    local existing
    if existing=$(find_weight_in "$mdir"); then
        MODEL_FILE="$existing"
        ok "模型已就位：$(basename "$existing")（$(human_size "$(stat -c%s "$existing")")）"
        return 0
    fi

    local src
    if ! src=$(find_model_source); then
        warn "未找到有效的基底权重（*.safetensors / *.bin，需 >$(human_size "$MODEL_MIN_SIZE")）"
        echo_blank
        echo_sep
        echo "  【模型获取方式】"
        echo "  1. 加入 QQ 社区群：1057895186（小凌社区1群），群文件里有完整权重"
        echo "  2. 下载后放到：$SCRIPT_DIR，或直接复制到：$mdir"
        echo "  3. 也可以什么都不做：程序首次启动会按所选档位自动下载"
        echo_sep
        echo_blank
        return 0
    fi

    local dest="$mdir/$(basename "$src")"
    MODEL_FILE="$dest"
    if [ "$src" = "$dest" ]; then
        ok "模型就地就位：$(basename "$dest")（$(human_size "$(stat -c%s "$dest")")）"
        return 0
    fi

    info "找到权重：$src（$(human_size "$(stat -c%s "$src")")）"
    info "复制到：$dest（保留原文件名，不再强制改名成 model.safetensors）"
    if command -v rsync >/dev/null 2>&1; then
        rsync -ah --progress "$src" "$dest" >&3 2>&3 || cp "$src" "$dest" || die "复制模型失败"
    else
        cp "$src" "$dest" || die "复制模型失败"
    fi
    ok "模型就位：$(basename "$dest")（$(human_size "$(stat -c%s "$MODEL_FILE")")）"
}

# ─────────────────────────── Phase 5：配置 API ───────────────────────────
configure_api() {
    step "配置 API 与 中转站"
    local env_file="$PROJECT_DIR/.env"

    if [ "$API_ALREADY_OK" = "1" ]; then
        ok "检测到已有 API Key 配置"
        config_prompt "是否重新配置？[y/N，默认 N]："
        read -r ans
        case "${ans:-N}" in
            [yY]*) : ;;
            *) info "保留原配置，跳过"; return 0 ;;
        esac
    fi

    local api_key="" base_url=""
    config_prompt "请输入 DeepSeek API Key（直接回车跳过，后期可在程序的「环境向导」里配）: "
    read -r api_key

    if [ -n "$api_key" ]; then
        config_prompt "请输入 API 中转站地址（Base URL，回车跳过）: "
        read -r base_url

        # 甲-1：写入程序真正读取的位置 .star_core/xiaoling_config.json，
        # 键名也要对（deepseek_api_key / deepseek_base_url）。
        # 旧脚本写的是 .env 的 DEEPSEEK_API_KEY / API_BASE_URL —— 程序从来不读它，
        # 用户配完等于没配，蒸馏老师永远离线。
        # 这里直接调用 core.config.patch()：复用程序自己的实现，也不用 sed 拼 JSON。
        #
        # 注意：本函数在 main() 里跑在 setup_venv **之前**，所以 venv 可能还不存在。
        # core.config 只依赖 stdlib，因此默认用系统 python3，venv 在就用 venv。
        local wrote=0 _py="python3"
        [ -x "$VENV_DIR/bin/python" ] && _py="$VENV_DIR/bin/python"
        if [ -f "$PROJECT_DIR/core/config.py" ]; then
            cd "$PROJECT_DIR" 2>/dev/null || true
            if XL_KEY="$api_key" XL_URL="$base_url" "$_py" - <<'PYEOF' >&3 2>&3
import os
from core import config
changes = {}
if os.environ.get('XL_KEY'):
    changes['deepseek_api_key'] = os.environ['XL_KEY']
if os.environ.get('XL_URL'):
    changes['deepseek_base_url'] = os.environ['XL_URL']
if changes:
    config.patch(changes)
    print(f'  [OK] 已写入 {config.CONFIG_PATH}：{"、".join(sorted(changes))}')
PYEOF
            then
                wrote=1
            fi
        fi

        if [ "$wrote" = "1" ]; then
            API_CONFIGURED=1
            ok "API 配置已保存到 .star_core/xiaoling_config.json"
        else
            # venv 还没建好等情况下退回 .env；程序启动时的 migrate_legacy_env()
            # 会自动把它迁进 config.json，所以这条路径依然有效（只是多一步）。
            local env_file="$PROJECT_DIR/.env"
            { [ -n "$api_key" ] && echo "DEEPSEEK_API_KEY=$api_key"; \
              [ -n "$base_url" ] && echo "API_BASE_URL=$base_url"; } >> "$env_file"
            API_CONFIGURED=1
            info "已写入 $env_file（程序启动时会自动迁移到 xiaoling_config.json）"
        fi
    else
        API_CONFIGURED=0
        info "已跳过 API 配置；之后可在程序的「环境向导 → API」里填写"
    fi
}

# ─────────────────────────── Phase 6：前置检查 ───────────────────────────
check_prereq() {
    step "前置检查"
    command -v sudo >/dev/null 2>&1 && ok "sudo 可用" || warn "无 sudo"
    curl -sI --max-time 5 https://pypi.org >/dev/null 2>&1 && ok "PyPI 可达" || warn "PyPI 不可达"
    if [ "$TORCH_VARIANT" != "cpu" ] && [ "$TORCH_VARIANT" != "rocm6.2" ]; then
        curl -sI --max-time 5 "$TORCH_INDEX" >/dev/null 2>&1 && ok "PyTorch 源可达" || warn "PyTorch 源不可达"
    fi
    cd "$PROJECT_DIR" || die "无法进入项目目录：$PROJECT_DIR"
    VENV_DIR="$PROJECT_DIR/$VENV_REL"
}

# ─────────────────────────── Phase 7：备份 ───────────────────────────
backup_data() {
    step "备份关键数据"
    BACKUP_DIR="$HOME/xl_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cd "$PROJECT_DIR"
    local saved=0

    for f in xl_memory.json requirements.txt xl.py pet.py; do
        [ -f "$f" ] && cp "$f" "$BACKUP_DIR/" 2>/dev/null && saved=$((saved+1))
    done
    # 语料目录实际叫 数据/（旧脚本写的是 data/，等于没备份）
    for d in 数据 data; do
        [ -d "$d" ] && cp -r "$d" "$BACKUP_DIR/" 2>/dev/null && saved=$((saved+1))
    done

    # 甲-7：成长数据才是最该备份的，旧清单完全漏了 .star_core。
    # 只备份"非权重"部分，避免把几 GB 的基底权重也复制一遍。
    local star="$PROJECT_DIR/.star_core"
    if [ -d "$star" ]; then
        local sdst="$BACKUP_DIR/.star_core"
        mkdir -p "$sdst" 2>/dev/null
        for a in adapter_config.json adapter_model.safetensors adapter_model.bin adapter.pt; do
            [ -f "$star/$a" ] && cp "$star/$a" "$sdst/" 2>/dev/null && saved=$((saved+1))
        done
        [ -d "$star/adapter" ] && cp -r "$star/adapter" "$sdst/" 2>/dev/null && saved=$((saved+1))
        for d in growth rag; do
            [ -d "$star/$d" ] && cp -r "$star/$d" "$sdst/" 2>/dev/null && saved=$((saved+1))
        done
        for f in xiaoling_config.json model_choice.txt; do
            [ -f "$star/$f" ] && cp "$star/$f" "$sdst/" 2>/dev/null && saved=$((saved+1))
        done
    fi
    ok "已备份 $saved 项 → $BACKUP_DIR（含成长数据；基底权重未备份以省空间）"
}

# ─────────────────────────── Phase 8：venv ───────────────────────────
setup_venv() {
    step "准备虚拟环境"

    if [ "$VENV_ALREADY_OK" = "1" ]; then
        ok "体检已确认 venv 可用，跳过重建"
    else
        if [ -e "$VENV_DIR" ]; then
            local owner; owner=$(file_owner "$VENV_DIR")
            if [ "$owner" != "$(id -un)" ]; then
                warn "venv 属主是 $owner，尝试修复"
                sudo chown -R "$(id -un):$(id -gn)" "$VENV_DIR" 2>/dev/null || {
                    warn "修复失败，删除重建"
                    sudo rm -rf "$VENV_DIR" 2>/dev/null || true
                }
            fi
        fi

        if [ -x "$VENV_DIR/bin/python" ] && [ "$VENV_ALREADY_OK" = "0" ]; then
            warn "$VENV_DIR 存在但不可用（版本不匹配等），删除重建"
            rm -rf "$VENV_DIR"
        fi

        if [ ! -x "$VENV_DIR/bin/python" ]; then
            info "创建 venv ..."
            # Python 3.13 且系统有 3.12 时优先用 3.12
            local py_for_venv="python3"
            if [ "$PY_VER" = "3.13" ] && command -v python3.12 >/dev/null 2>&1; then
                py_for_venv="python3.12"
                info "检测到 3.12，优先使用（PyTorch 生态兼容性更好）"
            fi
            run_or_die "$py_for_venv" -m venv "$VENV_DIR"
            ok "venv 创建：$VENV_DIR"
        fi
    fi

    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    ok "已激活：$(which python)  ($(python -V 2>&1))"

    export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_PROGRESS_BAR=on
    export PYTHONIOENCODING=utf-8 LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

    # pip/wheel 已齐则跳过
    if python -c "import wheel" 2>/dev/null && python -m pip --version >/dev/null 2>&1; then
        ok "pip $(pip --version | awk '{print $2}') / wheel 已就位，跳过升级"
    else
        info "升级 pip/wheel ..."
        run_install "升级 pip/wheel" pip install -U pip wheel
    fi
}

# ─────────────────────────── Phase 9：系统依赖 ───────────────────────────
install_sysdeps() {
    step "安装系统依赖（语音/音频/图像/Tk）"

    if [ "$PLATFORM_KIND" = "termux" ]; then
        info "Termux 环境：使用 pkg 安装系统依赖"
        run_install "pkg update" pkg update -y || warn "pkg update 失败（继续）"
        run_install "安装 Termux 基础依赖" pkg install -y python python-pip curl unzip python-numpy python-pillow clang || warn "基础依赖部分失败"
        run_install "安装 libomp" pkg install -y libomp || warn "libomp 安装失败"
        run_install "安装 python-psutil" pkg install -y python-psutil || warn "python-psutil 安装失败"

        local missing_termux=()
        for c in python curl unzip clang; do
            command -v "$c" >/dev/null 2>&1 || missing_termux+=("$c")
        done
        if [ "${#missing_termux[@]}" -eq 0 ]; then
            ok "Termux 系统依赖安装完成"
        else
            warn "Termux 缺少：${missing_termux[*]}"
        fi
        return 0
    fi

    if ! command -v apt >/dev/null 2>&1; then
        warn "非 Debian 系，跳过"; return 0
    fi

    run_install "apt 索引更新" sudo apt update || warn "apt update 失败（不致命）"

    # 甲-2：补齐 GL / xcb / OSMesa / 音频 / 中文字体。
    # 缺 libxcb-* 里任意一个，PySide6 就会报
    # "Could not load the Qt platform plugin xcb" —— 桌宠根本起不来；
    # 缺 libosmesa6 则无 GPU 时没有离屏软件 GL 兜底。
    # 清单与 打包/linux/install_deps.sh、renderer/renderer.py 的提示保持一致。
    local pkgs=(
        espeak-ng libespeak1 libespeak-ng1 libportaudio2 python3-tk ffmpeg rsync unzip alsa-utils
        libgl1 libglx-mesa0 libgl1-mesa-dri libosmesa6 libegl1 mesa-utils
        libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1
        libxcb-shape0 libxcb-randr0
        fonts-noto-cjk
    )
    local missing=() p
    for p in "${pkgs[@]}"; do
        dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        ok "系统依赖齐全（跳过 apt install）"; return 0
    fi

    # 先过滤掉当前发行版里不存在的包名（例如 libespeak1 在新版 Debian/Kali 上
    # 已被 libespeak-ng1 取代）。否则 apt install 会因为一个名字不存在而整条失败，
    # 结果一个包都装不上。
    local avail=()
    for p in "${missing[@]}"; do
        if apt-cache show "$p" >/dev/null 2>&1; then
            avail+=("$p")
        else
            info "  跳过当前发行版不存在的包：$p"
        fi
    done
    missing=("${avail[@]}")
    [ "${#missing[@]}" -eq 0 ] && { ok "没有可安装的缺失包"; return 0; }

    printf "${CLR_BLUE}[INFO]${CLR_RESET} 缺失依赖：%s\n" "${missing[*]}"
    # 整体装一次；万一仍失败（源异常/依赖冲突），退化为逐个装，尽量多装上几个
    if ! run_install "安装缺失依赖" sudo apt install -y --no-install-recommends "${missing[@]}"; then
        warn "整体安装失败，改为逐个安装"
        for p in "${missing[@]}"; do
            run_install "安装 $p" sudo apt install -y --no-install-recommends "$p" \
                || warn "  $p 装不上（继续）"
        done
    fi

    local still_missing=()
    for p in "${missing[@]}"; do
        dpkg -s "$p" 2>/dev/null | grep -q "^Status: install ok installed" || still_missing+=("$p")
    done
    if [ "${#still_missing[@]}" -eq 0 ]; then
        ok "系统依赖全部安装成功"
    else
        warn "未成功安装：${still_missing[*]}（语音/摄像头可能受限）"
    fi
}

# ─────────────────────────── Phase 10：修 requirements ───────────────────────────
fix_requirements() {
    step "核对依赖清单"
    cd "$PROJECT_DIR"
    [ -f requirements.txt ] || { warn "无 requirements.txt，跳过"; return 0; }

    # 旧版这里会往 requirements.txt 里给 win10toast/pypiwin32/pywin32 加
    # "sys_platform == win32" 标记 —— 但当前 requirements.txt 里**这三个包一个都没有**，
    # 属于永久空转（每次都打印"无需修改"）。改成一件真正有用的事：
    # 报告 venv 里缺哪些运行时依赖，以及 requirements.txt 是否漏声明。
    local miss="" pkg
    if [ -x "$VENV_DIR/bin/python" ]; then
        for pkg in Pillow numpy PyOpenGL PySide6 torch transformers peft accelerate; do
            "$VENV_DIR/bin/python" -c "
import importlib.util as u, sys
m={'Pillow':'PIL','PyOpenGL':'OpenGL','PySide6':'PySide6.QtWidgets'}.get('$pkg','$pkg')
sys.exit(0 if u.find_spec(m) else 1)" 2>/dev/null || miss="$miss $pkg"
        done
    fi
    if [ -n "$miss" ]; then
        warn "venv 里缺少：$miss"
        info "  可在程序的「环境向导 → 依赖」里一键安装，或："
        info "  ${VENV_DIR}/bin/python -m pip install$miss"
    else
        ok "venv 运行时依赖齐全"
    fi
}

# ─────────────────────────── Phase 11：torch ───────────────────────────
install_torch() {
    step "安装 PyTorch（$TORCH_VARIANT）"

    if [ "$TORCH_ALREADY_OK" = "1" ]; then
        ok "体检已确认 PyTorch 已装且匹配，跳过下载"
        python -c "import torch;print(f'  torch: {torch.__version__}  CUDA: {torch.version.cuda or \"cpu\"}')"
        return 0
    fi

    if [ "$PLATFORM_KIND" = "termux" ]; then
        run_install "pkg 安装 PyTorch" pkg install -y python-torch
        if python -c "import torch" 2>/dev/null; then
            ok "PyTorch 安装成功（$(python -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')）"
            python -c "import psutil" 2>/dev/null || run_install "安装 python-psutil" pkg install -y python-psutil
            run_install "安装 transformers/peft/accelerate" pip install transformers peft accelerate
            command -v clang >/dev/null 2>&1 || run_install "安装 clang（shim 需要）" pkg install -y clang
            return 0
        fi
        warn "pkg python-torch 无法导入，尝试 libomp ..."
        run_install "安装 libomp" pkg install -y libomp
        if python -c "import torch" 2>/dev/null; then
            ok "安装 libomp 后 PyTorch 可用"
            python -c "import psutil" 2>/dev/null || pkg install -y python-psutil
            pip install -q transformers peft accelerate 2>/dev/null || true
            return 0
        fi
        die "Termux 上 PyTorch 安装失败。"
    fi

    if python -c "import torch" 2>/dev/null; then
        local _cur_torch
        _cur_torch=$(python -c 'import torch;print(torch.__version__, torch.version.cuda or "cpu")' 2>/dev/null)
        info "已存在 torch（$_cur_torch），与目标方案 $TORCH_VARIANT 不匹配，准备重装"
        # 卸载前先冻结当前依赖清单：现有 torch 可能是用户用 uv 装的 CUDA 版，
        # 万一重装失败/装成 CPU 版，至少能用这份清单回退。
        if pip freeze > "$PROJECT_DIR/.venv_freeze_before_torch.txt" 2>/dev/null; then
            info "  已备份当前依赖清单 → .venv_freeze_before_torch.txt"
        fi
        # 清理旧版本，避免冲突
        run_install "卸载旧 torch 系列" pip uninstall -y torch torchvision torchaudio || true
    fi

    local attempt=0 max=2
    while [ "$attempt" -lt "$max" ]; do
        attempt=$((attempt+1))
        info "尝试 $attempt/$max ..."
        if run_install "pip 安装 PyTorch（$TORCH_VARIANT）" \
            pip install --upgrade torch torchvision torchaudio --index-url "$TORCH_INDEX"; then
            if pip show torch 2>/dev/null | grep -q "^Name: torch"; then
                ok "PyTorch 安装成功"; TORCH_ALREADY_OK=1; return 0
            fi
        fi
        warn "第 $attempt 次失败"
        sleep 2
    done

    if [[ "$TORCH_VARIANT" == rocm* ]]; then
        warn "ROCm 安装失败，回退 CPU"
        TORCH_VARIANT="cpu"
        TORCH_INDEX="${TORCH_INDEXES[cpu]}"
        run_install "pip 安装 CPU 版 PyTorch" \
            pip install --upgrade torch torchvision torchaudio --index-url "$TORCH_INDEX" \
            && { ok "CPU 版安装成功"; TORCH_ALREADY_OK=1; return 0; }
    fi
    die "PyTorch 安装失败。可试：export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 后重跑"
}

# ─────────────────────────── Phase 12：其他依赖 ───────────────────────────
install_other_deps() {
    step "安装模型与项目依赖"

    if [ "$ML_DEPS_ALREADY_OK" = "1" ]; then
        ok "体检已确认 ML 依赖齐全，跳过 pip 安装"
    else
        local ml=(transformers peft accelerate safetensors)
        info "ML 依赖：${ml[*]}"
        run_install "pip 安装 ML 依赖" pip install "${ml[@]}" || die "ML 依赖安装失败"

        local missing_ml=()
        for pkg in "${ml[@]}"; do
            pip show "$pkg" 2>/dev/null | grep -q "^Name: " || missing_ml+=("$pkg")
        done
        [ "${#missing_ml[@]}" -eq 0 ] && ok "ML 依赖齐全" || warn "缺：${missing_ml[*]}"
    fi

    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        cd "$PROJECT_DIR"
        info "项目 requirements ..."
        run_install "pip 安装项目 requirements" pip install -r requirements.txt \
            && ok "项目依赖完成" \
            || warn "部分项目依赖失败（通常不影响核心对话）"
    fi

    # edge-tts 在 requirements.txt 里是注释掉的，但它是语音朗读的默认引擎，
    # 程序首次启动也会自己装（xl.py 的 _ensure_deps）。这里顺手装上，省一次启动等待。
    if ! python -c "import edge_tts" 2>/dev/null; then
        run_install "pip 安装 edge-tts（情感语音）" pip install edge-tts \
            || warn "edge-tts 安装失败（语音朗读会退化，程序启动时会再试）"
    fi
}

# ─────────────────────────── Phase 13：应用模型选择 ───────────────────────────
apply_model_choice() {
    step "应用模型选择"
    [ -z "${MODEL_CHOICE:-}" ] && { info "未选择模型，跳过"; return 0; }

    # 甲-6：这里原先用 `sed -i` 直接改 xl.py 源码里的 "base_model" 硬编码值，
    # 每跑一次脚本就把工作区弄脏一次，还破坏升级判定。
    # 程序真正读的是 .star_core/model_choice.txt（xl.py 的 _select_model_on_start）
    # 以及 core/config.py 的 model.base_model，所以改成写这两处、不碰源码。
    local star="$PROJECT_DIR/.star_core"
    mkdir -p "$star" 2>/dev/null || true

    if printf '%s' "$MODEL_CHOICE" > "$star/model_choice.txt" 2>/dev/null; then
        ok "已写入 .star_core/model_choice.txt：$MODEL_CHOICE"
    else
        warn "写入 .star_core/model_choice.txt 失败（权限？）"
    fi

    # 同步到统一配置（走程序自己的 API，保证结构正确）
    if [ -x "$VENV_DIR/bin/python" ] && [ -f "$PROJECT_DIR/core/config.py" ]; then
        if XL_MODEL="$MODEL_CHOICE" "$VENV_DIR/bin/python" -c \
            "import os;from core import config;config.patch({'model':{'base_model':os.environ['XL_MODEL']}})" \
            >/dev/null 2>&1; then
            ok "已同步到 xiaoling_config.json"
        else
            info "未能同步到 xiaoling_config.json（程序首次启动会用 model_choice.txt）"
        fi
    fi
    info "注：本脚本不再修改 xl.py 源码，git 工作区保持干净。"
}

# ─────────────────────────── Phase 14：xl 启动命令 ───────────────────────────
setup_xl_cmd() {
    step "创建 xl 启动命令"
    local target_py="$VENV_DIR/bin/python"

    if ! command -v sudo >/dev/null 2>&1; then
        warn "无 sudo，无法写入 $XL_BIN"
        info "手动启动方式：cd $PROJECT_DIR && $target_py xl.py"
        return 0
    fi

    if [ -f "$XL_BIN" ] && grep -qF "$target_py" "$XL_BIN" && grep -qF "$PROJECT_DIR" "$XL_BIN"; then
        ok "$XL_BIN 已就绪（指向当前 venv）"; return 0
    fi

    [ -f "$XL_BIN" ] && { sudo cp "$XL_BIN" "$XL_BIN.bak.$(date +%s)" 2>/dev/null || true; info "已备份原 $XL_BIN"; }

    info "写入 $XL_BIN"
    # 甲-11：运行期补上 UTF-8 与 locale（原先只在安装期设过），
    # 并在启动前探测 PySide6，缺失时给一句可执行的提示而不是让用户面对 Qt 报错。
    printf '#!/bin/bash\n# 小凌启动器（由 setup_kali.sh 生成）\nexport PYTHONUTF8=1\nexport PYTHONIOENCODING=utf-8\ncd %q\nif ! %q -c "import PySide6.QtWidgets" >/dev/null 2>&1; then\n  echo "[提示] 缺少 PySide6，桌宠窗口不可用，将退化为命令行。"\n  echo "       修复：%q -m pip install PySide6"\nfi\nexec %q xl.py "$@"\n' \
        "$PROJECT_DIR" "$target_py" "$target_py" "$target_py" \
        | sudo tee "$XL_BIN" >/dev/null || die "写入 $XL_BIN 失败"
    sudo chmod +x "$XL_BIN" || die "chmod +x $XL_BIN 失败"

    if [ -x "$XL_BIN" ] && grep -qF "$target_py" "$XL_BIN"; then
        ok "$XL_BIN 就绪"
    else
        warn "$XL_BIN 写入但校验未通过"
    fi
}

# ─────────────────────────── Phase 15：打补丁 ───────────────────────────
patch_code() {
    step "检查代码内建能力（不再改源码）"
    cd "$PROJECT_DIR"
    local xlfile="$PROJECT_DIR/xl.py"

    if [ ! -f "$xlfile" ]; then
        warn "未找到 xl.py，跳过"
        return 0
    fi

    # 乙-4 / 乙-5：这里原先会往 xl.py 里“盲插”补丁（XL_ALLOW_UPDATE 开关、
    # stdin UTF-8 容错），另有一段匹配 -transparentcolor 的补丁早已失效（源码里
    # 根本没有那个字符串，只会静默打印“未出现，跳过”）。
    # 现在这些能力**已经内建在源码里**，脚本再改源码只会弄脏 git 工作区、
    # 破坏可复现性与升级判定，所以这里只“检查”，不再修改任何文件。
    local missing=0
    if grep -q 'XL_ALLOW_UPDATE' "$xlfile"; then
        ok "  自动更新开关：源码已内建（XL_ALLOW_UPDATE）"
    else
        warn "  自动更新开关：源码里没有 XL_ALLOW_UPDATE（可能是旧版 xl.py）"
        missing=1
    fi
    if grep -q 'sys.stdin.reconfigure' "$xlfile"; then
        ok "  UTF-8 容错：源码已内建（stdin + stdout）"
    else
        warn "  UTF-8 容错：源码里没有 sys.stdin.reconfigure"
        missing=1
    fi
    if grep -q 'XL_NO_AUTO_DEPS' "$xlfile"; then
        ok "  依赖安装开关：源码已内建（XL_NO_AUTO_DEPS / 默认不自动装 torch）"
    else
        warn "  依赖安装开关：源码里没有 XL_NO_AUTO_DEPS"
        missing=1
    fi
    if [ "$missing" = "1" ]; then
        info "  源码版本偏旧：建议 git pull 更新；本脚本不再替它打补丁。"
    fi

    if python3 -c "import ast; ast.parse(open('$xlfile', encoding='utf-8').read())" 2>/dev/null; then
        ok "xl.py 语法通过"
    else
        die "xl.py 语法错误，请先修复源码（本脚本已不再修改源码，无法自动恢复）"
    fi
}

# ─────────────────────────── Phase 16：验证 ───────────────────────────
verify() {
    step "验证安装"
    cd "$PROJECT_DIR"

    # ── 核心：torch / 训练依赖 ──
    # 乙-2 之后 torch 系是「可选」的：缺了不影响桌宠与对话，只影响本地推理/蒸馏，
    # 所以这里不再 die，只警告。
    if ! python - <<'PYEOF'
import sys
try:
    import torch
except ImportError as e:
    print(f"  [ERROR] import torch 失败：{e}"); sys.exit(1)
print(f"  [OK] torch        : {torch.__version__}")
if torch.cuda.is_available():
    print(f"  [OK] CUDA         : {torch.cuda.get_device_name(0)}")
    print(f"      计算能力     : sm_{''.join(map(str, torch.cuda.get_device_capability(0)))}")
    print(f"      显存         : {torch.cuda.get_device_properties(0).total_memory//1048576} MB")
else:
    print(f"  [WARN] CUDA 不可用，将走 CPU")
for mod in ("transformers", "peft", "accelerate", "safetensors"):
    try:
        m = __import__(mod)
        print(f"  [OK] {mod:<13}: {getattr(m,'__version__','?')}")
    except ImportError:
        print(f"  [WARN] {mod:<13}: 缺失（本地推理/蒸馏训练不可用，桌宠不受影响）")
PYEOF
    then
        warn "torch 不可用（桌宠与对话仍可正常运行；需要时在程序「环境向导」里装）"
    fi

    # ── 甲-3：GUI 组件必须单独验 ──
    # 旧版 verify 只验 torch 系，于是"PySide6 没装、桌宠根本打不开"也会打印配置成功。
    local gui_ok=1
    if python -c "import PySide6.QtWidgets" 2>/dev/null; then
        ok "PySide6 可用（桌宠窗口 / 训练工作台）"
    else
        warn "PySide6 不可用：桌宠窗口与工作台无法启动（会退化为命令行）"
        info "  修复：${VENV_DIR}/bin/python -m pip install PySide6（或运行程序的「环境向导」）"
        gui_ok=0
    fi
    if python -c "import OpenGL.GL" 2>/dev/null; then
        ok "PyOpenGL 可用（3D 渲染）"
    else
        warn "PyOpenGL 不可用：3D 渲染将退化为 numpy 软件光栅"
        info "  修复：${VENV_DIR}/bin/python -m pip install PyOpenGL"
    fi
    if [ "$gui_ok" = "1" ]; then
        if python -c "from core.avatar import run_headless_probe as p; raise SystemExit(0 if (p() or {}).get('ok') else 1)" >/dev/null 2>&1; then
            ok "渲染层无头探针通过"
        else
            info "渲染层无头探针未通过（无显示器/无 GL 时属正常，运行时会自动降级）"
        fi
    fi

    # ── 模型权重：与 xl.py 同口径（任意 *.safetensors / *.bin）──
    local mdir="$PROJECT_DIR/$MODEL_DIR_REL" found=""
    found=$(find_weight_in "$mdir") || true
    if [ -n "$found" ]; then
        MODEL_FILE="$found"
        ok "模型权重：$(basename "$found")（$(human_size "$(stat -c%s "$found")")）"
    else
        info "尚未放置基底权重（放进 $mdir，或让程序首次启动自动下载）"
    fi
}

# ─────────────────────────── Phase 17：权限修复 ───────────────────────────
fix_ownership() {
    step "权限修复"
    cd "$PROJECT_DIR"
    local bad
    bad=$(find . ! -user "$(id -un)" 2>/dev/null | head -5)
    if [ -n "$bad" ]; then
        warn "发现非当前用户所属："
        echo "$bad" | sed 's/^/      /'
        command -v sudo >/dev/null 2>&1 && sudo chown -R "$(id -un):$(id -gn)" "$PROJECT_DIR" && ok "已修复"
    else
        ok "属主正常"
    fi
}

# ─────────────────────────── Phase 18：汇总 ───────────────────────────
summary() {
    printf "\n"
    printf "${CLR_BLUE}╔════════════════════════════════════════════════════════════════╗${CLR_RESET}\n"
    if [ "$WARN_COUNT" -eq 0 ]; then
        printf "${CLR_BLUE}║                          配置完成                             ║${CLR_RESET}\n"
    else
        printf "${CLR_YELLOW}║                   配置完成（%s 条警告）                     ║${CLR_RESET}\n" "$WARN_COUNT"
    fi
    printf "${CLR_BLUE}╚════════════════════════════════════════════════════════════════╝${CLR_RESET}\n"
    cat <<EOF

  ─── 环境 ───
    平台           : $PLATFORM_KIND ($OS_NAME)
    Python         : $PY_VER
    GPU            : ${GPU_NAME:-无（CPU 模式）}
    PyTorch 方案   : $TORCH_VARIANT
    模型选择       : ${MODEL_CHOICE:-未选择}

  ─── 路径 ───
    项目目录       : $PROJECT_DIR
    虚拟环境       : $VENV_DIR
    模型文件       : $MODEL_FILE
    日志           : $LOG_FILE
    备份           : $BACKUP_DIR
    启动命令       : $XL_BIN

  ─── 启动小凌 ───
    在任意目录直接运行：  xl
    关闭自动更新：        XL_ALLOW_UPDATE=0 xl
    手动激活 venv：       source $VENV_DIR/bin/activate

  ─── 诊断 ───
    $VENV_DIR/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
    ls -la $MODEL_FILE
    tail -100 $LOG_FILE
EOF
}

# ─────────────────────────── 主流程 ───────────────────────────
main() {
    check_root
    log_init
    printf "  小凌环境预检 + 部署 v3.6（可选步骤）\n"
    printf "  %s\n\n" "$(date '+%Y-%m-%d %H:%M:%S')"

    check_sudo
    select_model_size
    detect_env
    select_profile
    deploy_project
    preflight_check
    place_model
    configure_api
    check_prereq
    backup_data
    setup_venv
    install_sysdeps
    fix_requirements
    install_torch
    install_other_deps
    apply_model_choice
    setup_xl_cmd
    patch_code
    verify
    fix_ownership
    summary

    printf "\n"
    printf "${CLR_GREEN}================================================================${CLR_RESET}\n"
    if [ "$API_CONFIGURED" -eq 1 ] || [ "$API_ALREADY_OK" -eq 1 ]; then
        printf "${CLR_GREEN}  [SUCCESS] 配置成功！API Key 已就绪，环境部署完毕。${CLR_RESET}\n"
    else
        printf "${CLR_YELLOW}  [SUCCESS] 环境部署完毕，但未配置 API Key（不影响聊天与桌宠）。${CLR_RESET}\n"
        printf "${CLR_YELLOW}  直接启动小凌即可，程序会弹出「环境配置向导」让你在窗口里填写。${CLR_RESET}\n"
        printf "${CLR_YELLOW}  写入位置：$PROJECT_DIR/.star_core/xiaoling_config.json 的 deepseek_api_key${CLR_RESET}\n"
    fi
    printf "${CLR_GREEN}  输入命令 'xl' 即可启动小凌。${CLR_RESET}\n"
    printf "${CLR_GREEN}  常用：xl --dashboard（训练工作台）  xl --growth（成长报告）  xl --selftest（全系统体检）${CLR_RESET}\n"
    printf "${CLR_GREEN}================================================================${CLR_RESET}\n\n"
    printf "  日志：%s\n\n" "$LOG_FILE"

    log_close
    exit 0
}

main "$@"