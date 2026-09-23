#!/usr/bin/env bash
# ============================================================
#  小凌一键部署 + 配置 v3.1（Kali/Linux/WSL2 新手向）
#  修复：自动更新开关缩进致命 bug / apt 退出码 / root 检测时机
#       官网自动下载 / 模型引导 / 校验逻辑
# ============================================================
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
SCRIPT_NAME="$(basename "$SCRIPT_PATH")"
LOG_FILE="$SCRIPT_DIR/peizhi.log"

# 用户输入（可被环境变量覆盖）
PROJECT_DIR="${PROJECT_DIR:-}"
PROFILE_OVERRIDE="${XL_PROFILE:-}"
XL_BIN="${XL_BIN:-/usr/local/bin/xl}"
# 官网下载源（更新包 + 版本信息）
OFFICIAL_URL="https://xiaoling-4o6.pages.dev/update/xiaoling_latest.zip"
VERSION_URL="https://xiaoling-4o6.pages.dev/update/version.json"

# 项目内部结构（相对项目根）
VENV_REL=".venv"
MODEL_REL=".star_core/XLmodel/model.safetensors"
MODEL_MIN_SIZE=104857600        # 100MB，小于此视为占位文件

# zip 与 model 的候选名（在脚本目录里按顺序找）
ZIP_CANDIDATES=("XL-main.zip" "xiaoling-app-main.zip" "xiaoling.zip" "XL.zip" "XLmodel-main.zip")
MODEL_CANDIDATES=("model.safetensors")

# PyTorch wheel 索引
declare -A TORCH_INDEXES=(
    [cu128]="https://download.pytorch.org/whl/cu128"
    [cu124]="https://download.pytorch.org/whl/cu124"
    [cu121]="https://download.pytorch.org/whl/cu121"
    [cu118]="https://download.pytorch.org/whl/cu118"
    [rocm6.2]="https://download.pytorch.org/whl/rocm6.2"
    [cpu]="https://download.pytorch.org/whl/cpu"
)

# ─────────────────────────── 状态 ───────────────────────────
STEP_TOTAL=16
STEP_CURRENT=0
HAS_NVIDIA=0; HAS_AMD=0
GPU_NAME=""; GPU_DRIVER=""; COMPUTE_CAP=""
TORCH_VARIANT=""; TORCH_INDEX=""
PLATFORM_KIND=""; OS_NAME=""; PY_VER=""
BACKUP_DIR=""
WARN_COUNT=0; ERR_COUNT=0
VENV_DIR=""; MODEL_FILE=""

# ─────────────────────────── 日志 ───────────────────────────
log_init() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    exec 3>&1 4>&2
    exec > >(tee -a "$LOG_FILE") 2>&1
    {
        echo ""
        echo "################################################################"
        echo "#  小凌一键部署  $(date '+%Y-%m-%d %H:%M:%S')"
        echo "#  用户：$(id -un)@$(hostname)   PID：$$"
        echo "#  脚本：$SCRIPT_PATH"
        echo "#  工作目录：$SCRIPT_DIR"
        echo "#  日志：$LOG_FILE"
        echo "################################################################"
    }
}

log_close() { exec 1>&3 2>&4; sleep 0.3; }

info() { echo "  [i] $*"; }
ok()   { echo "  [✓] $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); echo "  [!] $*"; }
err()  { ERR_COUNT=$((ERR_COUNT+1));  echo "  [✗] $*" >&2; }

step() {
    STEP_CURRENT=$((STEP_CURRENT+1))
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  [$STEP_CURRENT/$STEP_TOTAL] $*"
    echo "════════════════════════════════════════════════════════════════"
}

die() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    配置中止（严重错误）                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo "  错误：$*"
    echo "  时间：$(date '+%Y-%m-%d %H:%M:%S')"
    echo "  日志：$LOG_FILE"
    echo ""
    echo "  诊断："
    echo "    tail -100 \"$LOG_FILE\""
    echo "    把整个日志文件发给开发者"
    echo ""
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

# ─────────────────────────── Phase 0：root 检测（提前拦截） ───────────────────────────
check_root() {
    # v3.1 fix：root 检测放最前面，避免 root 用户在解压/建 venv 阶段污染文件系统
    if [ "$(id -u)" -eq 0 ]; then
        echo ""
        echo "╔════════════════════════════════════════════════════════════════╗"
        echo "║                 请勿用 root 运行本脚本！                        ║"
        echo "╚════════════════════════════════════════════════════════════════╝"
        echo "  原因：root 创建的 venv 和文件属主会是 root，"
        echo "        普通用户之后无法读写、无法启动小凌。"
        echo ""
        echo "  正确做法（三选一）："
        echo "    1) 用普通用户运行：  su - \$USER -c 'bash $SCRIPT_NAME'"
        echo "    2) 退出 root 后重跑： exit  然后  bash $SCRIPT_NAME"
        echo "    3) 新建普通用户：     sudo useradd -m xl && sudo passwd xl"
        echo "                          su - xl -c 'bash $SCRIPT_NAME'"
        echo ""
        exit 1
    fi
    ok "用户：$(id -un)（非 root，安全）"
}

# ─────────────────────────── Phase 0.5：选择模型大小 ───────────────────────────
select_model_size() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              选择你的小凌基底模型（自研档位）                    ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  根据你的设备选择想自研的模型大小："
    echo ""
    echo "    [1] 自研 2B 模型（默认）  MiniCPM5-2B  约 4.8GB  手机/电脑流畅，端侧最强"
    echo "    [2] 自研 1B 模型          MiniCPM5-1B  约 2.1GB  低配设备，轻量"
    echo ""
    echo -n "  请输入序号 [1-2，默认 1]："
    read -r choice
    case "${choice:-1}" in
        2) MODEL_CHOICE="自研1B模型" ;;
        *) MODEL_CHOICE="自研2B模型" ;;
    esac
    echo ""
    echo "  [✓] 已选择：$MODEL_CHOICE"
    echo "      （如需更换，重跑本脚本或改 xl.py 顶部 CONFIG['model']['base_model']）"
    echo ""
}

# ─────────────────────────── Phase 1：环境检测 ───────────────────────────
detect_env() {
    step "环境检测"

    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        OS_NAME="${PRETTY_NAME:-unknown}"
    fi
    info "操作系统：$OS_NAME"
    info "内核：$(uname -r)"

    if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
        PLATFORM_KIND="termux"
        info "运行环境：Termux（安卓）"
        info "包管理器：pkg（Termux 专用，勿用 apt）"
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
    if command -v free >/dev/null 2>&1; then
        info "内存：$(free -h | awk '/^Mem:/ {print $2" 总量 / "$7" 可用"}')"
    fi
    local avail
    avail=$(df -B1 "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "${avail:-}" ]; then
        info "脚本目录可用磁盘：$(human_size "$avail")"
        [ "$avail" -lt 5368709120 ] && warn "磁盘可用 < 5GB，PyTorch + 模型可能空间不足"
    fi

    command -v python3 >/dev/null 2>&1 || die "找不到 python3。请先：sudo apt install -y python3 python3-venv python3-full"
    PY_VER=$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    info "系统 Python：$PY_VER（$(command -v python3)）"
    case "$PY_VER" in
        3.10|3.11|3.12) ok "Python 版本适配良好" ;;
        3.13) warn "Python 3.13 部分 wheel 可能未跟上；如失败可 apt install python3.12-venv 后重跑" ;;
        *) warn "Python $PY_VER 未在测试范围内" ;;
    esac

    python3 -c "import venv" >/dev/null 2>&1 || die "Python 缺 venv 模块。请：sudo apt install -y python3-venv python3-full"

    detect_gpu
}

detect_gpu() {
    echo ""
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
                die "检测到 Blackwell(50系) 但驱动 $GPU_DRIVER < 570。请升级 Windows/Linux NVIDIA 驱动后重启 WSL 再试。"
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
            command -v rocminfo >/dev/null 2>&1 && info "  ROCm 已安装" || warn "  ROCm 未安装，尝试安装（失败自动回退 CPU）"
        fi
    fi

    if [ "$HAS_NVIDIA" = "0" ] && [ "$HAS_AMD" = "0" ]; then
        warn "未检测到独立显卡，将使用 CPU（推理较慢，功能完整）"
    fi
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
            TORCH_VARIANT="cu128"
            info "50 系（sm_120）→ cu128（Blackwell 必需）"
        elif [ "$drv_major" -ge 550 ]; then
            TORCH_VARIANT="cu124"; info "30/40 系 + 驱动 $GPU_DRIVER → cu124"
        elif [ "$drv_major" -ge 525 ]; then
            TORCH_VARIANT="cu121"; info "30/40 系 + 老驱动 → cu121"
        else
            TORCH_VARIANT="cu118"; warn "驱动 $GPU_DRIVER 较旧 → cu118（建议升级驱动）"
        fi
    elif [ "$HAS_AMD" = "1" ]; then
        TORCH_VARIANT="rocm6.2"; warn "AMD 方案 ROCm 6.2（失败自动回退 CPU）"
    else
        TORCH_VARIANT="cpu"; info "纯 CPU 模式"
    fi

    TORCH_INDEX="${TORCH_INDEXES[$TORCH_VARIANT]:-}"
    [ -z "$TORCH_INDEX" ] && die "内部错误：未知 TORCH_VARIANT=$TORCH_VARIANT"
    ok "方案：$TORCH_VARIANT"
    info "  索引源：$TORCH_INDEX"
}

# ─────────────────────────── Phase 3：部署项目 ───────────────────────────
find_project_dir() {
    # 优先：环境变量
    if [ -n "${PROJECT_DIR:-}" ] && [ -f "$PROJECT_DIR/xl.py" ]; then
        return 0
    fi
    # 脚本目录本身就是项目
    if [ -f "$SCRIPT_DIR/xl.py" ]; then
        PROJECT_DIR="$SCRIPT_DIR"; return 0
    fi
    # 脚本目录下的一级子目录含 xl.py
    local d
    for d in "$SCRIPT_DIR"/*/; do
        [ -d "$d" ] || continue
        if [ -f "$d/xl.py" ]; then
            PROJECT_DIR="${d%/}"; return 0
        fi
    done
    return 1
}

find_zip() {
    local name
    for name in "${ZIP_CANDIDATES[@]}"; do
        [ -f "$SCRIPT_DIR/$name" ] && { echo "$SCRIPT_DIR/$name"; return 0; }
    done
    # v3.1 fix：匹配 xiaoling_v*.zip 发布包（xiaoling_v0.0.7_release.zip 等）
    local z
    z=$(find "$SCRIPT_DIR" -maxdepth 1 -type f \( -name 'xiaoling_v*.zip' -o -name 'XLmodel*.zip' \) 2>/dev/null | head -1)
    [ -n "$z" ] && { echo "$z"; return 0; }
    # 通配兜底
    z=$(find "$SCRIPT_DIR" -maxdepth 1 -type f -name '*.zip' 2>/dev/null | head -1)
    [ -n "$z" ] && { echo "$z"; return 0; }
    return 1
}

download_official() {
    # v3.1：从官网自动下载最新发布包（新手不需要自己准备 zip）
    info "本地没有 zip，尝试从官网自动下载最新版..."
    command -v curl >/dev/null 2>&1 || { warn "无 curl，无法自动下载"; return 1; }
    command -v unzip >/dev/null 2>&1 || { warn "无 unzip，无法自动解压"; return 1; }

    # 先看官网版本信息
    local ver
    ver=$(curl -s --max-time 10 "$VERSION_URL" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("version",""))' 2>/dev/null)
    info "官网最新版本：${ver:-未知}"

    local zip_path="$SCRIPT_DIR/xiaoling_latest_download.zip"
    info "下载中：$OFFICIAL_URL"
    if ! curl -sL --max-time 300 -o "$zip_path" "$OFFICIAL_URL"; then
        warn "官网下载失败（网络/被墙？）"
        rm -f "$zip_path"
        return 1
    fi
    if [ ! -s "$zip_path" ]; then
        warn "官网下载为空文件"
        rm -f "$zip_path"
        return 1
    fi
    local sz; sz=$(stat -c%s "$zip_path")
    info "下载完成：$(human_size "$sz")"

    # 解压
    local before after newdir
    before=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    (cd "$SCRIPT_DIR" && unzip -q -o "$zip_path") || { warn "解压失败"; rm -f "$zip_path"; return 1; }
    after=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    newdir=$(comm -13 <(echo "$before") <(echo "$after") | head -1)

    rm -f "$zip_path"
    if [ -n "$newdir" ] && [ -f "$SCRIPT_DIR/$newdir/xl.py" ]; then
        PROJECT_DIR="$SCRIPT_DIR/$newdir"
        ok "官网下载并解压 → $PROJECT_DIR"
        return 0
    fi
    if find_project_dir; then
        ok "官网下载解压后找到项目 → $PROJECT_DIR"
        return 0
    fi
    warn "官网包解压后未找到 xl.py"
    return 1
}

deploy_project() {
    step "部署项目"

    if find_project_dir; then
        ok "已找到项目目录：$PROJECT_DIR"
        return 0
    fi

    warn "未找到已解压的项目，尝试从 zip 解压"
    local zip
    if ! zip=$(find_zip); then
        warn "脚本目录里没有 zip 包"
        # v3.1：尝试官网自动下载
        download_official && return 0
        die "未找到项目或 zip。
    请任选一种方式：
      1) 从官网下载发布包放到本目录：
         https://xiaoling-4o6.pages.dev/
      2) 或把 XL-main.zip 放到：$SCRIPT_DIR
      3) 或直接解压出含 xl.py 的目录放在这里"
    fi
    info "找到 zip：$zip"

    if ! command -v unzip >/dev/null 2>&1; then
        warn "未安装 unzip，尝试安装"
        if command -v apt >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
            sudo apt update -qq 2>/dev/null && sudo apt install -y unzip || die "安装 unzip 失败"
        else
            die "系统没有 unzip 命令，请手动安装：sudo apt install unzip"
        fi
    fi

    # 记录解压前的一级条目，解压后对比找出新目录
    local before after newdir
    before=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    info "解压中（可能耗时数秒）..."
    (cd "$SCRIPT_DIR" && unzip -q -o "$zip") || die "解压失败：$zip"
    after=$(cd "$SCRIPT_DIR" && ls -1 2>/dev/null | sort)
    newdir=$(comm -13 <(echo "$before") <(echo "$after") | head -1)

    if [ -n "$newdir" ] && [ -f "$SCRIPT_DIR/$newdir/xl.py" ]; then
        PROJECT_DIR="$SCRIPT_DIR/$newdir"
        ok "解压完成 → $PROJECT_DIR"
    elif find_project_dir; then
        ok "解压完成 → $PROJECT_DIR"
    else
        die "解压成功但未找到 xl.py，zip 内容可能异常。
    请检查 $SCRIPT_DIR 下的目录结构。"
    fi
}

# ─────────────────────────── Phase 4：放置模型 ───────────────────────────
find_model_source() {
    local name p
    # 脚本目录根
    for name in "${MODEL_CANDIDATES[@]}"; do
        p="$SCRIPT_DIR/$name"
        [ -f "$p" ] && [ "$(stat -c%s "$p" 2>/dev/null || echo 0)" -gt "$MODEL_MIN_SIZE" ] && { echo "$p"; return 0; }
    done
    # 脚本目录一级子目录
    local d
    for d in "$SCRIPT_DIR"/*/; do
        p="${d}model.safetensors"
        [ -f "$p" ] && [ "$(stat -c%s "$p" 2>/dev/null || echo 0)" -gt "$MODEL_MIN_SIZE" ] && { echo "$p"; return 0; }
    done
    # 常见备份路径
    for p in "$HOME/xiaoling1/model.safetensors" "$HOME/xiaoling/model.safetensors" \
             "$HOME/xiaoling1/.star_core/XLmodel/model.safetensors"; do
        [ -f "$p" ] && [ "$(stat -c%s "$p" 2>/dev/null || echo 0)" -gt "$MODEL_MIN_SIZE" ] && { echo "$p"; return 0; }
    done
    # 深搜
    p=$(find "$SCRIPT_DIR" -maxdepth 3 -type f -name 'model.safetensors' -size +100M 2>/dev/null | head -1)
    [ -n "$p" ] && { echo "$p"; return 0; }
    return 1
}

place_model() {
    step "放置模型权重"
    MODEL_FILE="$PROJECT_DIR/$MODEL_REL"
    mkdir -p "$(dirname "$MODEL_FILE")"

    local cur_size=0
    if [ -f "$MODEL_FILE" ]; then
        cur_size=$(stat -c%s "$MODEL_FILE" 2>/dev/null || echo 0)
    fi

    if [ "$cur_size" -gt "$MODEL_MIN_SIZE" ]; then
        ok "模型已就位：$(human_size "$cur_size")"
        return 0
    fi

    if [ "$cur_size" -gt 0 ]; then
        warn "现有 model.safetensors 是占位文件（$(human_size "$cur_size")），需要替换"
    else
        info "项目内暂无模型文件"
    fi

    local src
    if ! src=$(find_model_source); then
        # v3.1 fix：引导更明确（QQ 群）
        warn "未找到有效的 model.safetensors（需要 >100MB）"
        echo ""
        echo "  ═══════════════════════════════════════════════"
        echo "   【模型获取方式】"
        echo "   1. 加入 QQ 社区群：1057895186（小凌社区1群）"
        echo "      群文件里有完整 model.safetensors 权重"
        echo "   2. 下载后放到：$SCRIPT_DIR"
        echo "      或直接复制到：$MODEL_FILE"
        echo ""
        echo "   （也可以先继续配置，缺模型时小凌以'无基底权重'"
        echo "     模式运行，对话能力有限，装好模型后重启即可）"
        echo "  ═══════════════════════════════════════════════"
        echo ""
        return 0
    fi

    info "找到权重：$src（$(human_size "$(stat -c%s "$src")")）"
    info "复制到：$MODEL_FILE"
    if command -v rsync >/dev/null 2>&1; then
        rsync -ah --progress "$src" "$MODEL_FILE" || cp "$src" "$MODEL_FILE" || die "复制模型失败"
    else
        cp "$src" "$MODEL_FILE" || die "复制模型失败（磁盘空间？）"
    fi
    ok "模型就位：$(human_size "$(stat -c%s "$MODEL_FILE")")"
}

# ─────────────────────────── Phase 5：前置检查 ───────────────────────────
check_prereq() {
    step "前置检查"
    command -v sudo >/dev/null 2>&1 && ok "sudo 可用" || warn "无 sudo，系统依赖与 /usr/local/bin/xl 将无法安装"

    if curl -sI --max-time 5 https://pypi.org >/dev/null 2>&1; then
        ok "PyPI 可达"
    else
        warn "PyPI 不可达（网络/代理问题）"
    fi
    if [ "$TORCH_VARIANT" != "cpu" ] && [ "$TORCH_VARIANT" != "rocm6.2" ]; then
        curl -sI --max-time 5 "$TORCH_INDEX" >/dev/null 2>&1 \
            && ok "PyTorch 源可达" \
            || warn "PyTorch 源 $TORCH_INDEX 不可达"
    fi

    cd "$PROJECT_DIR"
    VENV_DIR="$PROJECT_DIR/$VENV_REL"
}

# ─────────────────────────── Phase 6：备份 ───────────────────────────
backup_data() {
    step "备份关键数据"
    BACKUP_DIR="$HOME/xl_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cd "$PROJECT_DIR"
    local saved=0
    for f in xl_memory.json requirements.txt xl.py pet.py; do
        [ -f "$f" ] && cp "$f" "$BACKUP_DIR/" 2>/dev/null && saved=$((saved+1))
    done
    [ -d data ] && cp -r data "$BACKUP_DIR/" 2>/dev/null && saved=$((saved+1))
    ok "已备份 $saved 项 → $BACKUP_DIR"
}

# ─────────────────────────── Phase 7：venv ───────────────────────────
setup_venv() {
    step "准备虚拟环境"
    if [ -x "$VENV_DIR/bin/python" ]; then
        ok "复用已有 venv：$VENV_DIR"
    else
        [ -e "$VENV_DIR" ] && { warn "$VENV_DIR 存在但不可用，删除重建"; rm -rf "$VENV_DIR"; }
        info "创建 venv ..."
        run_or_die python3 -m venv "$VENV_DIR"
        ok "venv 创建：$VENV_DIR"
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    ok "已激活：$(which python)  ($(python -V 2>&1))"

    export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_PROGRESS_BAR=on
    export PYTHONIOENCODING=utf-8 LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

    info "升级 pip/wheel ..."
    pip install -U pip wheel 2>&1 | tail -3
    ok "pip：$(pip --version | awk '{print $2}')"
}

# ─────────────────────────── Phase 8：系统依赖 ───────────────────────────
install_sysdeps() {
    step "安装系统依赖（语音/音频/图像/Tk）"

    # v3.3 fix：Termux 专用（pkg 预编译，含 libomp 修复 torch 导入）
    if [ "$PLATFORM_KIND" = "termux" ]; then
        info "Termux 环境：使用 pkg 安装系统依赖"
        pkg update -y 2>&1 | tail -1 || warn "pkg update 失败（网络问题，继续）"
        pkg install -y python python-pip curl unzip python-numpy python-pillow clang 2>&1 | tail -2 || {
            warn "pkg 安装基础依赖失败"
        }
        # clang: 编译 PyBaseObject_Type shim（Termux tokenizers ABI 修复）必需
        # libomp：Termux torch 导入必需（否则报 libomp.so not found）
        pkg install -y libomp 2>&1 | tail -1 || warn "libomp 安装失败（torch 导入可能需要）"
        # python-psutil：peft 的依赖，Termux 上 pip 编译必失败（platform android not supported），必须 pkg 装预编译
        pkg install -y python-psutil 2>&1 | tail -1 || warn "python-psutil 安装失败（peft 依赖，可用 pkg install python-psutil）"
        ok "Termux 系统依赖安装完成"
        return 0
    fi

    if ! command -v apt >/dev/null 2>&1; then
        warn "非 Debian 系，跳过"; return 0
    fi
    local pkgs=(espeak-ng libespeak1 libportaudio2 python3-tk ffmpeg rsync unzip)
    # v3.1 fix：分开执行 apt update，避免管道吞退出码
    if ! sudo apt update -qq 2>&1 | tail -2; then
        warn "apt update 失败（不致命，继续）"
    fi

    local missing=()
    for p in "${pkgs[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
    if [ "${#missing[@]}" -eq 0 ]; then ok "系统依赖齐全"; return 0; fi

    info "安装缺失：${missing[*]}"
    sudo apt install -y --no-install-recommends "${missing[@]}" \
        && ok "系统依赖安装成功" \
        || warn "系统依赖部分失败，语音/摄像头可能受限"
}

# ─────────────────────────── Phase 9：修 requirements ───────────────────────────
fix_requirements() {
    step "修复 requirements.txt"
    cd "$PROJECT_DIR"
    [ -f requirements.txt ] || { warn "无 requirements.txt，跳过"; return 0; }
    local changed=0
    for pkg in win10toast pypiwin32 pywin32; do
        if grep -qE "^[[:space:]]*${pkg}" requirements.txt && ! grep -qE "${pkg}.*sys_platform" requirements.txt; then
            sed -i -E "s|^([[:space:]]*${pkg}.*)\$|\1; sys_platform == \"win32\"|" requirements.txt
            changed=1
        fi
    done
    [ "$changed" -eq 1 ] && ok "已加平台标记（仅 Windows 安装）" || ok "无需修改"
}

# ─────────────────────────── Phase 10：torch ───────────────────────────
install_torch() {
    step "安装 PyTorch（$TORCH_VARIANT）"

    # v3.3 fix：Termux 专用（pkg 预编译 torch，pip 编译必失败）
    if [ "$PLATFORM_KIND" = "termux" ]; then
        info "Termux 环境：使用 pkg 安装预编译 PyTorch"
        pkg install -y python-torch 2>&1 | tail -1
        if python -c "import torch" 2>/dev/null; then
            ok "PyTorch 安装成功（$(python -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')）"
            # 其余 AI 依赖走 pip；先确保 psutil（peft 依赖，Termux 必须 pkg 装预编译）
            if ! python -c "import psutil" 2>/dev/null; then
                info "安装 python-psutil（peft 依赖，Termux 预编译）..."
                pkg install -y python-psutil 2>&1 | tail -1 || warn "pkg install python-psutil 失败"
            fi
            info "安装 transformers / peft / accelerate ..."
            pip install -q transformers peft accelerate 2>&1 | tail -1 || warn "pip 安装 AI 依赖失败，可稍后手动：pkg install python-psutil && pip install transformers peft accelerate"
            # v3.4 fix：Termux 上 Rust tokenizers 二进制 ABI 不兼容（PyBaseObject_Type）
            # 已内置 shim 方案（clang --defsym 注入符号），保留 Rust 加速分词
            # 确保 clang 可用（编译 shim 必需）
            if ! command -v clang >/dev/null 2>&1; then
                warn "clang 缺失，安装中（shim 编译需要）..."
                pkg install -y clang 2>&1 | tail -1 || warn "clang 安装失败（tokenizers 可能需降级）"
            fi
            return 0
        fi
        warn "pkg python-torch 安装后仍无法导入，尝试 libomp ..."
        pkg install -y libomp 2>&1 | tail -1
        if python -c "import torch" 2>/dev/null; then
            ok "安装 libomp 后 PyTorch 可用"
            if ! python -c "import psutil" 2>/dev/null; then
                pkg install -y python-psutil 2>&1 | tail -1 || true
            fi
            pip install -q transformers peft accelerate 2>&1 | tail -1 || true
            return 0
        fi
        die "Termux 上 PyTorch 安装失败。请手动执行：pkg install python-torch libomp python-psutil && pip install transformers peft accelerate"
    fi

    if python -c "import torch" 2>/dev/null; then
        info "已存在：$(python -c 'import torch;print(torch.__version__)')，尝试升级"
    fi

    local attempt=0 max=2
    while [ "$attempt" -lt "$max" ]; do
        attempt=$((attempt+1))
        info "尝试 $attempt/$max ..."
        if pip install --progress-bar on --upgrade \
                torch torchvision torchaudio --index-url "$TORCH_INDEX"; then
            ok "PyTorch 安装成功"; return 0
        fi
        warn "第 $attempt 次失败"
        sleep 2
    done

    if [[ "$TORCH_VARIANT" == rocm* ]]; then
        warn "ROCm 安装失败，回退 CPU"
        TORCH_VARIANT="cpu"
        TORCH_INDEX="${TORCH_INDEXES[cpu]}"
        pip install --progress-bar on --upgrade torch torchvision torchaudio \
            --index-url "$TORCH_INDEX" && { ok "CPU 版安装成功"; return 0; }
    fi
    die "PyTorch 安装失败。可试：export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 后重跑"
}

# ─────────────────────────── Phase 11：其他依赖 ───────────────────────────
install_other_deps() {
    step "安装模型与项目依赖"
    local ml=(transformers peft accelerate safetensors sentencepiece)
    info "ML 依赖：${ml[*]}"
    pip install --progress-bar on "${ml[@]}" || die "ML 依赖安装失败"

    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        cd "$PROJECT_DIR"
        info "项目 requirements ..."
        pip install --progress-bar on -r requirements.txt \
            && ok "项目依赖完成" \
            || warn "部分项目依赖失败（通常不影响核心对话）"
    fi
}

# ─────────────────────────── Phase 11.5：应用模型选择 ───────────────────────────
apply_model_choice() {
    if [ -z "${MODEL_CHOICE:-}" ]; then
        return 0
    fi
    local xlfile="$PROJECT_DIR/xl.py"
    [ -f "$xlfile" ] || return 0
    # 把 CONFIG 里的 base_model 改成用户选择
    if grep -q '"base_model"' "$xlfile"; then
        sed -i "s|\"base_model\": \"[^\"]*\"|\"base_model\": \"$MODEL_CHOICE\"|" "$xlfile"
        ok "已应用模型选择：$MODEL_CHOICE"
    else
        warn "未找到 base_model 配置，跳过"
    fi
}

# ─────────────────────────── Phase 12：xl 启动命令 ───────────────────────────
setup_xl_cmd() {
    step "创建 xl 启动命令"

    local target_py="$VENV_DIR/bin/python"

    if ! command -v sudo >/dev/null 2>&1; then
        warn "无 sudo，无法写入 $XL_BIN"
        info "手动启动方式："
        echo "      cd $PROJECT_DIR && $target_py xl.py"
        return 0
    fi

    # 若已存在且内容一致，跳过
    if [ -f "$XL_BIN" ] && grep -q "$target_py" "$XL_BIN" && grep -q "$PROJECT_DIR" "$XL_BIN"; then
        ok "$XL_BIN 已就绪"
        return 0
    fi

    # 备份旧文件
    if [ -f "$XL_BIN" ]; then
        sudo cp "$XL_BIN" "$XL_BIN.bak.$(date +%s)" 2>/dev/null || true
        info "已备份原 $XL_BIN"
    fi

    info "写入 $XL_BIN"
    printf '#!/bin/bash\n# 小凌启动器（由 setup_kali.sh 生成）\ncd %q\nexec %q xl.py "$@"\n' \
        "$PROJECT_DIR" "$target_py" \
        | sudo tee "$XL_BIN" >/dev/null \
        || die "写入 $XL_BIN 失败"
    sudo chmod +x "$XL_BIN" || die "chmod +x $XL_BIN 失败"

    # v3.1 fix：去掉 || true 恒真；真正校验内容
    if [ -x "$XL_BIN" ] && grep -q "$target_py" "$XL_BIN"; then
        ok "$XL_BIN 就绪"
        info "  内容："
        sed 's/^/      /' "$XL_BIN"
    else
        warn "$XL_BIN 写入但校验未通过，请手动检查"
    fi
}

# ─────────────────────────── Phase 13：补丁 ───────────────────────────
patch_code() {
    step "打代码兼容补丁"
    cd "$PROJECT_DIR"

    # 补丁 1：-transparentcolor 平台判断
    python3 - <<'PYEOF'
import re, pathlib
patched = []
for name in ("xl.py", "pet.py"):
    f = pathlib.Path(name)
    if not f.exists(): continue
    src = f.read_text(encoding="utf-8", errors="replace")
    if '-transparentcolor' not in src: continue
    lines = src.splitlines(keepends=True)
    new, i, done = [], 0, False
    while i < len(lines):
        ctx = "".join(lines[max(0, i-2):i])
        if '-transparentcolor' in lines[i] and 'sys.platform' not in lines[i] and 'sys.platform' not in ctx:
            indent = re.match(r'^(\s*)', lines[i]).group(1)
            m = re.match(r'^(\s*)(.+?)\.attributes\(\s*"-transparentcolor"\s*,\s*(.+?)\)\s*$', lines[i])
            if m:
                obj, val = m.group(2), m.group(3)
                new.append(f'{indent}if sys.platform == "win32":\n')
                new.append(f'{indent}    {obj}.attributes("-transparentcolor", {val})\n')
                done = True; i += 1; continue
        new.append(lines[i]); i += 1
    if done:
        text = "".join(new)
        if not re.search(r'^\s*import sys\b', text, re.M):
            text = "import sys\n" + text
        bak = f.with_suffix(f.suffix + ".bak_transparent")
        if not bak.exists(): bak.write_text(src, encoding="utf-8")
        f.write_text(text, encoding="utf-8")
        patched.append(name)
if patched:
    print(f"  [✓] -transparentcolor 已加平台判断：{', '.join(patched)}")
else:
    print("  [i] 无需处理 -transparentcolor")
PYEOF

    # 补丁 2：自动更新开关（v3.1 修复：动态缩进 + 默认开启）
    python3 - <<'PYEOF'
import pathlib, sys, re
f = pathlib.Path("xl.py")
if not f.exists():
    print("  [i] 无 xl.py"); sys.exit(0)
src = f.read_text(encoding="utf-8", errors="replace")
if 'XL_ALLOW_UPDATE' in src:
    print("  [i] 自动更新开关已存在")
    sys.exit(0)
# 精确匹配 updater 启动行，动态取它的缩进
pat = re.compile(r'^(\s*)(threading\.Thread\(target=_worker, daemon=True, name="updater"\)\.start\(\))\s*$', re.M)
m = pat.search(src)
if not m:
    # 兜底：宽松匹配
    pat2 = re.compile(r'^(\s*)(threading\.Thread\(target=_worker.*?start\(\))\s*$', re.M)
    m = pat2.search(src)
if not m:
    print("  [!] 未找到 updater 启动行，跳过自动更新开关")
    sys.exit(0)
indent = m.group(1)
call = m.group(2)
# 默认开启：XL_ALLOW_UPDATE != "0" 时正常启动；= "0" 时禁用
replacement = (
    f'{indent}if os.environ.get("XL_ALLOW_UPDATE") != "0":\n'
    f'{indent}    {call}\n'
    f'{indent}else:\n'
    f'{indent}    print("  [更新] 已禁用（XL_ALLOW_UPDATE=0）")\n'
)
if not re.search(r'^\s*import os\b', src, re.M):
    # 顶部加 import os
    first_import = re.search(r'^(import \w+.*)$', src, re.M)
    if first_import:
        src = src[:first_import.start()] + "import os\n" + src[first_import.start():]
    else:
        src = "import os\n" + src
src = src.replace(m.group(0), replacement, 1)
bak = f.with_suffix(f.suffix + ".bak_updater")
if not bak.exists(): bak.write_text(src, encoding="utf-8")
# 注意：上面备份的是改后的；先备份原始再写
bak.write_text(open(f, encoding="utf-8").read(), encoding="utf-8")
f.write_text(src, encoding="utf-8")
print("  [✓] 自动更新开关已加（默认开启，XL_ALLOW_UPDATE=0 关闭）")
PYEOF

    # 补丁 3：stdin/stdout UTF-8 容错（v3.1：精确匹配 __main__）
    python3 - <<'PYEOF'
import pathlib, sys, re
f = pathlib.Path("xl.py")
if not f.exists(): sys.exit(0)
src = f.read_text(encoding="utf-8", errors="replace")
if "sys.stdin.reconfigure" in src:
    print("  [i] UTF-8 容错已存在"); sys.exit(0)
# 精确匹配主入口
m = re.search(r'^if __name__\s*==\s*["\']__main__["\']\s*:', src, re.M)
PATCH = (
    '# Kali/Linux: stdin/stdout UTF-8 容错（防止非法字节崩溃）\n'
    'try:\n'
    '    sys.stdin.reconfigure(encoding="utf-8", errors="replace")\n'
    '    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
    'except Exception:\n'
    '    pass\n\n'
)
if not m:
    print("  [!] 未找到 __main__ 块，跳过")
else:
    # 备份原始
    bak = f.with_suffix(f.suffix + ".bak_utf8")
    if not bak.exists(): bak.write_text(src, encoding="utf-8")
    if not re.search(r'^\s*import sys\b', src, re.M):
        src = "import sys\n" + src
        m = re.search(r'^if __name__\s*==\s*["\']__main__["\']\s*:', src, re.M)
    src = src[:m.start()] + PATCH + src[m.start():]
    f.write_text(src, encoding="utf-8")
    print("  [✓] UTF-8 容错已加")
PYEOF

    # 语法校验（用 venv 的 python）
    if python -c "import ast; ast.parse(open('xl.py', encoding='utf-8').read())" 2>/dev/null; then
        ok "xl.py 语法通过"
    else
        die "xl.py 语法错误（补丁打坏）。恢复：cp xl.py.bak_* xl.py 或从 $BACKUP_DIR 恢复"
    fi
}

# ─────────────────────────── Phase 14：验证 ───────────────────────────
verify() {
    step "验证安装"
    cd "$PROJECT_DIR"
    if ! python - <<'PYEOF'
import sys
try:
    import torch
except ImportError as e:
    print(f"  [✗] import torch 失败：{e}")
    sys.exit(1)
print(f"  [✓] torch        : {torch.__version__}")
if torch.cuda.is_available():
    print(f"  [✓] CUDA         : {torch.cuda.get_device_name(0)}")
    print(f"      计算能力     : sm_{''.join(map(str, torch.cuda.get_device_capability(0)))}")
    print(f"      显存         : {torch.cuda.get_device_properties(0).total_memory//1048576} MB")
else:
    print(f"  [!] CUDA 不可用，将走 CPU（若为 NVIDIA GPU 请检查驱动 ≥ 570）")
for mod in ("transformers", "peft", "accelerate", "safetensors"):
    try:
        m = __import__(mod)
        print(f"  [✓] {mod:<13}: {getattr(m,'__version__','?')}")
    except ImportError:
        print(f"  [✗] {mod:<13}: 缺失")
        sys.exit(1)
PYEOF
    then
        die "核心依赖（torch/transformers 等）验证失败，请检查上方日志"
    fi

    if [ -f "$MODEL_FILE" ]; then
        local sz; sz=$(stat -c%s "$MODEL_FILE")
        if [ "$sz" -gt "$MODEL_MIN_SIZE" ]; then ok "模型权重：$(human_size "$sz")"
        else warn "模型权重不完整（$(human_size "$sz")）"; fi
    else
        warn "未找到 $MODEL_FILE"
    fi
}

# ─────────────────────────── Phase 15：权限 + 汇总 ───────────────────────────
fix_ownership() {
    step "权限修复"
    cd "$PROJECT_DIR"
    local bad
    bad=$(find . ! -user "$(id -un)" 2>/dev/null | head -5)
    if [ -n "$bad" ]; then
        warn "发现非当前用户所属："
        echo "$bad" | sed 's/^/      /'
        if command -v sudo >/dev/null 2>&1; then
            sudo chown -R "$(id -un):$(id -gn)" "$PROJECT_DIR" && ok "已修复"
        fi
    else
        ok "属主正常"
    fi
}

summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    if [ "$WARN_COUNT" -eq 0 ]; then
        echo "║                          配置完成                             ║"
    else
        echo "║                   配置完成（$WARN_COUNT 条警告）                     ║"
    fi
    echo "╚════════════════════════════════════════════════════════════════╝"
    cat <<EOF

  ─── 环境 ───
    平台           : $PLATFORM_KIND ($OS_NAME)
    Python         : $PY_VER
    GPU            : ${GPU_NAME:-无（CPU 模式）}
    PyTorch 方案   : $TORCH_VARIANT

  ─── 路径 ───
    工作目录       : $SCRIPT_DIR
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

  ─── 下次更新代码 ───
    1. 不要覆盖 .venv/ 和 .star_core/
    2. 备份 xl_memory.json 与 data/
    3. 重跑本脚本（会自动检测并跳过已完成步骤）

  ─── 模型未就位时 ───
    加入 QQ 社区群：1057895186（小凌社区1群）
    群文件下载完整 model.safetensors 后放到 $SCRIPT_DIR
EOF
}

# ─────────────────────────── 主流程 ───────────────────────────
main() {
    # v3.1 fix：root 检测最优先（Phase 0）
    check_root

    log_init
    echo "  小凌一键部署 + 配置 v3.2"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # v3.2 fix：第一步就是选择模型大小（自研档位）
    select_model_size

    detect_env
    select_profile
    deploy_project
    place_model
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

    log_close
    echo ""
    echo "  日志：$LOG_FILE"
    echo ""
    exit 0
}

main "$@"
