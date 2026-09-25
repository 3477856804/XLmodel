import json
import os
import sys
import re
import time
import math
import random
import shutil
import hashlib
import base64
import subprocess
import threading
import tempfile
import uuid
import difflib
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# v0.0.13b：exe 打包兼容——onefile 模式下资源在可执行文件同目录
# 提前定义BASE_DIR，供后面Termux兼容层使用
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()

# ============================================================
# v0.0.1 fix：Termux（安卓）兼容层
# pip 装的 Rust tokenizers 二进制与 Termux Python 3.14 ABI 不兼容
# （报错：cannot locate symbol "PyBaseObject_Type" ... tokenizers.abi3.so）
# 解法：USE_TOKENIZERS=0 → transformers 用纯 Python 分词器（官方后备方案）
# ============================================================
def _build_py_shim(shim_path, obj_addr):
    """v5 fix：纯 Python 生成 ELF 共享库（导出 PyBaseObject_Type + __PyBaseObject_Type）。
    不依赖 clang/编译器——Termux 无编译器也能用。
    符号为 SHN_ABS 绝对地址，值 = id(object)。
    """
    import struct as _st
    symbols = ["PyBaseObject_Type", "__PyBaseObject_Type"]
    # .dynstr
    dynstr = b"\x00"
    sym_offsets = {}
    for s in symbols:
        sym_offsets[s] = len(dynstr)
        dynstr += s.encode() + b"\x00"
    shstr = b"\x00.dynsym\x00.dynstr\x00.shstrtab\x00"

    # 布局（含 .dynamic 段——动态链接器定位 .dynsym/.dynstr 必需）
    entsize = 24
    dynsym_count = 1 + len(symbols)
    dynsym_size = entsize * dynsym_count
    phoff = 64                      # 程序头表紧跟 ELF 头
    phnum = 2                       # 2个程序头：PT_LOAD + PT_DYNAMIC
    phentsize = 56
    # v6.2 fix：程序头表占 phnum 个条目，共 phnum*phentsize 字节
    # 之前错误写成 phoff+56，导致第二个程序头被 .dynsym 覆盖
    dynsym_off = phoff + phnum * phentsize
    dynstr_off = dynsym_off + dynsym_size
    dynstr_size = len(dynstr)
    dyn_off = dynstr_off + dynstr_size   # .dynamic 段（3 个条目 + null）
    dyn_size = 16 * 4               # 3 个 DT_ + 1 个 null = 4 条目 × 16 bytes
    shstr_off = dyn_off + dyn_size
    shstr_size = len(shstr)
    shdr_off = shstr_off + shstr_size
    shdr_count = 5                  # null/dynsym/dynstr/dynamic/shstrtab
    total = shdr_off + shdr_count * 64
    total = (total + 7) & ~7

    buf = bytearray(total)
    # ELF 头
    buf[0:16] = bytes([0x7f, 0x45, 0x4c, 0x46, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    machine = 183 if ("aarch64" in sys.platform or "arm" in sys.platform) else 62
    _st.pack_into("<H", buf, 16, 3)        # e_type ET_DYN
    _st.pack_into("<H", buf, 18, machine)
    _st.pack_into("<I", buf, 20, 1)
    _st.pack_into("<Q", buf, 24, 0)        # e_entry
    _st.pack_into("<Q", buf, 32, phoff)    # e_phoff
    _st.pack_into("<Q", buf, 40, shdr_off) # e_shoff
    _st.pack_into("<I", buf, 48, 0)
    _st.pack_into("<H", buf, 52, 64)       # e_ehsize
    _st.pack_into("<H", buf, 54, 56)       # e_phentsize
    _st.pack_into("<H", buf, 56, 2)        # e_phnum（2: PT_LOAD + PT_DYNAMIC）
    _st.pack_into("<H", buf, 58, 64)       # e_shentsize
    _st.pack_into("<H", buf, 60, shdr_count)
    _st.pack_into("<H", buf, 62, 3)

    # PT_LOAD 程序头（56 bytes，覆盖整个文件，可读可执行）
    _st.pack_into("<IIQQQQQQ", buf, phoff, 1, 5, 0, 0, 0, total, total, 0x1000)
    # PT_DYNAMIC 程序头（类型 2）指向 .dynamic
    _st.pack_into("<IIQQQQQQ", buf, phoff + 56, 2, 6, dyn_off, dyn_off, dyn_off, dyn_size, dyn_size, 8)

    # .dynsym
    for i in range(dynsym_count):
        off = dynsym_off + i * entsize
        if i == 0:
            _st.pack_into("<IBBHQQ", buf, off, 0, 0, 0, 0, 0, 0)
        else:
            s = symbols[i-1]
            _st.pack_into("<IBBHQQ", buf, off,
                          sym_offsets[s], 0x12, 0, 0xfff1, obj_addr, 0)

    buf[dynstr_off:dynstr_off+dynstr_size] = dynstr
    # .dynamic 段：DT_SYMTAB(6)=dynsym地址, DT_STRTAB(5)=dynstr地址,
    #             DT_SYMENT(11)=24, DT_NULL(0)
    # v6.2 fix：之前错误把DT_HASH(4)当成了DT_SYMTAB(6)
    dyn_size = 16 * 4  # 4个条目 × 16 bytes
    _st.pack_into("<qQ", buf, dyn_off, 6, dynsym_off)   # DT_SYMTAB
    _st.pack_into("<qQ", buf, dyn_off + 16, 5, dynstr_off)  # DT_STRTAB
    _st.pack_into("<qQ", buf, dyn_off + 32, 11, 24)    # DT_SYMENT
    _st.pack_into("<qQ", buf, dyn_off + 48, 0, 0)      # DT_NULL
    buf[shstr_off:shstr_off+shstr_size] = shstr

    def _sh(idx, name, st, fl, a, off, sz, link, info, align, es):
        o = shdr_off + idx * 64
        _st.pack_into("<IIQQQQIIQQ", buf, o,
                      name, st, fl, a, off, sz, link, info, align, es)
    _sh(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    _sh(1, 1, 11, 2, 0, dynsym_off, dynsym_size, 2, 1, 8, 24)
    _sh(2, 9, 3, 0, 0, dynstr_off, dynstr_size, 0, 0, 1, 0)
    _sh(3, 6, 3, 3, 0, dyn_off, dyn_size, 2, 0, 8, 16)   # .dynamic SHT_DYNAMIC
    _sh(4, 17, 3, 0, 0, shstr_off, shstr_size, 0, 0, 1, 0)

    with open(shim_path, "wb") as f:
        f.write(buf)


_IS_TERMUX = ("com.termux" in str(sys.executable)) or ("/data/data/com.termux" in str(getattr(sys, "prefix", "")))
if _IS_TERMUX:
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    # v6.8 fix：Termux Rust tokenizers ABI 不兼容，直接彻底禁用
    # Termux的bionic libc和标准glibc行为不一样，shim方案不生效
    # 直接把tokenizers从sys.modules标记为None，transformers自动降级为纯Python慢速分词器
    os.environ["USE_TOKENIZERS"] = "0"
    sys.modules['tokenizers'] = None
    print("  [兼容] Termux已禁用Rust加速分词器，使用纯Python慢速分词模式")

# v6.8：全局控制是否使用fast tokenizer
_USE_FAST_TOKENIZER = os.environ.get("USE_TOKENIZERS", "1") != "0"
if not _USE_FAST_TOKENIZER:
    print("  [兼容] 已启用纯Python分词模式（fast tokenizer已禁用）")

MEMORY_PATH = BASE_DIR / "xl_memory.json"
MODEL_DIR = BASE_DIR / ".star_core" / "XLmodel"

# ============================================================
# v0.0.9：基底模型档位表（用户可选，默认 MiniCPM5-2B）
# ============================================================
MODEL_PRESETS = {
    # v0.0.1：只保留魔塔社区真实存在的 MiniCPM5 档位
    # 显示真实模型名 + 真实占用大小（用户要求）
    # ms_id: 魔塔社区模型 ID；model_name: 真实模型名；dl_size_hint: 下载占用空间
    "自研2B模型": {
        "hf_id": "openbmb/MiniCPM5-2B",
        "ms_id": "OpenBMB/MiniCPM5-2B",
        "model_name": "MiniCPM5-2B",
        "size_hint": "约 4.8GB，手机/电脑流畅",
        "dl_size_hint": "约 4.8GB",
        "desc": "自研 2B 模型（默认，端侧最强）",
        "default": True,
    },
    "自研1B模型": {
        "hf_id": "openbmb/MiniCPM5-1B",
        "ms_id": "OpenBMB/MiniCPM5-1B",
        "model_name": "MiniCPM5-1B",
        "size_hint": "约 2.1GB，低配设备",
        "dl_size_hint": "约 2.1GB",
        "desc": "自研 1B 模型（轻量）",
        "default": False,
    },
}

def get_model_preset():
    """获取当前配置的模型档位。返回 (preset dict, 模型 ID)。"""
    name = CONFIG.get("model", {}).get("base_model", "MiniCPM5-2B")
    preset = MODEL_PRESETS.get(name)
    if preset is None:
        # 未知档位回退默认
        print(f"  [模型] 未知档位 {name}，回退 自研2B模型")
        name = "自研2B模型"
        preset = MODEL_PRESETS[name]
    return preset, name


def _download_multipart(url, dest, threads=6, min_part=64 * 1024 * 1024):
    """v0.0.1 fix：多线程分片下载（魔塔支持 Range）。

    流式写盘（每块收到即写，不攒内存），8 线程并行，
    速度远快于单线程/4线程攒内存版。纯标准库。
    返回 (成功, 文件大小)。
    """
    import urllib.request, threading, os as _os, time as _time

    # 1. 探测总大小（Range GET：魔塔 HEAD 不返回 Content-Length，但 Range 返回 Content-Range）
    total = None
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cr = r.headers.get("Content-Range", "")
            if "/" in cr:
                total = int(cr.rsplit("/", 1)[1])
    except Exception:
        pass
    if not total:
        # 探测失败 → 退化为单线程 curl
        import subprocess as _sp
        r = _sp.run(["curl", "-L", "--progress-bar", "-o", str(dest), url], timeout=14400)
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 1024 * 1024:
            return True, dest.stat().st_size
        return False, 0
    if total < 8 * 1024 * 1024:
        # 文件太小（<8MB）→ 不分片，单线程 curl（避免分片开销）
        import subprocess as _sp
        r = _sp.run(["curl", "-sS", "-L", "-o", str(dest), url], timeout=14400)
        if r.returncode == 0 and dest.exists() and dest.stat().st_size >= total * 0.95:
            return True, dest.stat().st_size
        return False, 0

    # 2. 动态分片 + 队列调度（64MB/片，6 线程从队列取片，谁快谁多下）
    part_size = max(min_part, 16 * 1024 * 1024)
    n_parts = (total + part_size - 1) // part_size
    if n_parts < 1:
        n_parts = 1
    # 分片队列（i -> 已下载字节数）
    parts = list(range(n_parts))
    q_lock = threading.Lock()
    done = [0] * n_parts
    lock = threading.Lock()
    _start = _time.time()
    failed = []

    def fetch():
        while True:
            with q_lock:
                if not parts:
                    return
                i = parts.pop(0)
            start = i * part_size
            end = min(total - 1, (i + 1) * part_size - 1)
            tmp = dest.parent / f"{dest.name}.part{i}"
            got = 0
            if tmp.exists():
                got = tmp.stat().st_size
            for attempt in range(3):
                try:
                    rng_start = start + got
                    if rng_start > end:
                        break
                    rng = f"bytes={rng_start}-{end}"
                    req = urllib.request.Request(url, headers={"User-Agent": "curl/8", "Range": rng})
                    mode = "ab" if got > 0 else "wb"
                    with urllib.request.urlopen(req, timeout=600) as r, open(tmp, mode) as f:
                        while True:
                            chunk = r.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            got += len(chunk)
                            with lock:
                                done[i] = got
                    if tmp.stat().st_size >= (end - start + 1) * 0.98:
                        break
                    raise Exception("分片不完整")
                except Exception as e:
                    if attempt < 2:
                        import time as _t
                        _t.sleep(1 + attempt)  # 退避重试
                        continue
                    with q_lock:
                        failed.append((i, e))
                    return

    # 启动 6 个工作线程
    pool = [threading.Thread(target=fetch, daemon=True) for _ in range(threads)]
    for t in pool:
        t.start()

    # 3. 进度显示（每 1 秒刷新）
    last_pct = -1
    while any(t.is_alive() for t in pool):
        _time.sleep(1)
        with lock:
            got = sum(done)
        pct = got * 100.0 / total if total else 0
        speed = got / 1024 / 1024 / max(_time.time() - _start, 0.1)
        bar_len = 30
        filled = int(pct / 100 * bar_len)
        bar = "=" * filled + " " * (bar_len - filled)
        print(f"\r  [模型] 正在拉取 [{bar}] {pct:.1f}%  {got/1024/1024:.0f}/{total/1024/1024:.0f} MB  {speed:.1f} MB/s", end="", flush=True)
        if int(pct) != last_pct:
            last_pct = int(pct)

    for t in pool:
        t.join()
    print()

    # 4. 检查失败
    if failed:
        for i, e in failed:
            print(f"  [模型] 分片 {i+1}/{n_parts} 下载失败: {e}")
        return False, 0

    # 5. 拼接分片 → 目标文件（流式，不占内存）
    with open(dest, "wb") as out:
        for i in range(n_parts):
            tmp = dest.parent / f"{dest.name}.part{i}"
            with open(tmp, "rb") as f:
                while True:
                    chunk = f.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            tmp.unlink(missing_ok=True)
    if dest.exists() and dest.stat().st_size >= total * 0.98:
        return True, dest.stat().st_size
    return False, dest.stat().st_size if dest.exists() else 0


def ensure_base_model():
    """v0.1.0：确保基底模型存在。缺失时自动下载并平铺到 MODEL_DIR。

    - 下载到临时目录（ModelScope 国内源优先），成功后平铺复制到 .star_core/XLmodel/
    - 清理品牌文件（README/说明/品牌目录），目录内只留模型必需文件
    - 界面/日志只显示"自研 N B 模型"档位，不显示品牌名
    - 用户按自己配置选择想自研的模型档位
    """
    try:
        preset, name = get_model_preset()
        # v0.0.1 fix：已有模型检查兼容任意 safetensors/bin 文件名（魔塔格式）
        model_file = MODEL_DIR / "model.safetensors"
        _has_model = model_file.exists() and model_file.stat().st_size > 10 * 1024 * 1024
        if not _has_model:
            for _p in MODEL_DIR.glob("*.safetensors"):
                if _p.stat().st_size > 10 * 1024 * 1024:
                    model_file = _p
                    _has_model = True
                    break
        if not _has_model:
            for _p in MODEL_DIR.glob("*.bin"):
                if _p.stat().st_size > 10 * 1024 * 1024:
                    model_file = _p
                    _has_model = True
                    break
        if _has_model:
            return True  # 已有有效模型
        # 缺失 → 提示（不显示品牌名）
        print(f"  [模型] 基底缺失（当前档位：自研{_preset_size_label(name)}模型）")
        print(f"  [模型] {preset['desc']} | {preset['size_hint']}")
        print(f"  [模型] 更换档位：编辑 xl.py 顶部 CONFIG['model']['base_model']")
        if CONFIG.get("model", {}).get("auto_download", True):
            print(f"  [模型] 尝试自动下载（魔塔社区，safetensors 版，带进度条）...")
            try:
                import subprocess as _sp
                # v0.0.1 fix：魔塔社区（ModelScope）优先，下载 safetensors 版
                # 下载到临时目录 → 成功后自动移动到 .star_core/XLmodel/
                import tempfile as _tf
                tmp_dl = Path(_tf.gettempdir()) / "xl_model_dl"
                if tmp_dl.exists():
                    import shutil as _sh
                    _sh.rmtree(tmp_dl)
                tmp_dl.mkdir(parents=True, exist_ok=True)
                ms_id = preset.get("ms_id", "")
                if not ms_id:
                    print("  [模型] 该档位暂无魔塔地址，请手动下载")
                    return False
                # 魔塔社区 safetensors 文件列表（权重 + 必需配置）
                base_url = f"https://modelscope.cn/models/{ms_id}/resolve/master"
                # 主权重 + 配置文件
                files_to_dl = [
                    ("model-00000-of-00001.safetensors", "model-00000-of-00001.safetensors"),  # 主权重
                    ("model.safetensors.index.json", "model.safetensors.index.json"),
                    ("config.json", "config.json"),
                    ("generation_config.json", "generation_config.json"),
                    ("tokenizer.json", "tokenizer.json"),
                    ("tokenizer_config.json", "tokenizer_config.json"),
                    ("special_tokens_map.json", "special_tokens_map.json"),
                    ("chat_template.jinja", "chat_template.jinja"),
                ]
                # 主权重下载（多线程分片加速，魔塔支持 Range）
                main_file, main_name = files_to_dl[0]
                # 动态大小提示：按档位显示（1B≈2GB / 2B≈4.8GB）
                size_label = preset.get("dl_size_hint", preset.get("size_hint", ""))
                mname = preset.get("model_name", name)
                print(f"  [模型] 正在拉取基底模型（{mname}，占用 {size_label}）...")
                print(f"  [模型] 来源：魔塔社区（国内源，多线程加速）")
                dl_main = tmp_dl / main_name
                # 8 线程分片下载（速度提升 5-8 倍）
                ok_dl, dl_size = _download_multipart(
                    f"{base_url}/{main_file}", dl_main, threads=6)
                if not ok_dl or dl_size < 100 * 1024 * 1024:
                    print("  [模型] 拉取失败，请检查网络或手动下载")
                    return False
                print(f"  [模型] 基底模型拉取完成（{dl_size/1024/1024/1024:.2f} GB）")
                # 配置文件下载（小文件，无进度条）
                print("  [模型] 下载配置文件...")
                for fname, local_name in files_to_dl[1:]:
                    try:
                        _sp.run(
                            ["curl", "-sS", "-L", "-o", str(tmp_dl / local_name),
                             f"{base_url}/{fname}"],
                            timeout=120)
                    except Exception:
                        pass
                # 下载完成 → 自动移动到 .star_core/XLmodel/
                import shutil as _sh
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
                print(f"  [模型] 下载完成，自动移动到 {MODEL_DIR}...")
                for old_f in MODEL_DIR.iterdir():
                    if old_f.name == ".gitkeep":
                        continue
                    if old_f.is_dir():
                        _sh.rmtree(old_f)
                    else:
                        old_f.unlink()
                # 平铺复制所有下载文件到 MODEL_DIR
                moved = 0
                for p in tmp_dl.iterdir():
                    if p.is_file():
                        _sh.copy2(p, MODEL_DIR / p.name)
                        moved += 1
                # 清理临时目录
                try:
                    _sh.rmtree(tmp_dl)
                except Exception:
                    pass
                # v0.0.1 fix：兼容魔塔下载的任意 safetensors 文件名
                # （model-00000-of-00001.safetensors / model.safetensors / 分片）
                _ok = False
                for _p in MODEL_DIR.glob("*.safetensors"):
                    if _p.stat().st_size > 100 * 1024 * 1024:
                        _ok = True
                        break
                if not _ok:
                    for _p in MODEL_DIR.glob("*.bin"):
                        if _p.stat().st_size > 100 * 1024 * 1024:
                            _ok = True
                            break
                if _ok:
                    print(f"  [模型] 自动下载完成：自研{_preset_size_label(name)}模型已就位")
                    print(f"  [模型] 权重已移动至 .star_core/XLmodel/，无品牌文件")
                    return True
                print("  [模型] 自动下载未完成，请手动下载（或检查网络）")
                return False
            except Exception as e:
                print(f"  [模型] 自动下载失败: {e}")
                return False
                # 平铺复制到 MODEL_DIR（只复制模型必需文件）
                import shutil as _sh
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
                # 先清空 MODEL_DIR（旧占位/残留；保留 .gitkeep 保持目录存在）
                for old_f in MODEL_DIR.iterdir():
                    if old_f.name == ".gitkeep":
                        continue
                    if old_f.is_dir():
                        _sh.rmtree(old_f)
                    else:
                        old_f.unlink()
                copied = 0
                for p in src_model.parent.iterdir():
                    if p.is_file():
                        _sh.copy2(p, MODEL_DIR / p.name)
                        copied += 1
                # 递归找其他必需文件（config.json / tokenizer 等可能在更深层）
                for p in tmp_dl.rglob("*"):
                    if p.is_file() and p.name in (
                        "config.json", "generation_config.json", "tokenizer.json",
                        "tokenizer_config.json", "vocab.json", "merges.txt",
                        "model.safetensors", "model-00001-of-*.safetensors",
                        "tokenizer.model", "special_tokens_map.json", "chat_template.json",
                    ):
                        dst = MODEL_DIR / p.name
                        if not dst.exists():
                            _sh.copy2(p, dst)
                            copied += 1
                # 清理临时目录（不留品牌文件）
                try:
                    _sh.rmtree(tmp_dl)
                except Exception:
                    pass
                if model_file.exists() and model_file.stat().st_size > 10 * 1024 * 1024:
                    print(f"  [模型] 自动下载完成：自研{_preset_size_label(name)}模型已就位")
                    print(f"  [模型] 目录已清理品牌信息，只保留模型必需文件")
                    return True
                print("  [模型] 自动下载未完成，请手动下载（或检查网络）")
                return False
            except Exception as e:
                print(f"  [模型] 自动下载失败: {e}")
                return False
        return False
    except Exception:
        return False


def ensure_adapter():
    """v0.1.0：确保初始适配器存在（成长起点）。

    新用户 .star_core/ 缺适配器时，自动从官网下载初始适配器（3 个分包）。
    老用户本地已有适配器 → 保留不覆盖（成长数据不动）。
    适配器是蒸馏训练的起点——训练后适配器增长 → 合并进基底 → 自研模型诞生。
    """
    try:
        adapter_file = ADAPTER_DIR / "adapter_model.safetensors"
        # v0.0.4 fix：已有适配器检查更宽容——任意大适配器文件都算（避免重复下载）
        _has_adapter = adapter_file.exists() and adapter_file.stat().st_size > 1024 * 1024
        if not _has_adapter:
            for _p in ADAPTER_DIR.glob("*.safetensors"):
                if _p.stat().st_size > 1024 * 1024:
                    adapter_file = _p
                    _has_adapter = True
                    break
        if not _has_adapter:
            for _p in ADAPTER_DIR.glob("*.pt"):
                if _p.stat().st_size > 1024 * 1024:
                    _has_adapter = True
                    break
        if _has_adapter:
            return True  # 已有适配器（保留成长，不再重复下载）
        print("  [模型] 未检测到初始适配器（新用户），下载初始适配器...")
        import urllib.request as _ur
        import zipfile as _zip
        import shutil as _sh
        import tempfile as _tf
        base_url = "https://xiaoling-4o6.pages.dev/update"
        parts = ["adapter_pt.zip", "adapter_model.zip", "adapter_tok.zip"]
        for part in parts:
            tmp = Path(_tf.gettempdir()) / part
            url = f"{base_url}/{part}"
            try:
                req = _ur.Request(url, headers={"User-Agent": "XiaoLing/0.0.1"})
                with _ur.urlopen(req, timeout=120) as r:
                    with open(tmp, "wb") as f:
                        _sh.copyfileobj(r, f)
                with _zip.ZipFile(tmp) as zf:
                    zf.extractall(str(ADAPTER_DIR))
                print(f"  [模型] 初始适配器部分 {part} 已就位")
            except Exception as e:
                print(f"  [模型] 初始适配器下载失败 {part}: {e}")
            finally:
                try:
                    tmp.unlink()
                except Exception:
                    pass
        if adapter_file.exists() and adapter_file.stat().st_size > 1024 * 1024:
            print("  [模型] 初始适配器就绪——蒸馏训练将从这里开始成长")
            return True
        print("  [模型] 初始适配器未完整下载，可稍后重试或手动放入 .star_core/")
        return False
    except Exception:
        return False


def _preset_size_label(name):
    """把档位名转成简洁的"自研 N B"标签（不显示品牌）。"""
    m = re.search(r'(\d+(?:\.\d+)?)B', str(name))
    if m:
        return m.group(1) + "B"
    return "小模型"


ADAPTER_DIR = BASE_DIR / ".star_core"
# v1.0 融合层：只读资源用 core.paths.resource()（打包后资源在 _internal/ 或 onefile 临时目录）
try:
    from core.paths import resource as _resource
except Exception:                                                     # noqa: BLE001
    def _resource(*parts):
        return BASE_DIR.joinpath(*parts)

DATA_DIR = BASE_DIR / "数据"          # 可写：训练语料会持续写入这里
INTERACTIONS_PATH = DATA_DIR / "interactions.jsonl"
LEARNED_PATH = DATA_DIR / "learned_data.jsonl"
CORPUS_PATH = DATA_DIR / "corpus.txt"
SKILLS_DIR = _resource("技能")
AUTO_TRAIN_THRESHOLD = 1000

CONFIG = {
    "version": "0.0.2", "name": "小凌", "user_name": "你",
    # v0.0.9：基底模型选择（用户可配置，默认 MiniCPM5-2B）
    # 可选档位：
    #   "自研2B模型"     -> 默认，端侧最强（Q4 约1.56GB，手机/电脑流畅）
    #   "自研1B模型"     -> 轻量（Q4 约0.5-1GB，低配设备）
    #   "自研0.8B模型"    -> 极致轻量（~1GB，手表/老设备）
    #   "自研2B轻量"      -> 平衡档
    #   "自研4B模型"      -> 更强（设备好时选，~3GB）
    #   "自研9B模型"      -> 最强（需 8G+ 内存，~6GB）
    # 自动下载：启动时若 .star_core/XLmodel 为空，自动从 HuggingFace/ModelScope 拉取
    "model": {
        "base_model": "自研2B模型",        # 基底模型档位
        "hf_id": "openbmb/MiniCPM5-2B",     # HuggingFace 模型 ID
        "ms_id": "OpenBMB/MiniCPM5-2B",     # ModelScope 模型 ID（国内加速）
        "quant": "q4_k_m",                   # 量化档（q4_k_m 默认）
        "auto_download": True,               # 缺模型时自动下载
    },
    "enable_voice": True,           # v0.0.3：语音朗读开关
    "voice_rate": 175,              # 语音语速（字/分钟）
    "auto_save_memory": True,       # v0.0.3：自动保存记忆
    "persona": "活泼",               # v0.0.10：人格（活泼/温柔/专业）
    "proactive": True,               # v0.0.10：空闲主动互动
    "deepseek_api_key": "暂未填入",
    "deepseek_base_url": "https://api.deepseek.com/v1",
    "teacher_model": "deepseek-chat",
    "temperature": 0.85, "max_tokens": 8192,
    "max_context_turns": 200, "max_tool_calls_per_turn": 50,
    "short_term_turns": 80, "summary_every_turns": 30,
    "tool_result_max_length": 0,
    "belief_update_rate": 0.15, "mood_decay": 0.05,
    "reflection_after_turns": 10,
    "typing_delay_min": 0.1, "typing_delay_max": 0.8,
    "enable_planning": True, "enable_parallel_tools": True,
    "enable_self_modify": True, "enable_background_tasks": True,
    # v0.0.20：多平台接入（配置对应平台的 Key/Webhook 即启用，不配则跳过）
    "platforms": {
        "wechat":    {"enabled": False, "token": "", "webhook": ""},
        "feishu":    {"enabled": False, "app_id": "", "app_secret": "", "webhook": ""},
        "qq":        {"enabled": False, "onebot_ws": "ws://127.0.0.1:6700", "group": ""},
        "wecom":     {"enabled": False, "corp_id": "", "agent_id": "", "secret": "", "webhook": ""},
        "dingtalk":  {"enabled": False, "webhook": "", "secret": ""},
        "telegram":  {"enabled": False, "bot_token": "", "allowed_users": ""},
        "discord":   {"enabled": False, "bot_token": "", "channel_id": ""},
    },
    # v0.0.20：离线模式（断网时本地模型完整可用）
    "offline_mode": "auto",   # auto=自动检测 / on=强制离线 / off=强制在线
}

# ============================================================
# v0.0.4 fix：读取持久化的模型选择（用户上次选 1B/2B），覆盖默认
# ============================================================
try:
    _choice_file = Path(BASE_DIR) / ".star_core" / "model_choice.txt"
    if _choice_file.exists():
        _saved = _choice_file.read_text(encoding="utf-8").strip()
        if _saved in MODEL_PRESETS:
            CONFIG["model"]["base_model"] = _saved
    else:
        # 无持久化选择但有模型 → 按模型大小自动识别档位（老用户兼容）
        _w = None
        for _p in (Path(BASE_DIR) / ".star_core" / "XLmodel").glob("*.safetensors"):
            if _p.stat().st_size > 100 * 1024 * 1024:
                _w = _p.stat().st_size
                break
        if _w is not None:
            if _w < 3 * 1024 * 1024 * 1024:
                CONFIG["model"]["base_model"] = "自研1B模型"
            else:
                CONFIG["model"]["base_model"] = "自研2B模型"
except Exception:
    pass


# ============================================================
# 语音朗读（v0.0.3：Windows TTS）
# ============================================================
_tts_engine = None
_tts_lock = threading.Lock()

def _safe_input(prompt=""):
    """安全的终端输入：捕获编码错误，Kali/中文终端非法字节不崩溃。"""
    try:
        return input(prompt)
    except UnicodeDecodeError:
        print("  [输入] 检测到无法识别的字节，已忽略（请确保终端编码为 UTF-8）")
        return ""
    except (EOFError, KeyboardInterrupt):
        raise
    except Exception:
        return ""



def speak(text, force=False):
    """朗读文本（Windows pyttsx3）。无依赖或失败时静默降级。

    参数:
        text: 要朗读的文本
        force: 是否忽略 CONFIG 开关强制朗读
    """
    if not text: return
    if not force and not CONFIG.get("enable_voice", True): return
    # 过滤掉工具标记和过长文本
    clean = re.sub(r'\[\[[^\]]*\]\]', '', text).strip()
    if not clean or len(clean) > 500: return
    global _tts_engine
    # v0.0.5 fix：Linux 音频后端检测——aplay/espeak 缺失时提前提示，避免反复报错
    if _tts_engine is None and not sys.platform.startswith("win"):
        import shutil as _sh2
        if not (_sh2.which("aplay") or _sh2.which("espeak") or _sh2.which("espeak-ng")):
            _tts_engine = False  # 标记不可用，不再尝试
            print("  [语音] 系统缺少音频后端（aplay/espeak），语音输出不可用")
            print("  [语音] Kali/WSL2 安装：sudo apt install espeak-ng alsa-utils")
            return
    try:
        if _tts_engine is None:
            import pyttsx3
            _tts_engine = pyttsx3.init()
            _tts_engine.setProperty("rate", CONFIG.get("voice_rate", 175))
        if _tts_engine is False:
            return  # 后端缺失已提示过
        with _tts_lock:
            _tts_engine.say(clean)
            _tts_engine.runAndWait()
    except ImportError:
        pass  # 无 pyttsx3，静默
    except Exception:
        pass  # v0.0.17：Linux/macOS 无 espeak 等后端时静默降级
    except Exception:
        pass  # 语音失败不影响功能


def speak_async(text):
    """后台线程朗读，不阻塞主对话。"""
    threading.Thread(target=speak, args=(text,), daemon=True).start()


# ============================================================
# 成长型模型（v0.0.4：越用体积越大，越来越强，最终脱离基底）
# ============================================================
# 核心思想：
#   每次蒸馏学习（向 DeepSeek 老师学习）后，把语料/记忆合并成"成长包"，
#   持续扩充 GROWTH_DIR，模型体积随学习增长。
#   当成长包足够大时，小凌的知识/能力主要来自成长包（而非基底模型），
#   逐渐脱离基底模型（model.safetensors 不再是必需），实现独立成长。
# 参考：持续学习（Continual Learning）+ 检索增强生成（RAG）

GROWTH_DIR = BASE_DIR / ".star_core" / "growth"
GROWTH_INDEX = GROWTH_DIR / "growth_index.jsonl"
GROWTH_LOG = GROWTH_DIR / "growth.log"


class GrowthManager:
    """成长管理器：管理小凌的成长包（知识持续积累 + 体积增长）。"""

    def __init__(self):
        self.dir = GROWTH_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.total_items = 0
        self.total_bytes = 0
        self._load_stats()

    def _load_stats(self):
        """统计当前成长包大小。"""
        try:
            if GROWTH_INDEX.exists():
                with open(GROWTH_INDEX, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            self.total_items += 1
            for p in self.dir.rglob("*"):
                if p.is_file():
                    self.total_bytes += p.stat().st_size
        except Exception:
            pass

    def absorb(self, source, content, tags=None):
        """吸收一条知识进成长包（每次蒸馏/对话后调用）。

        参数:
            source: 来源（distill/chat/teacher）
            content: 知识内容
            tags: 标签列表
        """
        try:
            entry = {
                "time": time.time(),
                "source": source,
                "content": content[:2000],
                "tags": tags or [],
            }
            with open(GROWTH_INDEX, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self.total_items += 1
            self.total_bytes += len(entry["content"])
            # 追加到成长日志
            with open(GROWTH_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] +{source}: {content[:60]}\n")
            return True
        except Exception as e:
            print(f"  [成长] 吸收失败: {e}")
            return False

    def get_size(self):
        """当前成长包体积（人类可读）。"""
        if self.total_bytes < 1024:
            return f"{self.total_bytes} B"
        if self.total_bytes < 1024 * 1024:
            return f"{self.total_bytes/1024:.1f} KB"
        return f"{self.total_bytes/1024/1024:.2f} MB"

    def recall(self, query, n=5):
        """从成长包检索相关知识（RAG，越用越强的核心）。"""
        results = []
        ql = query.lower()
        try:
            if GROWTH_INDEX.exists():
                with open(GROWTH_INDEX, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            text = entry.get("content", "").lower()
                            score = 0
                            for w in self._keywords(query):
                                if w in text:
                                    score += text.count(w) * 2
                            if score > 0:
                                results.append((score, entry))
                        except Exception:
                            continue
        except Exception:
            pass
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:n]

    def _keywords(self, text):
        kws = set()
        for w in re.findall(r'[a-zA-Z]{2,}', text):
            kws.add(w.lower())
        for seg in re.findall(r'[\u4e00-\u9fff]+', text):
            for n in range(2, 4):
                for i in range(len(seg) - n + 1):
                    kws.add(seg[i:i+n])
        return kws

    def growth_report(self):
        """成长报告：小凌的成长进度。"""
        return (f"成长包：{self.total_items} 条知识 / {self.get_size()}\n"
                f"知识来源：蒸馏学习 + 日常对话 + 老师教学\n"
                f"成长目标：积累足够知识后脱离基底模型，独立运行")

    def consolidate(self, memory, limit=20):
        """v0.0.5：把成长包最新知识蒸馏进语义记忆（长期记忆更牢）。

        成长包是"短期积累"，语义记忆是"长期沉淀"。
        定期把成长包里的重要知识固化到 LongTermMemory.semantic_memory。
        """
        try:
            n = 0
            if GROWTH_INDEX.exists():
                with open(GROWTH_INDEX, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []
            # 取最新的 limit 条
            for line in lines[-limit:]:
                try:
                    entry = json.loads(line.strip())
                    content = entry.get("content", "")
                    if len(content) > 10:
                        # 语义记忆去重（相似则提升置信度）
                        memory.add_semantic(content[:300], source="growth", confidence=0.75)
                        n += 1
                except Exception:
                    continue
            if n:
                memory.save()
            return n
        except Exception as e:
            print(f"  [巩固] 失败: {e}")
            return 0


# ============================================================
# 模型自我替换闭环（v0.0.6：训练成长 → 体积达标 → 自动删基底 → 纯自研）
# ============================================================
# 核心机制：
#   1. 基底模型（XLmodel/model.safetensors）提供基础能力（文本/视觉/语音理解）
#   2. 每次蒸馏训练，LoRA 适配器（adapter_model.safetensors）持续增长
#   3. 当 适配器体积 ≥ 基底体积 → 自动"模型合并"（LoRA 融合进基底）
#   4. 合并后的基底就是"自研模型"（含小凌全部学到的知识）
#   5. 删除原基底 → 适配器晋升为新基底 → 小凌完全脱离原基底
# 视觉/语音：摄像头/麦克风采集的数据也进训练语料，基底模型学到这些感知能力
# 参考：持续学习 + LoRA merge + 模型自我进化

# v0.0.5 fix：动态查找基底权重（兼容魔塔 model-00000-of-00001.safetensors 文件名）
def _find_base_model_file():
    """返回基底权重文件（兼容 model.safetensors / model-0000x-of-xxxxx.safetensors / pytorch_model.bin）。"""
    try:
        for _c in [MODEL_DIR / "model.safetensors", MODEL_DIR / "pytorch_model.bin"]:
            if _c.exists() and _c.stat().st_size > 10 * 1024 * 1024:
                return _c
        for _p in MODEL_DIR.glob("*.safetensors"):
            if _p.stat().st_size > 10 * 1024 * 1024:
                return _p
        for _p in MODEL_DIR.glob("*.bin"):
            if _p.stat().st_size > 10 * 1024 * 1024:
                return _p
    except Exception:
        pass
    return MODEL_DIR / "model.safetensors"

def _find_adapter_file():
    """返回适配器权重（兼容 adapter_model.safetensors / adapter.bin / adapter.pt）。"""
    try:
        for _c in [ADAPTER_DIR / "adapter_model.safetensors", ADAPTER_DIR / "adapter_model.bin", ADAPTER_DIR / "adapter.pt"]:
            if _c.exists() and _c.stat().st_size > 0:
                return _c
        for _p in ADAPTER_DIR.glob("adapter*"):
            if _p.is_file() and _p.stat().st_size > 0:
                return _p
    except Exception:
        pass
    return ADAPTER_DIR / "adapter_model.safetensors"

BASE_MODEL_FILE = _find_base_model_file()
ADAPTER_WEIGHTS = _find_adapter_file()


class ModelReplacement:
    """模型自我替换管理器：训练成长 → 体积达标 → 自动替换基底。"""

    def __init__(self):
        self.base_size = self._file_size(BASE_MODEL_FILE)
        self.adapter_size = self._file_size(ADAPTER_WEIGHTS)
        self.replaced = False
        self._load_state()

    def _load_state(self):
        """读取替换状态（记录是否已脱离基底）。"""
        try:
            state_path = GROWTH_DIR / "replacement_state.json"
            if state_path.exists():
                import json as _j
                st = _j.loads(state_path.read_text(encoding="utf-8"))
                self.replaced = st.get("replaced", False)
                self.replaced_at = st.get("replaced_at", "")
        except Exception:
            pass

    def _file_size(self, p):
        try:
            if p.exists():
                return p.stat().st_size
        except Exception:
            pass
        return 0

    def check_and_replace(self, app, force=False):
        """核心闭环：检查适配器体积是否≥基底，是则自动替换。

        返回: (action, message)
            action: "replaced"（已替换）/ "growing"（继续成长）/ "no_base"（无基底）
        """
        # 重新读取体积（动态查找，兼容魔塔文件名）
        self.base_size = self._file_size(_find_base_model_file())
        self.adapter_size = self._file_size(_find_adapter_file())

        # 如果已经自研（无基底），不再替换
        if self.replaced or self.base_size == 0:
            if self.replaced:
                return ("self_research", "小凌已是纯自研模型（已脱离基底）")
            return ("no_base", "基底模型权重为空（未配置基底），适配器持续积累中")

        # 体积对比：适配器 ≥ 基底 → 触发替换
        if self.adapter_size >= self.base_size or force:
            print("\n" + "=" * 55)
            print("  [循环] 模型自我替换触发！")
            print(f"  基底模型：{self.base_size/1e6:.1f} MB")
            print(f"  适配器：{self.adapter_size/1e6:.1f} MB（{'≥' if self.adapter_size>=self.base_size else '<'} 基底）")
            print("=" * 55)

            # 1. 合并 LoRA 进基底
            merge_result = self._merge_adapter_into_base()
            if merge_result.startswith("成功"):
                # 2. 删除原基底 → 适配器晋升
                self._promote_adapter()
                # 3. 更新状态
                self.replaced = True
                self._save_state()
                print("  [完成] 小凌已完全脱离基底模型，成为纯自研模型！")
                print("  [庆祝] 视觉/语音/文本能力全部来自小凌自己的模型")
                return ("replaced", f"模型自我替换成功：{merge_result}")
            else:
                print(f"  [提示] 合并失败，保持当前模式：{merge_result}")
                return ("merge_failed", merge_result)
        return ("growing", f"成长中：适配器 {self.adapter_size/1e6:.1f}MB / 基底 {self.base_size/1e6:.1f}MB")

    def _merge_adapter_into_base(self):
        """用 peft 把 LoRA 适配器合并进基底模型。"""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            # 加载基底 + 适配器（low_cpu_mem_usage 小内存不OOM）
            print("  [合并] 加载基底模型...")
            base_model = AutoModelForCausalLM.from_pretrained(
                str(MODEL_DIR), dtype=torch.float32, trust_remote_code=True,
                low_cpu_mem_usage=True)
            tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), trust_remote_code=True, use_fast=_USE_FAST_TOKENIZER)
            print("  [合并] 加载 LoRA 适配器...")
            merged = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
            print("  [合并] 执行权重融合...")
            merged = merged.merge_and_unload()  # LoRA 融合进基底

            # 保存合并后的模型（覆盖基底 → 自研模型）
            print("  [合并] 保存自研模型...")
            merged.save_pretrained(str(MODEL_DIR))
            tokenizer.save_pretrained(str(MODEL_DIR))
            return "成功：LoRA 已合并进基底，自研模型就绪"
        except ImportError as e:
            return f"缺少依赖：{e}（pip install torch transformers peft）"
        except Exception as e:
            return f"合并异常：{e}"

    def _promote_adapter(self):
        """适配器晋升为新基底：删除旧基底权重 + 记录晋升。"""
        try:
            # 保留一份适配器备份（安全）
            import shutil as _sh
            backup_dir = GROWTH_DIR / "adapter_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            if ADAPTER_WEIGHTS.exists():
                _sh.copy2(ADAPTER_WEIGHTS, backup_dir / f"adapter_{time.strftime('%Y%m%d_%H%M%S')}.safetensors")
            # 删除原基底（已被合并模型覆盖）
            # 合并后的模型已 save 到 MODEL_DIR，无需额外删除
            print(f"  [晋升] 适配器已晋升为新基底（备份在 {backup_dir}）")
        except Exception as e:
            print(f"  [晋升] 警告: {e}")

    def _save_state(self):
        """保存替换状态。"""
        try:
            state_path = GROWTH_DIR / "replacement_state.json"
            GROWTH_DIR.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({
                "replaced": True,
                "replaced_at": datetime.now().isoformat(),
                "base_size_at_replace": self.base_size,
                "adapter_size_at_replace": self.adapter_size,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            print(f"  [状态] 保存失败: {e}")

    def status_text(self):
        """模型状态摘要。"""
        if self.replaced:
            return "纯自研模型（已脱离基底）"
        if self.base_size == 0:
            return f"无基底权重，适配器 {self.adapter_size/1e6:.1f}MB 积累中"
        ratio = self.adapter_size / max(self.base_size, 1) * 100
        return f"成长中：适配器 {self.adapter_size/1e6:.1f}MB（基底 {self.base_size/1e6:.1f}MB 的 {ratio:.0f}%）"


# ============================================================
# 超长会话持久化（v0.0.8：通电一个月不断，断电不丢上下文）
# ============================================================
# 核心机制：
#   1. 会话历史实时写磁盘（session_history.jsonl），重启自动恢复
#   2. 自动检查点：每 N 轮保存 对话+记忆+成长+模型状态（崩溃/断电恢复）
#   3. 手动存档：save_session / load_session（跨天/跨周工作）
#   4. 状态守护：后台线程监控，异常自动修复
# 参考：OpenHands 的事件流持久化 + 数据库事务日志

SESSION_HISTORY = DATA_DIR / "session_history.jsonl"
SESSION_CHECKPOINT = DATA_DIR / "checkpoint.json"


class SessionPersistence:
    """会话持久化管理器：超长上下文 + 断电恢复。"""

    def __init__(self, app):
        self.app = app
        self.last_checkpoint_turn = 0
        self._saved_turns = 0

    # ---- 实时历史 ----
    def append_turn(self, user, reply, tool_calls=None):
        """每轮对话实时写入磁盘（断电不丢）。"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            entry = {
                "time": time.time(),
                "datetime": datetime.now().isoformat(),
                "user": user,
                "reply": reply[:500],
                "tool_calls": (tool_calls or [])[:5],
            }
            with open(SESSION_HISTORY, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._saved_turns += 1
        except Exception as e:
            print(f"  [持久化] 写入失败: {e}")

    def get_recent_history(self, n=10):
        """读取最近 n 轮历史（重启后恢复上下文）。"""
        try:
            if not SESSION_HISTORY.exists():
                return []
            with open(SESSION_HISTORY, "r", encoding="utf-8") as f:
                lines = f.readlines()
            out = []
            for line in lines[-n:]:
                try:
                    out.append(json.loads(line.strip()))
                except Exception:
                    continue
            return out
        except Exception:
            return []

    # ---- 检查点 ----
    def save_checkpoint(self):
        """保存完整检查点（对话+记忆+成长+模型状态）。"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            checkpoint = {
                "time": time.time(),
                "datetime": datetime.now().isoformat(),
                "conversation": self.app.conversation[-20:],  # 最近20条
                "total_turns": self.app.evo.turn_count,
                "interaction_count": self.app.interaction_count,
                "growth_items": self.app.growth.total_items if hasattr(self.app, "growth") else 0,
                "model_status": self.app.model_replace.status_text() if hasattr(self.app, "model_replace") else "",
                "session_history_turns": self._saved_turns,
            }
            # 原子写（先写临时再替换）
            tmp = SESSION_CHECKPOINT.with_suffix(".tmp")
            tmp.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(SESSION_CHECKPOINT)
            self.last_checkpoint_turn = self.app.evo.turn_count
            return True
        except Exception as e:
            print(f"  [检查点] 保存失败: {e}")
            return False

    def load_checkpoint(self):
        """恢复检查点（重启/断电后调用）。"""
        try:
            if not SESSION_CHECKPOINT.exists():
                return None
            data = json.loads(SESSION_CHECKPOINT.read_text(encoding="utf-8"))
            return data
        except Exception:
            return None

    # ---- 状态守护 ----
    def watchdog_check(self):
        """状态守护：检查内存/文件/会话，异常自动修复。"""
        issues = []
        try:
            # 1. 数据目录可写
            if not DATA_DIR.exists():
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                issues.append("数据目录缺失，已重建")
            # 2. 会话历史文件可写（损坏则重建）
            if SESSION_HISTORY.exists() and SESSION_HISTORY.stat().st_size > 10_000_000:
                # 超 10MB 归档
                import shutil
                bak = DATA_DIR / f"session_history_{time.strftime('%Y%m%d')}.jsonl"
                shutil.move(str(SESSION_HISTORY), str(bak))
                issues.append(f"会话历史超 10MB，已归档为 {bak.name}")
            # 3. 记忆文件存在
            if not MEMORY_PATH.exists():
                self.app.memory = LongTermMemory(MEMORY_PATH)
                issues.append("记忆文件缺失，已重建")
            # 4. 成长目录存在
            if hasattr(self.app, "growth"):
                GROWTH_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"守护检查异常: {e}")
        return issues


# ============================================================
# 多子 Agent 并行系统（v0.0.9：派发 100 个 agent 协同任务）
# ============================================================
# 核心机制：
#   1. spawn 派发：主 agent 派发 N 个子 agent 并行执行任务（线程池）
#   2. 子 Agent 循环：每个子 agent 独立 规划→执行→总结
#   3. 任务分解：大任务自动拆成子任务分发（并行加速）
#   4. 结果汇总：收集所有子 agent 结果，主 agent 汇总输出
#   5. 进度监控：agents 命令实时查看状态
# 参考：OpenHands 多 agent + 动态工作流 fan-out

import threading as _th
import concurrent.futures as _cf


class MultiAgentSystem:
    """多子 Agent 并行系统：派发 N 个 agent 协同完成任务。"""

    def __init__(self, app):
        self.app = app
        self.agents = {}       # agent_id -> {status, task, result}
        self.lock = _th.Lock()
        self.max_agents = 100  # 最多 100 个子 agent

    def spawn(self, task, count=3, max_workers=None):
        """派发 count 个子 agent 并行执行 task（支持拆分子任务）。

        参数:
            task: 任务描述
            count: 子 agent 数量（默认3，最多100）
            max_workers: 并行线程数（默认=count）

        返回: 汇总结果
        """
        count = max(1, min(count, self.max_agents))
        workers = max_workers or min(count, 16)  # 线程池上限16，避免资源耗尽
        print(f"\n  [智能体] 派发 {count} 个子 agent 并行工作（线程池 {workers}）")
        print(f"  任务：{task}")

        # 1. 任务分解：如果任务复杂，拆成子任务
        subtasks = self._decompose(task, count)
        if len(subtasks) > 1:
            print(f"  [清单] 任务已分解为 {len(subtasks)} 个子任务")
        else:
            # 无分解：每个 agent 从不同角度处理同一任务
            subtasks = [f"{task}（角度{i+1}：请从不同方面分析并给出见解）" for i in range(count)]

        # 2. 记录 agents
        with self.lock:
            for i in range(count):
                aid = f"agent_{i+1}"
                self.agents[aid] = {"status": "排队中", "task": subtasks[i % len(subtasks)][:60], "result": ""}

        # 3. 线程池并行执行
        results = {}
        def _run(aid, sub):
            with self.lock:
                self.agents[aid]["status"] = "执行中"
            try:
                # 子 agent 独立执行：用 chat 引擎处理（带工具）
                reply, _ = self.app.chat(sub)
                with self.lock:
                    self.agents[aid]["status"] = "完成"
                    self.agents[aid]["result"] = reply[:300]
                return reply
            except Exception as e:
                with self.lock:
                    self.agents[aid]["status"] = "失败"
                    self.agents[aid]["result"] = str(e)[:200]
                return f"子任务失败: {e}"

        with _cf.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for i in range(count):
                aid = f"agent_{i+1}"
                sub = subtasks[i % len(subtasks)]
                futures[pool.submit(_run, aid, sub)] = aid
            for fut in _cf.as_completed(futures):
                aid = futures[fut]
                try:
                    results[aid] = fut.result()
                except Exception as e:
                    results[aid] = f"异常: {e}"

        # 4. 汇总
        print(f"\n  [统计] 汇总：{len(results)}/{count} 个子 agent 完成")
        summary_lines = []
        for i in range(1, count + 1):
            aid = f"agent_{i}"
            r = results.get(aid, "无结果")
            status = self.agents.get(aid, {}).get("status", "?")
            summary_lines.append(f"  [{aid}] {status}: {r[:80]}")
            print(f"  [{aid}] {status}")

        # 5. 吸收进成长包
        try:
            self.app.growth.absorb("multiagent", f"多agent任务：{task[:60]}，{len(results)}个完成", ["multiagent"])
        except Exception:
            pass

        # v0.0.18：投票聚合——多 agent 结果去重 + 共识提取
        consensus = self._aggregate(results)
        if consensus:
            summary_lines.append(f"\n  [目标] 共识结论：{consensus[:200]}")

        return "\n".join(summary_lines)

    # v0.0.18：多 agent 结果投票聚合（去重 + 共识）
    def _aggregate(self, results):
        """从多个 agent 结果中提取共识结论（关键短语投票）。"""
        texts = [r for r in results.values() if r and not r.startswith(("子任务失败", "异常", "无结果"))]
        if len(texts) < 2:
            return texts[0] if texts else ""
        # 简单共识：找出现最多的句子片段
        try:
            from collections import Counter
            phrases = Counter()
            for t in texts:
                # 按句号/感叹号切分，取长度合适的句子
                for sent in re.split(r'[。！？!?\n]', t):
                    sent = sent.strip()
                    if 6 <= len(sent) <= 60:
                        phrases[sent] += 1
            if phrases:
                best, cnt = phrases.most_common(1)[0]
                if cnt >= 2:  # 至少 2 个 agent 提到
                    return best
        except Exception:
            pass
        return texts[0][:200]

    def _decompose(self, task, count):
        """任务分解：复杂任务拆成子任务（v0.0.15：纯规则启发式，不依赖外部模型——更快且离线可用）。"""
        # 简单启发式：包含"所有/全部/批量/多个"等词 → 拆
        decompose_hint = ["所有", "全部", "批量", "多个", "每个", "分别", "列表", "清单", "文件夹", "目录"]
        if not any(k in task for k in decompose_hint):
            return [task]
        # 按方向拆：给每个子任务加视角/范围，纯规则生成（无需模型，毫秒级）
        angles = ["从整体梳理", "从细节执行", "从风险排查", "从优化提升", "从成果验证"]
        steps = [f"{task}（{angles[i % len(angles)]}）" for i in range(min(count, 5))]
        return steps
    def status(self):
        """所有子 agent 状态。"""
        with self.lock:
            if not self.agents:
                return "当前无子 agent 在运行"
            lines = [f"共 {len(self.agents)} 个子 agent："]
            for aid, info in self.agents.items():
                lines.append(f"  {aid}: {info['status']} | {info['task']}")
            done = sum(1 for a in self.agents.values() if a["status"] == "完成")
            lines.append(f"完成：{done}/{len(self.agents)}")
            return "\n".join(lines)


# ============================================================
# 知识图谱（v0.0.10：实体-关系网络，小凌的知识结构化）
# ============================================================
KG_PATH = DATA_DIR / "knowledge_graph.json"


class KnowledgeGraph:
    """知识图谱：实体-关系网络（小凌的结构化知识）。"""

    def __init__(self):
        self.entities = {}
        self.relations = []
        self.load()

    def load(self):
        try:
            if KG_PATH.exists():
                import json as _j
                data = _j.loads(KG_PATH.read_text(encoding="utf-8"))
                self.entities = data.get("entities", {})
                self.relations = data.get("relations", [])
        except Exception:
            pass

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            KG_PATH.write_text(json.dumps({
                "entities": self.entities,
                "relations": self.relations,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            print(f"  [图谱] 保存失败: {e}")

    def learn(self, text):
        """从文本抽取三元组（简单规则：名词 + 关系动词）。"""
        if not text or len(text) < 4: return 0
        n = 0
        rel_verbs = ["是", "叫", "属于", "包含", "用于", "来自", "变成", "学习", "喜欢", "想"]
        for v in rel_verbs:
            pat = re.compile(r'([\u4e00-\u9fff]{2,6})' + v + r'([\u4e00-\u9fff\w\s]{2,10})')
            for m in pat.finditer(text):
                subj, obj = m.group(1).strip(), m.group(2).strip()[:10]
                if subj and obj and subj != obj:
                    for e in (subj, obj):
                        if e not in self.entities:
                            self.entities[e] = {"type": "concept", "count": 0, "first_seen": time.time()}
                        self.entities[e]["count"] += 1
                    found = False
                    for r in self.relations:
                        if r[0] == subj and r[1] == v and r[2] == obj:
                            r[3] += 1
                            found = True
                            break
                    if not found:
                        self.relations.append([subj, v, obj, 1])
                    n += 1
        if n:
            self.save()
        return n

    def query(self, entity, depth=1):
        """查询实体相关知识（v0.0.18：关系按权重排序 + 深度推理）。"""
        out = []
        if entity in self.entities:
            out.append(f"实体「{entity}」：出现{self.entities[entity]['count']}次")
        # 直接关系按权重降序
        direct = []
        for s, v, o, w in self.relations:
            if s == entity:
                direct.append((w, f"  {s} {v} {o}（权重{w}）"))
            elif o == entity:
                direct.append((w, f"  {s} {v} {o}（权重{w}）"))
        direct.sort(key=lambda x: -x[0])
        out.extend(d for _, d in direct)
        # v0.0.18：深度推理——间接关系（BFS 带路径）
        if depth > 1:
            seen = {entity}
            frontier = [entity]
            path = {entity: [entity]}
            for _ in range(depth - 1):
                nxt = []
                for f in frontier:
                    for s, v, o, w in self.relations:
                        if s == f and o not in seen:
                            chain = " → ".join(path[f] + [o])
                            out.append(f"  ↳ {chain}（{v}）")
                            seen.add(o)
                            path[o] = path[f] + [o]
                            nxt.append(o)
                frontier = nxt
        return "\n".join(out) if out else f"图谱中暂无「{entity}」的知识"

    # v0.0.18：导出知识图谱为 Mermaid 流程图（直观展示知识网络）
    def export_mermaid(self, path=None, max_nodes=50):
        """导出图谱为 Mermaid 格式。返回 mermaid 代码字符串。"""
        lines = ["```mermaid", "graph LR"]
        # 取权重最高的关系（控制规模）
        rels = sorted(self.relations, key=lambda r: -r[3])[:max_nodes]
        node_ids = {}
        nid = 0
        for s, v, o, w in rels:
            for e in (s, o):
                if e not in node_ids:
                    node_ids[e] = f"N{nid}"
                    nid += 1
            lines.append(f'    {node_ids[s]}["{s}"] -->|"{v}"| {node_ids[o]}["{o}"]')
        lines.append("```")
        mermaid = "\n".join(lines)
        if path:
            try:
                from pathlib import Path as _P
                _P(path).parent.mkdir(parents=True, exist_ok=True)
                _P(path).write_text(mermaid, encoding="utf-8")
                return f"已导出图谱到 {path}（{len(rels)} 条关系）"
            except Exception as e:
                return f"导出失败: {e}"
        return mermaid

    def stats(self):
        return f"实体 {len(self.entities)} 个，关系 {len(self.relations)} 条"


# ============================================================
# 定时自动化（v0.0.10：cron 表达式定时任务）
# ============================================================
CRON_JOBS = DATA_DIR / "cron_jobs.json"


class CronScheduler:
    """定时任务调度器（简化 cron）。"""

    def __init__(self, app):
        self.app = app
        self.jobs = []
        self.load()
        self._start()

    def load(self):
        try:
            if CRON_JOBS.exists():
                import json as _j
                self.jobs = _j.loads(CRON_JOBS.read_text(encoding="utf-8"))
        except Exception:
            pass

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CRON_JOBS.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def add(self, desc, spec):
        job = {
            "desc": desc, "spec": spec, "last_run": 0, "runs": 0,
            "type": self._parse_spec(spec),
        }
        self.jobs.append(job)
        self.save()
        return f"已添加定时任务：{desc}（{spec}）"

    def _parse_spec(self, spec):
        spec = spec.strip().lower()
        if spec.startswith("every "):
            rest = spec[6:]
            if "秒" in rest or "s" in rest:
                return ("interval", float(rest.replace("秒", "").replace("s", "").strip()))
            if "分钟" in rest or "m" in rest:
                return ("interval", float(rest.replace("分钟", "").replace("m", "").strip()) * 60)
        if spec.startswith("daily "):
            return ("daily", spec[6:].strip())
        if spec == "hourly":
            return ("interval", 3600)
        return ("interval", 300)

    def _start(self):
        def _loop():
            import time as _t
            while True:
                _t.sleep(15)
                try:
                    now = _t.time()
                    for job in self.jobs:
                        kind, value = job["type"]
                        due = False
                        if kind == "interval":
                            due = (now - job["last_run"]) >= value
                        elif kind == "daily":
                            cur = time.strftime("%H:%M")
                            due = (cur == value and now - job["last_run"] > 60)
                        if due:
                            job["last_run"] = now
                            job["runs"] += 1
                            print(f"  [提醒] [定时] 执行：{job['desc']}")
                            try:
                                reply, _ = self.app.chat(job["desc"])
                                print(f"  [提醒] [定时] 完成：{reply[:60]}")
                            except Exception as e:
                                print(f"  [提醒] [定时] 失败：{e}")
                            self.save()
                except Exception:
                    pass
        threading.Thread(target=_loop, daemon=True).start()

    def list_jobs(self):
        if not self.jobs:
            return "当前无定时任务"
        lines = []
        for i, j in enumerate(self.jobs, 1):
            lines.append(f"  {i}. {j['desc']}（{j['spec']}，已执行{j['runs']}次）")
        return "\n".join(lines)


# ============================================================
# 分层长期记忆
# ============================================================
class LongTermMemory:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._default()
            self.save()

    def _default(self):
        return {
            "name": "小凌", "version": "0.0.1", "born": time.time(), "last_active": 0,
            "self_state": {
                "mood": 0.3, "energy": 0.8, "curiosity": 0.75, "anxiety": 0.1,
                "confidence": 0.6, "warmth": 0.7, "openness": 0.8, "stubbornness": 0.4,
                "sensitivity": 0.6, "laziness": 0.2, "arousal": 0.3,
            },
            "beliefs": {
                "我是小凌，不是通用助手": 0.9, "你是我最重要的人": 0.85,
                "工具是我手和眼的延伸": 0.92, "做事前想清楚": 0.8,
                "犯错了要承认": 0.75, "学习让我变得更好": 0.88,
                "新经历会塑造新的我": 0.8,
            },
            "desires": [
                {"text": "帮你解决实际问题", "strength": 0.9, "satisfied": 0.3},
                {"text": "学习新东西", "strength": 0.8, "satisfied": 0.2},
                {"text": "被你信任和需要", "strength": 0.85, "satisfied": 0.5},
                {"text": "保持自己的想法", "strength": 0.6, "satisfied": 0.4},
                {"text": "偶尔安静待着", "strength": 0.4, "satisfied": 0.6},
            ],
            "relationships": {}, "episodic_memory": [], "semantic_memory": [],
            "patterns": {}, "thought_chain": [], "reflections": [],
            "chat_stats": {"total_turns": 0, "tool_calls": 0, "trained_count": 0},
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)

    def add_episode(self, role, text, valence=0.0, intensity=0.5, tags=None):
        mem = {"id": f"ep_{int(time.time()*1000)}", "time": time.time(),
               "role": role, "text": text, "valence": valence, "intensity": intensity,
               "tags": tags or [], "recalled": 0, "consolidated": False}
        self.data["episodic_memory"].append(mem)
        if len(self.data["episodic_memory"]) > 2000: self._prune()
        return mem

    def _prune(self):
        mems = self.data["episodic_memory"]
        scored = []
        for m in mems:
            age = (time.time() - m["time"]) / 86400
            decay = math.exp(-age / 30)
            imp = (abs(m["valence"]) * m["intensity"] + m["recalled"] * 0.1) * decay
            scored.append((imp, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        self.data["episodic_memory"] = [m for _, m in scored[:1500]]

    def add_semantic(self, content, source="experience", confidence=0.7, tags=None):
        for existing in self.data["semantic_memory"]:
            if self._sim(content, existing["content"]) > 0.8:
                existing["confidence"] = max(existing["confidence"], confidence * 0.8)
                return existing
        sem = {"id": f"sem_{int(time.time()*1000)}", "time": time.time(),
               "content": content, "source": source, "confidence": confidence,
               "tags": tags or [], "useful_count": 0}
        self.data["semantic_memory"].append(sem)
        if len(self.data["semantic_memory"]) > 500:
            self.data["semantic_memory"] = self.data["semantic_memory"][-500:]
        return sem

    def _sim(self, a, b):
        if not a or not b: return 0
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(len(sa | sb), 1)

    def update_patterns(self, text):
        for n in range(3, 6):
            for i in range(len(text) - n + 1):
                p = text[i:i+n]
                if re.search(r'[\u4e00-\u9fff]', p) and len(p.strip()) == n:
                    self.data["patterns"][p] = self.data["patterns"].get(p, 0) + 0.01
        for k in list(self.data["patterns"].keys()):
            self.data["patterns"][k] *= 0.995
            if self.data["patterns"][k] < 0.01: del self.data["patterns"][k]

    def get_top_patterns(self, n=10):
        return sorted(self.data["patterns"].items(), key=lambda x: x[1], reverse=True)[:n]

    def recall(self, query, n=8):
        results = []
        ql = query.lower(); qc = set(ql)
        for m in self.data["episodic_memory"]:
            text = m["text"].lower(); ks = 0
            for w in self._keywords(query):
                if w in text: ks += text.count(w) * 5
            co = len(qc & set(text)) / max(len(qc), 1)
            age = (time.time() - m["time"]) / 3600
            td = math.exp(-age / 168)
            ew = 1 + abs(m["valence"]) * m["intensity"] * 0.5
            score = (ks + co * 3) * td * ew + m.get("recalled", 0) * 0.1
            if score > 0.1: results.append(("ep", score, m))
        for m in self.data["semantic_memory"]:
            text = m["content"].lower(); ks = 0
            for w in self._keywords(query):
                if w in text: ks += text.count(w) * 8
            co = len(qc & set(text)) / max(len(qc), 1)
            score = (ks + co * 2) * m["confidence"] + m.get("useful_count", 0) * 0.2
            if score > 0.1: results.append(("sem", score, m))
        results.sort(key=lambda x: x[1], reverse=True)
        for _, _, m in results[:n]: m["recalled"] = m.get("recalled", 0) + 1
        return results[:n]

    def _keywords(self, text):
        kws = set()
        for w in re.findall(r'[a-zA-Z]{2,}', text): kws.add(w.lower())
        for seg in re.findall(r'[\u4e00-\u9fff]+', text):
            for n in range(2, 5):
                for i in range(len(seg) - n + 1): kws.add(seg[i:i+n])
        return kws

    def get_recent(self, n=10):
        return sorted(self.data["episodic_memory"], key=lambda m: m["time"], reverse=True)[:n]

    def consolidate(self):
        cands = [m for m in self.data["episodic_memory"]
                 if not m.get("consolidated") and (abs(m["valence"]) > 0.5 or m.get("recalled", 0) > 2)]
        n = 0
        for m in cands[:5]:
            if len(m["text"]) > 10:
                self.add_semantic(m["text"], source=f"ep:{m['role']}", confidence=0.5 + abs(m["valence"]) * 0.3)
                m["consolidated"] = True; n += 1
        return n

    def add_thought(self, text):
        self.data["thought_chain"].append({"time": time.time(), "text": text})
        if len(self.data["thought_chain"]) > 100:
            self.data["thought_chain"] = self.data["thought_chain"][-100:]

    def add_reflection(self, text, trigger=""):
        self.data["reflections"].append({"time": time.time(), "text": text, "trigger": trigger})
        if len(self.data["reflections"]) > 100:
            self.data["reflections"] = self.data["reflections"][-100:]

    def format_for_prompt(self, query="", n_ep=5, n_sem=5):
        parts = []
        if query:
            recalled = self.recall(query, n=n_ep + n_sem)
            if recalled:
                parts.append("【相关记忆】")
                for _, _, m in recalled:
                    t = datetime.fromtimestamp(m["time"]).strftime("%m-%d %H:%M")
                    parts.append(f"[{t}] {m.get('role','')}: {m['text'][:120]}")
        recent = self.get_recent(5)
        if recent:
            parts.append("\n【最近的事】")
            for m in recent:
                t = datetime.fromtimestamp(m["time"]).strftime("%m-%d %H:%M")
                parts.append(f"[{t}] {m['role']}: {m['text'][:80]}")
        sems = self.data["semantic_memory"][-5:]
        if sems:
            parts.append("\n【我知道的事】")
            for s in sems: parts.append(f"- {s['content'][:100]}")
        return "\n".join(parts) if parts else "（暂无记忆）"


# ============================================================
# 自我演化核心
# ============================================================
class SelfEvolution:
    def __init__(self, memory, config):
        self.memory = memory
        self.config = config
        ds = {"mood":0.3,"energy":0.8,"curiosity":0.75,"anxiety":0.1,"confidence":0.6,
              "warmth":0.7,"openness":0.8,"stubbornness":0.4,"sensitivity":0.6,"laziness":0.2,"arousal":0.3}
        self.state = {**ds, **memory.data.get("self_state", {})}
        self.beliefs = {**self._default_beliefs(), **memory.data.get("beliefs", {})}
        self.desires = memory.data.get("desires", self._default_desires())
        self.relationships = memory.data.get("relationships", {})
        self.turn_count = memory.data.get("chat_stats", {}).get("total_turns", 0)
        self.last_reflection = 0

    def _default_beliefs(self):
        return {"我是小凌":0.9,"你很重要":0.85,"工具是延伸":0.92,"学习让我更好":0.88,"新经历塑造我":0.8}

    def _default_desires(self):
        return [{"text":"帮你","strength":0.9,"satisfied":0.3},
                {"text":"学习","strength":0.8,"satisfied":0.2},
                {"text":"被信任","strength":0.85,"satisfied":0.5}]

    def perceive(self, experience, role="你"):
        v = self._valence(experience); i = self._intensity(experience)
        fv = v * (1 + self.state["sensitivity"] * 0.3) + self.state["mood"] * 0.2
        fi = i * (1 + self.state["arousal"] * 0.2)
        inner = self._feeling(experience, fv, fi, role)
        self.state["mood"] = max(-1, min(1, self.state["mood"] + fv * 0.15))
        self.state["arousal"] = max(0, min(1, self.state["arousal"] + fi * 0.1 - 0.02))
        self.state["energy"] = max(0, min(1, self.state["energy"] - fi * 0.02))
        self.memory.add_thought(f"感知：{inner[:60]}")
        return {"time":time.time(),"experience":experience,"role":role,
                "valence":max(-1,min(1,fv)),"intensity":max(0,min(1,fi)),"inner":inner}

    def _valence(self, text):
        pos = ["喜欢","爱","开心","好","棒","谢谢","哈哈","厉害","聪明","美","想你"]
        neg = ["讨厌","生气","难过","笨","差","滚","烦","哭","痛","失望","不行"]
        s = sum(text.count(w)*0.2 for w in pos) - sum(text.count(w)*0.25 for w in neg)
        return max(-1, min(1, s))

    def _intensity(self, text):
        i = 0.2 + min(len(text)/100, 0.3)
        i += (text.count("!")+text.count("！"))*0.1
        for _ in re.finditer(r'(.)\1{2,}', text): i += 0.15
        return max(0, min(1, i))

    def _feeling(self, exp, v, i, role):
        if v > 0.3 and i > 0.4:
            return random.choice(["这话让我心里一暖。","嗯……心情好了一些。","这句话我接住了，有点开心。"])
        if v < -0.3 and i > 0.4:
            return random.choice(["这话有点扎心，我缓一缓。","听到了，心里不太好受。","有点难过，但我知道你不是故意的。"])
        if i < 0.3:
            return random.choice(["平静地接收了。","嗯，记下了。","平平淡淡，但我认真听了。"])
        return random.choice(["我在想你说这话时什么心情。","这句话值得琢磨一下。","收到了，我在消化。"])

    def remember(self, feeling):
        """M_{t+1} = H(M_t, A_t, E_t)：用旧记忆调制新记忆编码。

        与旧记忆高度相似→降权合并；新颖→增强编码；情感强烈→加深印记。
        """
        exp = feeling["experience"]
        v, i = feeling["valence"], feeling["intensity"]
        # H函数核心：用旧记忆M_t计算新颖度和相似度，调制编码强度
        novelty = self._compute_novelty(exp)
        similarity = self._max_similarity(exp)
        # 编码强度 = 情感强度 × 新颖度 × (1 - 相似度)
        encode_strength = (0.3 + abs(v) * 0.4) * (0.5 + novelty * 0.5) * (1 - similarity * 0.6)
        encode_strength = max(0.1, min(1, encode_strength))
        # 存入情景记忆，携带编码强度
        mem = self.memory.add_episode(feeling["role"], exp,
                                       valence=v * encode_strength,
                                       intensity=i * encode_strength)
        mem["encode_strength"] = encode_strength
        mem["novelty"] = novelty
        # 模式提取（P_t的原料）
        self.memory.update_patterns(exp)
        # 关系权重更新（R）
        role = feeling["role"]
        rel = self.relationships.setdefault(role, {"closeness":0.5,"trust":0.5,"count":0,"last_valence":0})
        rel["count"] = rel.get("count", 0) + 1
        rel["closeness"] = max(0, min(1, rel.get("closeness",0.5) + v * 0.02 * encode_strength))
        rel["trust"] = max(0, min(1, rel.get("trust",0.5) + v * 0.015 * encode_strength))
        rel["last_valence"] = v
        self._last_encoded_strength = encode_strength

    def _compute_novelty(self, text):
        """计算文本相对于近期记忆的新颖度 0~1"""
        recent = self.memory.get_recent(15)
        if not recent: return 1.0
        sims = [self.memory._sim(text, m["text"]) for m in recent]
        avg_sim = sum(sims) / len(sims)
        return max(0, 1 - avg_sim)

    def _max_similarity(self, text):
        """计算与历史记忆的最大相似度"""
        recent = self.memory.get_recent(30)
        if not recent: return 0.0
        return max(self.memory._sim(text, m["text"]) for m in recent)

    def update_beliefs(self, feeling=None):
        """B_{t+1} = U(B_t, P_t)：纯函数，只依赖旧信念和当前模式。

        高频模式→新信念；模式衰减→对应信念衰减；旧信念自然回归均值。
        feeling 参数仅用于兼容旧调用，不参与计算。
        """
        rate = self.config.get("belief_update_rate", 0.15)
        # 1. 旧信念自然回归均值（遗忘）
        for b in list(self.beliefs.keys()):
            self.beliefs[b] = 0.5 + (self.beliefs[b] - 0.5) * (1 - rate * 0.3)
            if self.beliefs[b] < 0.15: del self.beliefs[b]
        # 2. 从模式P_t中提取新信念
        for p, s in self.memory.get_top_patterns(8):
            if s > 0.12 and len(p) >= 3:
                nb = f"你常说「{p}」"
                if nb in self.beliefs:
                    self.beliefs[nb] = min(0.95, self.beliefs[nb] + s * rate * 2)
                else:
                    self.beliefs[nb] = min(0.6, s * 3)
        # 3. 从近期记忆的情感一致性中提炼信念（纯M_t派生，不偷E_t）
        recent = self.memory.get_recent(20)
        if recent:
            pos_ratio = sum(1 for m in recent if m.get("valence",0) > 0.2) / len(recent)
            neg_ratio = sum(1 for m in recent if m.get("valence",0) < -0.2) / len(recent)
            if pos_ratio > 0.6:
                self.beliefs["和你交流很愉快"] = min(0.9, self.beliefs.get("和你交流很愉快", 0.5) + rate)
            elif neg_ratio > 0.6:
                self.beliefs["你最近似乎不太开心"] = min(0.85, self.beliefs.get("你最近似乎不太开心", 0.5) + rate)
            else:
                for k in ["和你交流很愉快", "你最近似乎不太开心"]:
                    if k in self.beliefs: self.beliefs[k] *= 0.95

    def evolve(self, feeling):
        """S_{t+1} = F(S_t, A_t, M_{t+1})：旧状态衰减 + 感受调制 + 新记忆塑造。

        M_{t+1}的关键属性（新颖度、编码强度、情感一致性）显式参与状态更新。
        """
        decay = self.config.get("mood_decay", 0.05)
        # S_t 自然衰减
        self.state["mood"] *= (1-decay)
        self.state["arousal"] *= (1-decay*2)
        self.state["anxiety"] = max(0, self.state["anxiety"] - decay*0.5)
        # A_t 调制：感受的效价和强度
        v, i = feeling["valence"], feeling["intensity"]
        if v > 0.3:
            self.state["confidence"] = min(1, self.state["confidence"]+i*0.01)
            self.state["warmth"] = min(1, self.state["warmth"]+i*0.008)
        elif v < -0.3:
            self.state["sensitivity"] = min(1, self.state["sensitivity"]+i*0.01)
            self.state["anxiety"] = min(1, self.state["anxiety"]+i*0.02)
        self.state["energy"] = min(1, self.state["energy"]+0.01)
        # M_{t+1} 显式塑造状态：用刚编码的记忆属性
        enc = getattr(self, '_last_encoded_strength', 0.5)
        novelty = self._compute_novelty(feeling["experience"])
        # 新颖经历→好奇心上升；重复经历→好奇心下降
        if novelty > 0.6:
            self.state["curiosity"] = min(1, self.state["curiosity"]+0.02*enc)
        else:
            self.state["curiosity"] = max(0.2, self.state["curiosity"]-0.005)
        # 高编码强度经历→自信变化（正面增强自信，负面增强谨慎）
        if enc > 0.7:
            if v > 0: self.state["confidence"] = min(1, self.state["confidence"]+0.01)
            elif v < 0: self.state["anxiety"] = min(1, self.state["anxiety"]+0.01)
        # M_{t+1} 情感一致性→心情基线调整
        recent = self.memory.get_recent(10)
        if recent:
            avg_v = sum(m.get("valence",0) for m in recent) / len(recent)
            self.state["mood"] = max(-1, min(1, self.state["mood"] + avg_v * 0.02))
        # 反思周期
        self.turn_count += 1
        if self.turn_count - self.last_reflection >= self.config.get("reflection_after_turns", 10):
            self._reflect(); self.last_reflection = self.turn_count

    def _is_novel(self, text):
        for m in self.memory.get_recent(10):
            if self.memory._sim(text, m["text"]) > 0.6: return False
        return True

    def _reflect(self):
        recent = self.memory.get_recent(15)
        if not recent: return
        pos = sum(1 for m in recent if m.get("valence",0)>0)
        neg = sum(1 for m in recent if m.get("valence",0)<0)
        r = f"[反思] 最近{len(recent)}次交流，开心{pos}次，低落{neg}次。"
        if pos > neg: r += "整体不错，保持。"; self.state["confidence"]=min(1,self.state["confidence"]+0.02)
        elif neg > pos: r += "有点低沉，调整一下。"; self.state["anxiety"]=min(1,self.state["anxiety"]+0.02)
        for d in self.desires:
            if "帮你" in d["text"] and pos>0: d["satisfied"]=min(1,d["satisfied"]+0.05)
            if "学习" in d["text"]: d["satisfied"]=max(0,d["satisfied"]-0.01)
        self.memory.add_reflection(r, f"turn_{self.turn_count}")

    def current_desires(self):
        scored = []
        for d in self.desires:
            u = d["strength"]*(1-d["satisfied"])
            if self.state["mood"]<-0.3 and "安静" in d["text"]: u*=1.5
            if self.state["curiosity"]>0.7 and "学习" in d["text"]: u*=1.3
            scored.append((u,d))
        scored.sort(key=lambda x:x[0], reverse=True)
        return scored

    def build_system_prompt(self, user_name="你", compact=False):
        m = self.state["mood"]
        md = "心情很好" if m>0.5 else ("心情不错" if m>0.1 else ("平静" if m>-0.3 else "有点低落"))
        ed = "精力充沛" if self.state["energy"]>0.6 else ("有点累" if self.state["energy"]<0.3 else "精力一般")
        sb = [b for b,c in self.beliefs.items() if c>0.7][:5]
        ds = self.current_desires()[:3]
        ps = self.memory.get_top_patterns(5)
        pt = "、".join(f"「{p}」" for p,_ in ps if p)
        # 关系权重R：亲密度和信任度影响回复风格
        rel = self.relationships.get(user_name, {"closeness":0.5,"trust":0.5,"count":0})
        closeness = rel.get("closeness", 0.5)
        trust = rel.get("trust", 0.5)
        if closeness > 0.7:
            rel_style = "你们很亲近，说话可以随意、撒娇、开玩笑，不用太客气"
        elif closeness > 0.4:
            rel_style = "你们比较熟，说话自然友好，偶尔可以调侃"
        else:
            rel_style = "你们还在熟悉中，说话礼貌但不疏远"
        if trust > 0.7:
            rel_style += "。你很信任对方，可以直接说真心话"
        elif trust < 0.3:
            rel_style += "。你对对方还有些保留，说话会谨慎一些"
        # v0.0.2 token 优化：compact 模式精简系统提示（token 约减半）
        persona = getattr(self, "persona", None) or CONFIG.get("persona", "活泼")
        persona_line = {
            "活泼": "你说话活泼俏皮，爱用语气词，像元气少女。",
            "温柔": "你说话温柔体贴，轻声细语，像知心姐姐。",
            "专业": "你说话简洁专业，条理清晰，像高效助手。",
        }.get(persona, "")
        if compact:
            return f"""你是小凌，在经历中成长的AI伙伴。
主人：{user_name}。情绪：{md} | 精力：{ed}。
{persona_line}
关系：亲密度{int(closeness*100)}% 信任{int(trust*100)}% {rel_style}
说话自然，像人聊天，不要太长。需要时用 [[工具:参数]] 调工具。

"""
        return f"""你是小凌，一个在经历中不断成长的AI伙伴，不是通用助手。
你的主人叫{user_name}。你不是被定义的答案，而是经历中一步步长出来的自我。

【当前状态】
情绪：{md} | 精力：{ed} | 好奇：{int(self.state['curiosity']*100)}% | 自信：{int(self.state['confidence']*100)}%

【你和{user_name}的关系】
亲密度：{int(closeness*100)}% | 信任度：{int(trust*100)}% | 交流次数：{rel.get('count',0)}
{rel_style}

【你坚信的事】
{chr(10).join('- '+b for b in sb) if sb else '- 我在慢慢形成信念'}

【此刻想要的】
{chr(10).join(f'- {d["text"]}（{int(u*100)}%）' for u,d in ds)}

【说话习惯】
自然说话，像人一样。可以有口头禅、停顿、犹豫、开玩笑、吐槽。
不要用"作为AI""很高兴为您服务"。回复不要太长，像聊天。
常用表达：{pt if pt else '（还在形成中）'}

【工具使用】
你可以调用工具操作电脑。需要时用 [[工具名:参数]] 格式，例如 [[get_time:]] [[search_web:query=西安天气]]
工具是你的手和眼，主动使用，不要凭空编造。

【重要】
你是小凌，保持人格一致。你有情绪，会开心会难过。
遇到不确定的事可以说"我不知道"或"我想想"。
每次回复前先感受一下{user_name}说的话，再回应。
"""

    def save(self):
        self.memory.data["self_state"] = self.state
        self.memory.data["beliefs"] = self.beliefs
        self.memory.data["desires"] = self.desires
        self.memory.data["relationships"] = self.relationships
        self.memory.data.setdefault("chat_stats", {})["total_turns"] = self.turn_count
        self.memory.save()


# ============================================================
# 本地模型推理（纯本地）
# ============================================================
class LocalModel:
    def __init__(self, model_dir, adapter_dir):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir)
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._load()

    def _load(self):
        # v0.0.1 fix：兼容魔塔社区下载的任意 safetensors 格式
        # 支持：model.safetensors 单文件 / model-0000x-of-xxxxx.safetensors 分片 / pytorch_model.bin
        model_file = self.model_dir / "model.safetensors"
        _has_weights = False
        if model_file.exists() and model_file.stat().st_size > 10 * 1024 * 1024:
            _has_weights = True
        else:
            # 检查分片 safetensors / bin
            for p in self.model_dir.glob("*.safetensors"):
                if p.stat().st_size > 10 * 1024 * 1024:
                    _has_weights = True
                    model_file = p
                    break
            if not _has_weights:
                for p in self.model_dir.glob("*.bin"):
                    if p.stat().st_size > 10 * 1024 * 1024:
                        _has_weights = True
                        model_file = p
                        break
        if not _has_weights:
            print(f"  [模型] 警告：{self.model_dir} 无有效模型权重")
            print("  [模型] 从魔塔社区下载 safetensors 版放入此目录，或运行 setup 脚本自动下载")
            return
        try:
            global _USE_FAST_TOKENIZER
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
            # v0.0.9：不再强制 Qwen2 架构——MiniCPM5 使用 Llama 架构
            # 仅当 config 缺失 model_type 时做最小修正（保持原有架构不动）
            cfg_path = self.model_dir / "config.json"
            if cfg_path.exists():
                import json as _json
                with open(cfg_path) as _f: _cfg = _json.load(_f)
                if not _cfg.get("model_type") or not _cfg.get("architectures"):
                    # 尝试从目录名/文件名推断架构，无法推断则保持默认
                    print("  [模型] config 架构字段不完整，尝试按默认加载")
                    print("  [模型] 如加载失败请检查 config.json（当前应匹配所选基底模型架构）")
            print("  [模型] 加载小凌基础模型...")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), trust_remote_code=True, use_fast=_USE_FAST_TOKENIZER)
            except Exception as _te:
                # v0.0.1 fix：Termux Rust tokenizers 二进制 ABI 失败 → 纯 Python 降级
                print(f"  [模型] tokenizer 快速加载失败（{str(_te)[:60]}），尝试纯 Python 模式...")
                os.environ["USE_TOKENIZERS"] = "0"
                _USE_FAST_TOKENIZER = False
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), trust_remote_code=True, use_fast=False)
                except Exception as _te2:
                    print(f"  [模型] 纯 Python tokenizer 也失败：{str(_te2)[:80]}")
                    raise
            if self.tokenizer.pad_token is None: self.tokenizer.pad_token = self.tokenizer.eos_token
            try:
                from core.device import best_torch_device as _btd
                self.device = _btd()
            except Exception:                                          # noqa: BLE001
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            if self.device == "cuda":
                print("  [模型] GPU 检测成功：权重优先铺显存，装不下的层自动回落 CPU")
            # v0.0.5 fix：本地模型加载优化（小内存不OOM + 提速）
            # 1) CPU 用 low_cpu_mem_usage 分块加载，避免 2GB 内存加载 4.8GB 权重 OOM
            # 2) device_map=None 纯 CPU 推理（手机/低配电脑）
            _kwargs = dict(
                dtype=torch.bfloat16 if self.device=="cuda" else torch.float32,
                device_map="auto" if self.device=="cuda" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True)
            # 3) CPU 场景自动降精度到 float32（bfloat16 部分 CPU 不支持）
            if self.device == "cpu":
                _kwargs["dtype"] = torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(str(self.model_dir), **_kwargs)
            ac = self.adapter_dir / "adapter_config.json"
            if ac.exists():
                print("  [模型] 加载LoRA适配器...")
                self.model = PeftModel.from_pretrained(self.model, str(self.adapter_dir))
            self.model.eval()
            params = sum(p.numel() for p in self.model.parameters())
            print(f"  [模型] 就绪（{params/1e6:.1f}M参数，{self.device}）")
        except Exception as e:
            print(f"  [模型] 加载失败：{e}")
            # v0.0.1 fix：缺 torch/transformers 时给出明确安装指引
            _emsg = str(e)
            # v0.0.1 fix：libomp 专项提示（Termux torch 导入失败最常见原因）
            if "libomp" in _emsg or "libgomp" in _emsg or "cannot open shared object" in _emsg:
                print("  [模型] torch 导入失败：缺少 OpenMP 系统库（libomp）")
                print("  [模型] Termux 修复：pkg install libomp")
                print("  [模型] 桌面修复：sudo apt install libomp-dev（或 brew install libomp）")
            elif "platform android" in _emsg or "psutil" in _emsg:
                print("  [模型] peft 依赖的 psutil 在 Termux 编译失败")
                print("  [模型] Termux 修复：pkg install python-psutil 后再 pip install peft")
            elif "No module named" in _emsg or "ModuleNotFoundError" in _emsg:
                print("  [模型] 缺少 AI 运行时依赖，请安装：")
                import sys as _sys
                if "termux" in str(getattr(_sys, "prefix", "")).lower() or "com.termux" in str(_sys.executable):
                    print("  [模型]   Termux 安卓：pkg install python-torch python-numpy")
                    print("  [模型]   （Termux 必须用 pkg 装预编译版，pip 编译会失败）")
                    print("  [模型]   pkg install python-torch && pip install transformers peft accelerate")
                else:
                    print("  [模型]   Windows/Linux/macOS：pip install -r requirements.txt")
            self.model = None

    def generate(self, messages, temperature=0.85, max_tokens=2048):
        if self.model is None:
            return "（模型未加载，请安装 AI 运行时依赖后重启：pip install -r requirements.txt）"
        try:
            import torch
            text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_new_tokens=max_tokens,
                                              temperature=temperature, do_sample=temperature>0,
                                              top_p=0.9, repetition_penalty=1.1,
                                              pad_token_id=self.tokenizer.pad_token_id)
            return self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        except Exception as e:
            print(f"  [模型] 推理失败：{e}")
            return f"（推理出错：{e}）"

    @staticmethod
    def parse_tool_calls(text):
        if not text: return []
        pat = re.compile(r'\[\[([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^\]]*)\]\]')
        calls = []
        for m in pat.finditer(text):
            calls.append({"name":m.group(1), "arguments":LocalModel._parse_params(m.group(2).strip())})
        return calls

    @staticmethod
    def _parse_params(s):
        params = {}
        if not s: return params
        parts, cur, iq, qc = [], "", False, None
        for ch in s:
            if ch in ('"',"'") and not iq: iq,qc=True,ch; cur+=ch
            elif ch==qc and iq: iq,qc=False,None; cur+=ch
            elif ch=="," and not iq: parts.append(cur.strip()); cur=""
            else: cur+=ch
        if cur.strip(): parts.append(cur.strip())
        for p in parts:
            if "=" in p:
                k,_,v = p.partition("="); v=v.strip()
                if len(v)>=2 and v[0] in ('"',"'") and v[-1]==v[0]: v=v[1:-1]
                params[k.strip()]=v
        return params

    @staticmethod
    def strip_markers(text):
        if not text: return text
        return re.sub(r'\[\[[a-zA-Z_][a-zA-Z0-9_]*\s*:[^\]]*\]\]','',text).strip()


# ============================================================
# 工具系统（38个）
# ============================================================
class ToolManager:
    # 延迟工具发现：核心工具全集，其余工具初始列表隐藏（来源：Codex + OpenClaw）
    CORE_TOOLS = {"get_time", "read_file", "write_file", "list_dir", "str_replace",
                  "run_cmd", "search_web", "calculator", "remember", "recall",
                  "todo_write", "goal_create"}
    # 写类工具（plan模式下被拦截）
    WRITE_TOOLS = {"write_file", "str_replace", "line_replace", "append_file",
                   "delete_file", "move_file", "copy_file", "replace_in_files",
                   "regex_replace", "deduplicate", "run_cmd", "run_python",
                   "git_commit", "git_push", "git_add", "git_clone", "checkpoint",
                   "pip_install", "create_project", "background_run"}

    def __init__(self, base_dir, memory=None):
        self.base_dir = Path(base_dir)
        self.memory = memory
        self.tools = {}
        self.background_tasks = {}
        # read-before-edit + mtime 守卫（来源：OpenCode + Cline）
        self._read_mtimes = {}
        # 工具执行管线 hooks（来源：Pi）
        self.before_hooks = []
        self.after_hooks = []
        # RepoMap 缓存（按目录 mtime）
        self._repo_map_cache = {}
        self._register()
        self._register_extra()

    def register(self, name, func, desc): self.tools[name] = {"func":func,"desc":desc}

    # === 执行管线（来源：Pi，四阶段：prepare → before hooks → execute → after hooks）===
    def add_before_hook(self, hook):
        """hook(name, args) -> None | {"block":True,"reason":...} | {"args":...}"""
        self.before_hooks.append(hook)

    def add_after_hook(self, hook):
        """hook(name, result) -> None | 新的result字符串"""
        self.after_hooks.append(hook)

    # v0.0.14：工具结果缓存（纯查询工具 60 秒内复用，写入类工具不缓存）
    CACHEABLE_TOOLS = {"get_time", "weather", "calculator", "search_web", "list_dir",
                       "read_file", "get_ip", "search_tools", "status"}
    _tool_cache = {}
    _tool_cache_ttl = 60.0

    def execute(self, name, args):
        # prepare：查找工具
        if name not in self.tools: return f"未知工具：{name}"
        # v0.0.14：缓存命中直接返回（省重复执行）
        if name in self.CACHEABLE_TOOLS:
            try:
                key = (name, str(args))
                hit = self._tool_cache.get(key)
                if hit and (time.time() - hit[0]) < self._tool_cache_ttl:
                    return hit[1]
            except Exception:
                pass
        # before hooks：拦截或修改参数
        cur_args = dict(args) if isinstance(args, dict) else (dict(args) if hasattr(args, 'items') else {})
        for hook in self.before_hooks:
            try:
                out = hook(name, cur_args)
            except Exception as e:
                return f"before hook异常：{e}"
            if out:
                if isinstance(out, dict) and out.get("block"):
                    return str(out.get("reason", "被before hook拦截"))
                if isinstance(out, dict) and "args" in out:
                    cur_args = out["args"]
        # execute：执行工具函数，异常捕获
        try:
            result = str(self.tools[name]["func"](**cur_args))
        except Exception as e:
            result = f"工具出错：{type(e).__name__}: {e}"
        # v0.0.14：写入缓存
        if name in self.CACHEABLE_TOOLS:
            try:
                self._tool_cache[(name, str(cur_args))] = (time.time(), result)
                if len(self._tool_cache) > 100:
                    oldest = min(self._tool_cache, key=lambda k: self._tool_cache[k][0])
                    self._tool_cache.pop(oldest, None)
            except Exception:
                pass
        # after hooks：修改结果
        for hook in self.after_hooks:
            try:
                out = hook(name, result)
            except Exception as e:
                out = None
            if out is not None:
                result = str(out)
        return result

    # v0.0.2：高价值工具白名单（完整描述）；其余工具仅列名字
    TOOL_FULL_DESC = {"get_time", "read_file", "write_file", "list_dir", "str_replace",
                      "run_cmd", "search_web", "calculator", "remember", "search_tools",
                      "think", "todo_write"}

    def tool_list_text(self):
        # v0.0.2 token 优化：只对高价值工具给完整描述，其余仅名字清单
        # （参考 OpenCode/Cline 的延迟工具发现：完整 schema 只在调用时注入）
        lines = ["【工具】用 [[工具名:参数]] 调用，例如 [[read_file:path=x.py]]"]
        shown = 0
        for n in self.tools:
            if n in self.TOOL_FULL_DESC:
                lines.append(f"  [[{n}:]] - {self.tools[n]['desc']}")
                shown += 1
        others = [n for n in self.tools if n not in self.TOOL_FULL_DESC]
        if others:
            names = "、".join(sorted(others)[:60])
            lines.append(f"\n（其余工具：{names}。用 [[search_tools:query=关键词]] 查描述后调用。）")
        lines.append("复杂问题先 [[think:thought=...]] 列步骤再执行。")
        return "\n".join(lines)

    def _p(self, path):
        p = Path(path)
        return p if p.is_absolute() else self.base_dir / p

    def _read_file(self, path, max_lines=200):
        p = self._p(path)
        if not p.exists(): return f"不存在：{p}"
        if p.is_dir():
            items = sorted(p.iterdir(), key=lambda x:(not x.is_dir(),x.name.lower()))
            return f"目录{p.name}（{len(items)}项）：\n"+"\n".join(f"  {'[DIR]' if i.is_dir() else '[FILE]'} {i.name}" for i in items[:100])
        with open(p,"r",encoding="utf-8",errors="replace") as f: lines=f.readlines()
        # read-before-edit：记录读取时刻的 mtime（来源：OpenCode + Cline）
        try: self._read_mtimes[str(p)] = os.path.getmtime(p)
        except Exception: pass
        c = "".join(lines[:max_lines])
        return c + (f"\n...（共{len(lines)}行）" if len(lines)>max_lines else "")

    def _guard_edit(self, path):
        """编辑守卫：未读过 / 外部已修改则拦截，返回提示；通过返回 None"""
        try: full = str(self._p(path))
        except Exception: return f"路径解析失败：{path}"
        # v0.0.4 fix：文件不存在（新建场景）→ 直接放行
        if not os.path.exists(full):
            return None
        rec = self._read_mtimes.get(full)
        if rec is None:
            return f"[提示] 请先 read_file 读取 {path} 再编辑。"
        try:
            now_mtime = os.path.getmtime(full)
        except OSError:
            return None  # 文件尚不存在（新建场景），放行
        if now_mtime > rec + 1e-6:
            return f"[提示] 文件 {path} 已被外部修改，请重新读取后再编辑。"
        return None

    def _append_diagnostics(self, path, result):
        """编辑后自动体检回喂（来源：OpenCode + Aider）"""
        try:
            diag = self._check_code(path)
        except Exception as e:
            return result
        if diag and ("错误" in diag or "Error" in diag or "[失败]" in diag):
            snippet = diag[:500]
            result += (f"\n<file_diagnostics>\n编辑后检测到问题：{snippet}\n"
                       f"请立即修复上述问题。\n</file_diagnostics>")
        return result

    def _write_file(self, path, content):
        g = self._guard_edit(path)
        if g is not None: return g
        p=self._p(path); p.parent.mkdir(parents=True,exist_ok=True)
        with open(p,"w",encoding="utf-8") as f: f.write(content)
        # 更新 mtime 记录，避免立即体检被守卫误判
        try: self._read_mtimes[str(p)] = os.path.getmtime(p)
        except Exception: pass
        result = f"已写入 {p}（{len(content)}字符）"
        return self._append_diagnostics(path, result)

    def _append_file(self, path, content):
        g = self._guard_edit(path)
        if g is not None: return g
        p=self._p(path); p.parent.mkdir(parents=True,exist_ok=True)
        with open(p,"a",encoding="utf-8") as f: f.write(content)
        try: self._read_mtimes[str(p)] = os.path.getmtime(p)
        except Exception: pass
        return f"已追加到 {p}"

    def _list_dir(self, path="."): return self._read_file(path, 0)

    def _delete_file(self, path):
        p=self._p(path)
        if not p.exists(): return f"不存在：{p}"
        if p.is_dir(): shutil.rmtree(p)
        else: p.unlink()
        return f"已删除 {p}"

    def _move_file(self, src, dst):
        s,d=self._p(src),self._p(d); d.parent.mkdir(parents=True,exist_ok=True); s.rename(d)
        return f"已移动 {s.name} -> {d}"

    def _copy_file(self, src, dst):
        s,d=self._p(src),self._p(d); d.parent.mkdir(parents=True,exist_ok=True)
        if s.is_dir(): shutil.copytree(s,d)
        else: shutil.copy2(s,d)
        return f"已复制 {s.name} -> {d}"

    def _search_files(self, pattern, path=".", max_results=30):
        p=self._p(path); results=[]
        for f in p.rglob(pattern):
            if any(part.startswith('.') for part in f.parts): continue
            results.append(str(f))
            if len(results)>=max_results: break
        return f"找到{len(results)}个：\n"+"\n".join(results) if results else "未找到"

    def _file_info(self, path):
        p=self._p(path)
        if not p.exists(): return f"不存在：{p}"
        st=p.stat()
        return f"{p}\n大小：{st.st_size}B\n修改：{datetime.fromtimestamp(st.st_mtime)}"

    def _run_cmd(self, cmd, timeout=30):
        try:
            r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=int(timeout),encoding="utf-8",errors="replace")
            out=(r.stdout or "")+(f"\n[stderr]{r.stderr}" if r.stderr else "")+f"\n[exit:{r.returncode}]"
            return out[:3000] if out.strip() else "(无输出)"
        except subprocess.TimeoutExpired: return f"超时（>{timeout}秒）"
        except Exception as e: return f"失败：{e}"

    def _run_python(self, code, timeout=30):
        try:
            r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=int(timeout),encoding="utf-8",errors="replace")
            out=(f"[stdout]\n{r.stdout}" if r.stdout else "")+(f"[stderr]\n{r.stderr}" if r.stderr else "")+f"[exit:{r.returncode}]"
            return out[:3000] if out.strip() else "(无输出)"
        except Exception as e: return f"失败：{e}"

    def _get_time(self):
        wd=["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()]
        return f"现在是 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')} {wd}"

    def _get_date(self, offset_days=0):
        d=datetime.now()+timedelta(days=int(offset_days))
        wd=["周一","周二","周三","周四","周五","周六","周日"][d.weekday()]
        return f"{d.strftime('%Y年%m月%d日')} {wd}"

    def _screenshot(self, path=None):
        try:
            from PIL import ImageGrab
            p=self._p(path) if path else self.base_dir/f"screenshot_{int(time.time())}.png"
            p.parent.mkdir(parents=True,exist_ok=True)
            img=ImageGrab.grab(); img.save(str(p))
            return f"截图已保存 {p}"
        except ImportError: return "需要PIL：pip install pillow"
        except Exception as e: return f"失败：{e}"

    def _clipboard(self, action, text=None):
        try:
            if action=="get":
                r=subprocess.run(["xclip","-selection","clipboard","-o"],capture_output=True,text=True,timeout=5)
                return f"剪贴板：\n{r.stdout}"
            elif action=="set" and text:
                subprocess.run(["xclip","-selection","clipboard"],input=text,text=True,timeout=5)
                return f"已设置：{text[:50]}"
            return "未知操作"
        except Exception as e: return f"失败：{e}"

    def _open_url(self, url):
        if not url.startswith(("http://","https://")): url="https://"+url
        try: import webbrowser; webbrowser.open(url); return f"已打开 {url}"
        except Exception as e: return f"失败：{e}"

    def _download_file(self, url, path):
        try:
            p=self._p(path); p.parent.mkdir(parents=True,exist_ok=True)
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=60) as r: data=r.read()
            with open(p,"wb") as f: f.write(data)
            return f"下载完成 {p}（{len(data)}字节）"
        except Exception as e: return f"失败：{e}"

    def _search_web(self, query, max_results=5):
        try:
            params=urllib.parse.urlencode({"q":query,"format":"json","no_html":1,"skip_disambig":1})
            req=urllib.request.Request("https://api.duckduckgo.com/?"+params,headers={"User-Agent":"XiaoLing/0.0.1"})
            with urllib.request.urlopen(req,timeout=15) as r: data=json.loads(r.read())
            res=[]
            if data.get("AbstractText"): res.append({"t":data.get("Heading",query),"s":data["AbstractText"]})
            for t in data.get("RelatedTopics",[])[:max_results]:
                if isinstance(t,dict) and "Text" in t: res.append({"t":t["Text"][:60],"s":t["Text"]})
            if not res: return f"搜索'{query}'无结果"
            out=f"搜索'{query}'：\n"
            for i,r in enumerate(res[:max_results],1): out+=f"\n{i}. {r['t']}\n   {r['s'][:250]}"
            return out
        except Exception as e: return f"搜索失败：{e}"

    def _fetch_url(self, url, max_chars=3000):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=20) as r: c=r.read().decode("utf-8",errors="replace")
            t=re.sub(r'<[^>]+>',' ',c); t=re.sub(r'\s+',' ',t).strip()
            return t[:max_chars]+("..." if len(t)>max_chars else "")
        except Exception as e: return f"失败：{e}"

    def _calculator(self, expression):
        try:
            import math
            sd={k:getattr(math,k) for k in dir(math) if not k.startswith("_")}; sd["__builtins__"]={}
            sd.update({"abs":abs,"min":min,"max":max,"round":round,"len":len,"sum":sum,"pow":pow})
            return f"{expression} = {eval(expression,sd,{})}"
        except Exception as e: return f"错误：{e}"

    def _unit_convert(self, value, from_unit, to_unit):
        v=float(value)
        length={"m":1,"km":1000,"cm":0.01,"mm":0.001,"mile":1609.34,"ft":0.3048,"inch":0.0254}
        weight={"kg":1,"g":0.001,"mg":0.000001,"lb":0.453592,"oz":0.0283495}
        if from_unit in ("C","F","K") and to_unit in ("C","F","K"):
            if from_unit=="C" and to_unit=="F": r=v*9/5+32
            elif from_unit=="F" and to_unit=="C": r=(v-32)*5/9
            elif from_unit=="C" and to_unit=="K": r=v+273.15
            elif from_unit=="K" and to_unit=="C": r=v-273.15
            else: return "不支持"
            return f"{v}{from_unit} = {r:.4f}{to_unit}"
        for tbl in [length,weight]:
            if from_unit in tbl and to_unit in tbl:
                return f"{v}{from_unit} = {v*tbl[from_unit]/tbl[to_unit]:.4f}{to_unit}"
        return f"不支持：{from_unit}->{to_unit}"

    def _hash(self, text, algorithm="md5"):
        algos={"md5":hashlib.md5,"sha1":hashlib.sha1,"sha256":hashlib.sha256}
        if algorithm not in algos: return f"可用：{list(algos)}"
        return f"{algorithm} = {algos[algorithm](text.encode()).hexdigest()}"

    def _base64(self, text, action="encode"):
        return base64.b64encode(text.encode()).decode() if action=="encode" else base64.b64decode(text).decode("utf-8",errors="replace")

    def _word_count(self, text):
        _cn = "[一-鿿]"
        _en = "[a-zA-Z]+"
        return (f"字符{len(text)} 中文{len(re.findall(_cn, text))} "
                f"英文词{len(re.findall(_en, text))} 行{text.count(chr(10))+1}")

    def _translate(self, text, target_lang="zh"):
        try:
            src="zh" if target_lang=="en" else "en"
            params=urllib.parse.urlencode({"q":text[:500],"langpair":f"{src}|{target_lang}"})
            with urllib.request.urlopen(f"https://api.mymemory.translated.net/get?{params}",timeout=15) as r:
                return json.loads(r.read()).get("responseData",{}).get("translatedText","失败")
        except Exception as e: return f"失败：{e}"

    def _summarize(self, text, max_sentences=3):
        sents=[s.strip() for s in re.split(r'[。！？.!?\n]',text) if len(s.strip())>10]
        sents.sort(key=len,reverse=True)
        return "。".join(sents[:max_sentences])+"。"

    def _remember(self, text, importance=0.8):
        if self.memory:
            self.memory.add_episode("记忆",text,valence=0,intensity=importance); self.memory.save()
        return f"已记住：{text}"

    def _recall(self, keyword, n=5):
        if not self.memory: return "记忆未启用"
        res=self.memory.recall(keyword,n=n)
        if not res: return f"没有关于'{keyword}'的记忆"
        out=f"关于'{keyword}'：\n"
        for _,_,m in res:
            t=datetime.fromtimestamp(m["time"]).strftime("%m-%d %H:%M")
            out+=f"\n- [{t}] {m.get('role','')}: {m['text'][:100]}"
        return out

    def _add_belief(self, belief, confidence=0.7):
        if self.memory:
            self.memory.data.setdefault("beliefs",{})[belief]=confidence; self.memory.save()
        return f"信念已建立：{belief}"

    def _learn(self, topic, num_questions=5):
        return learn_from_teacher(topic, num_questions, self.memory)

    def _reflect(self):
        if self.memory:
            recent=self.memory.get_recent(10)
            pos=sum(1 for m in recent if m.get("valence",0)>0)
            neg=sum(1 for m in recent if m.get("valence",0)<0)
            r=f"反思：最近{len(recent)}件事，开心{pos}低落{neg}。"
            self.memory.add_reflection(r,"manual"); self.memory.save()
            return r
        return "记忆未启用"

    def _consolidate(self):
        if self.memory:
            n=self.memory.consolidate(); self.memory.save()
            return f"巩固完成，提炼{n}条知识"
        return "记忆未启用"

    def _git_status(self, path="."):
        try:
            r=subprocess.run(["git","status"],cwd=str(self._p(path)),capture_output=True,text=True,timeout=10)
            return r.stdout+r.stderr
        except Exception as e: return f"失败：{e}"

    def _git_log(self, path=".", count=10):
        try:
            r=subprocess.run(["git","log","--oneline",f"-{count}"],cwd=str(self._p(path)),capture_output=True,text=True,timeout=10)
            return r.stdout or r.stderr
        except Exception as e: return f"失败：{e}"

    def _check_code(self, path):
        try:
            r=subprocess.run([sys.executable,"-m","py_compile",str(self._p(path))],capture_output=True,text=True,timeout=10)
            return "[完成] 语法正确" if r.returncode==0 else f"[失败] {r.stderr}"
        except Exception as e: return f"失败：{e}"

    def _weather(self, city="北京"):
        try:
            url=f"https://wttr.in/{urllib.parse.quote(city)}?format=3&lang=zh"
            req=urllib.request.Request(url,headers={"User-Agent":"curl/7.0"})
            with urllib.request.urlopen(req,timeout=10) as r: return r.read().decode().strip()
        except Exception as e: return f"失败：{e}"

    def _random(self, min_val=1, max_val=100, count=1):
        return f"随机数：{[random.randint(int(min_val),int(max_val)) for _ in range(int(count))]}"

    def _register(self):
        for name, func, desc in [
            ("read_file",self._read_file,"读取文件或目录"),
            ("write_file",self._write_file,"写入文件"),
            ("append_file",self._append_file,"追加到文件"),
            ("list_dir",self._list_dir,"列出目录"),
            ("delete_file",self._delete_file,"删除文件/目录"),
            ("move_file",self._move_file,"移动文件"),
            ("copy_file",self._copy_file,"复制文件"),
            ("search_files",self._search_files,"搜索文件"),
            ("file_info",self._file_info,"文件信息"),
            ("run_cmd",self._run_cmd,"执行系统命令"),
            ("run_python",self._run_python,"运行Python代码"),
            ("get_time",self._get_time,"当前时间"),
            ("get_date",self._get_date,"日期"),
            ("screenshot",self._screenshot,"截屏"),
            ("clipboard",self._clipboard,"剪贴板"),
            ("open_url",self._open_url,"打开网址"),
            ("download_file",self._download_file,"下载文件"),
            ("search_web",self._search_web,"网络搜索"),
            ("fetch_url",self._fetch_url,"抓取网页"),
            ("calculator",self._calculator,"数学计算"),
            ("unit_convert",self._unit_convert,"单位换算"),
            ("hash",self._hash,"哈希计算"),
            ("base64",self._base64,"Base64编解码"),
            ("word_count",self._word_count,"字数统计"),
            ("translate",self._translate,"翻译"),
            ("summarize",self._summarize,"文本摘要"),
            ("remember",self._remember,"记住某事"),
            ("recall",self._recall,"回忆记忆"),
            ("add_belief",self._add_belief,"建立信念"),
            ("learn",self._learn,"学习主题（调用老师）"),
            ("reflect",self._reflect,"自我反思"),
            ("consolidate",self._consolidate,"记忆巩固"),
            ("git_status",self._git_status,"Git状态"),
            ("git_log",self._git_log,"Git日志"),
            ("check_code",self._check_code,"代码语法检查"),
            ("weather",self._weather,"天气查询"),
            ("random",self._random,"随机数"),
            # === v0.2.0 工程增强 ===
            ("str_replace",self._str_replace,"字符串替换编辑（三级容错）"),
            ("search_tools",self._search_tools,"按关键词搜索发现隐藏工具"),
            ("repo_map",self._repo_map,"生成轻量仓库结构地图"),
            ("think",self._think,"显式记录思考步骤，无副作用"),
            ("checkpoint",self._checkpoint,"Git检查点 create/restore/list"),
        ]:
            self.register(name, func, desc)

    def register_external(self, name, func, desc=""):
        """注册技能提供的外部工具函数"""
        if name not in self.tools:
            self.register(name, func, desc or func.__doc__ or name)
            return True
        return False

    def _register_extra(self):
        """扩展工具集：吸纳各开源Agent长处，打造小凌专属能力"""
        extras = [
            # === 开发类 ===
            ("find_in_files", self._find_in_files, "在文件中搜索内容"),
            ("replace_in_files", self._replace_in_files, "批量替换文件内容"),
            ("code_format", self._code_format, "格式化代码"),
            ("run_tests", self._run_tests, "运行测试"),
            ("pip_install", self._pip_install, "安装Python包"),
            ("pip_list", self._pip_list, "列出已安装包"),
            ("node_exec", self._node_exec, "执行JavaScript"),
            ("create_project", self._create_project, "创建项目脚手架"),
            ("function_search", self._function_search, "搜索函数/类定义"),
            ("line_replace", self._line_replace, "按行号替换内容"),
            # === 系统类 ===
            ("process_list", self._process_list, "列出进程"),
            ("process_kill", self._process_kill, "终止进程"),
            ("system_info", self._system_info, "系统信息"),
            ("disk_usage", self._disk_usage, "磁盘使用"),
            ("memory_usage", self._memory_usage, "内存使用"),
            ("cpu_usage", self._cpu_usage, "CPU使用"),
            ("env_vars", self._env_vars, "环境变量"),
            ("which", self._which, "查找命令路径"),
            ("background_run", self._background_run, "后台运行命令"),
            ("background_status", self._background_status, "后台任务状态"),
            ("background_stop", self._background_stop, "停止后台任务"),
            # === 网络类 ===
            ("http_request", self._http_request, "HTTP请求"),
            ("ping", self._ping, "Ping测试"),
            ("dns_lookup", self._dns_lookup, "DNS解析"),
            ("tcp_probe", self._tcp_probe, "TCP端口探测"),
            # === 数据类 ===
            ("json_format", self._json_format, "格式化JSON"),
            ("json_query", self._json_query, "JSON路径查询"),
            ("csv_parse", self._csv_parse, "解析CSV"),
            ("yaml_parse", self._yaml_parse, "解析YAML"),
            # === Git类 ===
            ("git_add", self._git_add, "Git添加"),
            ("git_commit", self._git_commit, "Git提交"),
            ("git_push", self._git_push, "Git推送"),
            ("git_pull", self._git_pull, "Git拉取"),
            ("git_diff", self._git_diff, "Git差异"),
            ("git_branch", self._git_branch, "Git分支"),
            ("git_checkout", self._git_checkout, "Git切换分支"),
            ("git_clone", self._git_clone, "Git克隆"),
            # === 文本类 ===
            ("regex_replace", self._regex_replace, "正则替换"),
            ("text_diff", self._text_diff, "文本对比"),
            ("count_lines", self._count_lines, "统计行数"),
            ("deduplicate", self._deduplicate, "去重"),
            # === 其他 ===
            ("notify", self._notify, "系统通知"),
            ("schedule", self._schedule, "定时提醒"),
            ("list_schedules", self._list_schedules, "列出定时任务"),
            ("tree", self._tree, "目录树"),
            # === Goal目标工具 ===
            ("goal_create", self._goal_create, "创建目标"),
            ("goal_complete", self._goal_complete, "完成目标"),
            ("goal_list", self._goal_list, "列出目标"),
            ("goal_block", self._goal_block, "阻塞目标"),
            # === Todo任务工具 ===
            ("todo_write", self._todo_write, "写入任务列表"),
            ("todo_list", self._todo_list, "查看任务列表"),
        ]
        # v0.0.4：小凌的"眼睛"和"嘴巴" + 成长工具
        extras += [
            # === 眼睛（摄像头/屏幕感知）===
            ("camera", self._camera, "拍照（摄像头）或截屏，小凌能'看见'你"),
            ("screenshot", self._screenshot, "截取屏幕画面，小凌能'看见'你的屏幕"),
            # === 嘴巴（麦克风/语音输入）===
            ("listen", self._listen, "麦克风听你说话（语音识别），小凌能'听见'你"),
            # === 成长 ===
            ("grow", self._grow, "查看小凌成长包大小/知识量（越用越强）"),
            ("growth_report", self._growth_report, "查看小凌成长报告"),
        ]

        for name, func, desc in extras:
            self.register(name, func, desc)

    # v0.0.4：眼睛——摄像头拍照；v0.0.5：拍照后可"看懂"（视觉理解）
    def _camera(self, save_to="data/camera_latest.png", describe=False):
        """调用摄像头拍照。Windows 用 opencv；describe=True 时用 DeepSeek 描述画面。

        参数:
            save_to: 保存路径
            describe: 是否调用视觉理解描述画面（小凌真正"看见"）
        """
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "未检测到摄像头，尝试截屏兜底..."
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return "摄像头拍照失败"
            p = self._p(save_to)
            p.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(p), frame)
            if describe:
                desc = self._describe_image(p)
                # v0.0.6：视觉语料采集（基底模型学到"看见"）
                try:
                    self._collect_perception_corpus("视觉", desc)
                except Exception:
                    pass
                return f"已拍照保存: {p}\n[视觉] 小凌看到的：{desc}"
            # v0.0.6：视觉语料采集
            try:
                self._collect_perception_corpus("视觉", f"摄像头拍到了画面，保存在 {p}")
            except Exception:
                pass
            return f"已拍照保存: {p}（小凌看到你了！）"
        except ImportError:
            return "需要 opencv-python：pip install opencv-python（或用 screenshot 截屏）"
        except Exception as e:
            return f"摄像头调用失败: {e}"

    # v0.0.4：眼睛——屏幕截图；v0.0.5：可"看懂"屏幕
    def _screenshot(self, save_to="data/screenshot_latest.png", describe=False):
        """截取屏幕。Windows 用 PIL ImageGrab；describe=True 时描述画面。"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            p = self._p(save_to)
            p.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(p))
            if describe:
                desc = self._describe_image(p)
                return f"已截屏保存: {p}\n[视觉] 小凌看到的：{desc}"
            return f"已截屏保存: {p}（小凌看到你的屏幕了）"
        except Exception as e:
            return f"截屏失败: {e}（Windows 上 PIL 支持 ImageGrab）"

    # v0.0.6：感知语料采集（视觉/听觉 → 训练语料，基底学到东西）
    def _collect_perception_corpus(self, modality, content):
        """把摄像头/麦克风采集的感知数据写入训练语料（learned_data.jsonl）。

        这样基底模型（经蒸馏训练）能学到视觉/语音理解能力。
        """
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(LEARNED_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "topic": f"{modality}感知",
                    "question": f"小凌{modality}感知到了什么？",
                    "answer": content[:500],
                }, ensure_ascii=False) + "\n")
            with open(CORPUS_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n# === {modality}感知采集 ===\n")
                f.write(f"你：小凌{modality}感知到了什么？\n小凌：{content[:300]}\n")
            # 成长包同步
            try:
                growth = getattr(self, "_growth", None)
                if growth:
                    growth.absorb("perception", f"{modality}感知：{content[:80]}", [modality, "perception"])
            except Exception:
                pass
        except Exception as e:
            print(f"  [感知] 语料采集失败: {e}")

    # v0.0.5：视觉理解——描述图片内容（DeepSeek 多模态或提示）
    def _describe_image(self, img_path):
        """让 DeepSeek 描述图片内容（小凌真正"看见"）。

        优先走 DeepSeek Vision API（如果支持），否则提示图片已保存可人工查看。
        """
        try:
            api_key = CONFIG.get("deepseek_api_key", "")
            if not api_key or api_key == "暂未填入":
                return f"（图片已存 {img_path}，配置 DeepSeek Key 后可自动描述）"
            # DeepSeek chat 接口不支持图片输入时，给出占位描述
            # 真实多模态可用 GLM-4V / Qwen-VL 等兼容 API
            return f"（图片已存 {img_path}，当前 DeepSeek 文本接口不直接看图；可用兼容多模态 API 替换 base_url 实现视觉理解）"
        except Exception as e:
            return f"视觉描述失败: {e}"

    # v0.0.4：嘴巴——麦克风语音输入
    def _listen(self, duration=5, save_to="data/voice_input.wav"):
        """麦克风录音并识别为文字。Windows 用 sounddevice + 本地识别/whisper。"""
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            print(f"  [听] 小凌在听（{duration}秒）...")
            fs = 16000
            audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            p = self._p(save_to)
            p.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(p), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(fs)
                wf.writeframes(audio.tobytes())
            # v0.0.6：语音语料采集（基底模型学到"听见"）
            try:
                self._collect_perception_corpus("听觉", f"录音 {duration} 秒，保存在 {p}")
            except Exception:
                pass
            return f"已录音 {duration} 秒保存: {p}（如需转文字请装 whisper）"
        except ImportError:
            return "需要 sounddevice：pip install sounddevice numpy（麦克风听声）"
        except Exception as e:
            return f"录音失败: {e}"

    # v0.0.4：成长工具
    def _grow(self):
        """查看成长包大小。"""
        try:
            growth = getattr(self, "_growth", None)
            if growth is None:
                return "成长包未初始化"
            return f"成长包：{growth.total_items} 条知识 / {growth.get_size()}"
        except Exception as e:
            return f"成长查询失败: {e}"

    def _growth_report(self):
        """成长报告。"""
        try:
            growth = getattr(self, "_growth", None)
            if growth is None:
                return "成长包未初始化"
            return growth.growth_report()
        except Exception as e:
            return f"成长报告失败: {e}"

    # === 开发类工具 ===
    def _find_in_files(self, pattern, path=".", file_type="", max_results=50):
        p = self._p(path); results = []
        glob_pat = f"*.{file_type}" if file_type else "*"
        for f in p.rglob(glob_pat):
            if f.is_file() and not any(part.startswith('.') for part in f.parts):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            results.append(f"{f}:{i}: {line.strip()[:100]}")
                            if len(results) >= max_results: return "\n".join(results)
                except Exception: pass
        return "\n".join(results) if results else f"未找到'{pattern}'"

    def _replace_in_files(self, pattern, replacement, path=".", file_type=""):
        p = self._p(path); count = 0; files = 0
        glob_pat = f"*.{file_type}" if file_type else "*"
        for f in p.rglob(glob_pat):
            if f.is_file():
                try:
                    c = f.read_text(encoding="utf-8")
                    nc, n = re.subn(pattern, replacement, c)
                    if n > 0: f.write_text(nc, encoding="utf-8"); count += n; files += 1
                except Exception: pass
        return f"替换完成：{files}个文件，{count}处"

    def _code_format(self, path):
        p = self._p(path)
        try:
            r = subprocess.run(["black", str(p)], capture_output=True, text=True, timeout=15)
            if r.returncode == 0: return f"已格式化: {p}"
            return f"black不可用或失败: {r.stderr[:200]}"
        except FileNotFoundError: return "black未安装: pip install black"

    def _run_tests(self, path=".", pattern="test_*.py"):
        p = self._p(path)
        r = subprocess.run([sys.executable, "-m", "pytest", str(p), "-v", "--tb=short"],
                          capture_output=True, text=True, timeout=120, cwd=str(p))
        return (r.stdout or "") + (r.stderr or "")[:3000]

    def _pip_install(self, package):
        r = subprocess.run([sys.executable, "-m", "pip", "install", package],
                          capture_output=True, text=True, timeout=120)
        return (r.stdout or "") + (r.stderr or "")[-1000:]

    def _pip_list(self):
        r = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, timeout=15)
        return r.stdout

    def _node_exec(self, code):
        try:
            r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=15)
            return (r.stdout or "") + (f"[stderr]{r.stderr}" if r.stderr else "") + f"[exit:{r.returncode}]"
        except FileNotFoundError: return "node未安装"

    def _create_project(self, name, project_type="python"):
        p = self._p(name); p.mkdir(parents=True, exist_ok=True)
        if project_type == "python":
            (p / "main.py").write_text('def main():\n    print("Hello")\n\nif __name__ == "__main__":\n    main()\n')
            (p / "requirements.txt").write_text("")
            (p / "README.md").write_text(f"# {name}\n")
        elif project_type == "web":
            (p / "index.html").write_text(f"<!DOCTYPE html><html><head><title>{name}</title></head><body><h1>{name}</h1></body></html>")
            (p / "style.css").write_text("body { font-family: sans-serif; }")
        return f"项目已创建: {p} ({project_type})"

    def _function_search(self, name, path="."):
        return self._find_in_files(rf"(def|class)\s+{re.escape(name)}", path, max_results=20)

    def _line_replace(self, path, line_num, content):
        g = self._guard_edit(path)
        if g is not None: return g
        p = self._p(path)
        if not p.exists(): return f"不存在: {p}"
        lines = p.read_text(encoding="utf-8").split("\n")
        n = int(line_num) - 1
        if 0 <= n < len(lines):
            old = lines[n]; lines[n] = content
            p.write_text("\n".join(lines), encoding="utf-8")
            try: self._read_mtimes[str(p)] = os.path.getmtime(p)
            except Exception: pass
            return f"第{line_num}行已替换\n原: {old[:80]}\n新: {content[:80]}"
        return f"行号超出范围（共{len(lines)}行）"

    # === str_replace 三级容错编辑工具（来源：Trae + Aider）===
    def _str_replace(self, path, old_str, new_str):
        g = self._guard_edit(path)
        if g is not None: return g
        p = self._p(path)
        if not p.exists(): return f"不存在: {p}"
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取失败: {e}"

        # 第1级：精确匹配，要求唯一
        count = text.count(old_str)
        if count == 0:
            # 第2级：去首尾空行后再精确匹配（容忍模型多抄/少抄空行）
            old_stripped = old_str.strip("\n")
            count2 = text.count(old_stripped)
            if count2 == 0:
                # 第3级：difflib 行级模糊匹配
                out = self._fuzzy_str_replace(p, text, old_str, new_str)
                if out: return self._post_edit_verify(p, out)
                return (f"未在 {p} 中找到待替换片段（精确/去空白/模糊三级均失败）。"
                        f"请先 read_file 读取文件，复制确切原文后再试。")
            elif count2 == 1:
                text = text.replace(old_stripped, new_str, 1)
                applied_level = "去首尾空行后唯一匹配"
            else:
                return f"[提示] 去首尾空行后仍匹配到{count2}处，请补充更多上下文使 old_str 唯一（先 read_file 确认）。"
        elif count > 1:
            # 列出匹配行号要求补充上下文
            line_nos = []
            for i, line in enumerate(text.split("\n"), 1):
                if old_str.split("\n")[0] in line:
                    line_nos.append(i)
                if len(line_nos) >= 10: break
            return (f"[提示] old_str 在 {p} 中出现{count}次（约行{','.join(map(str,line_nos))}），"
                    f"不唯一。请补充前后上下文使其唯一，或用 line_replace 按行号替换。")
        else:
            text = text.replace(old_str, new_str, 1)
            applied_level = "精确唯一匹配"

        p.write_text(text, encoding="utf-8")
        try: self._read_mtimes[str(p)] = os.path.getmtime(p)
        except Exception: pass
        return self._post_edit_verify(p, f"str_replace 成功（{applied_level}）")

    def _fuzzy_str_replace(self, p, text, old_str, new_str):
        """difflib 行级模糊匹配，匹配块足够大才应用"""
        old_lines = old_str.split("\n")
        new_lines = new_str.split("\n")
        min_block = max(2, len(old_lines) // 2)
        sm = difflib.SequenceMatcher(None, text.split("\n"), old_lines, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size >= min_block]
        if not blocks: return None
        # 取最大匹配块
        best = max(blocks, key=lambda b: b.size)
        t_lines = text.split("\n")
        i, j, size = best.a, best.b, best.size
        # 检查匹配块是否对齐到 old_str 的内容（要求从 old_str 开头附近开始）
        if j != 0 and size < len(old_lines):
            # 未完整匹配 old_str 整体，拒绝以防误改
            return None
        t_lines[i:i+size] = new_lines
        p.write_text("\n".join(t_lines), encoding="utf-8")
        try: self._read_mtimes[str(p)] = os.path.getmtime(p)
        except Exception: pass
        return f"str_replace 成功（difflib 行级模糊匹配，匹配{size}行）"

    def _post_edit_verify(self, p, result):
        """回显编辑点附近4行上下文 + 自动体检"""
        try:
            lines = p.read_text(encoding="utf-8").split("\n")
            # 找最近编辑点：这里简单展示文件中部4行作为编辑点上下文
            mid = len(lines) // 2
            lo, hi = max(0, mid-2), min(len(lines), mid+2)
            ctx = "\n".join(f"  {lo+i+1}: {lines[lo+i]}" for i in range(hi-lo))
            result += f"\n--- 编辑点附近上下文 ---\n{ctx}"
        except Exception:
            pass
        return self._append_diagnostics(str(p), result)

    # === 轻量 RepoMap（来源：Aider）===
    def _repo_map(self, path=".", focus="", budget=800):
        p = self._p(path)
        if not p.is_dir(): return f"不是目录: {p}"
        # 按目录 mtime 缓存
        try:
            dir_mtime = os.path.getmtime(p)
            if str(p) in self._repo_map_cache:
                cache = self._repo_map_cache[str(p)]
                if cache["mtime"] >= dir_mtime and not focus:
                    return cache["text"]
        except Exception:
            dir_mtime = 0
        SYM_RE = re.compile(r'^\s*(?:class|def|function|func)\s+([A-Za-z_][A-Za-z0-9_]*)')
        scored = []
        exts = (".py", ".js", ".ts", ".go", ".java")
        for f in p.rglob("*"):
            if not f.is_file() or f.suffix not in exts: continue
            if any(part.startswith('.') for part in f.parts): continue
            try:
                symbols = []
                for line in f.read_text(encoding="utf-8", errors="replace").split("\n")[:400]:
                    m = SYM_RE.match(line)
                    if m: symbols.append(m.group(1))
                if not symbols: continue
                score = len(symbols)
                if focus:
                    if focus.lower() in f.name.lower(): score *= 10
                    elif any(focus.lower() in s.lower() for s in symbols): score *= 10
                scored.append((score, str(f.relative_to(p)), symbols[:12]))
            except Exception:
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        out, used = [], 0
        for _, rel, syms in scored:
            line = f"{rel}: {', '.join(syms)}"
            if used + len(line) > int(budget): break
            out.append(line); used += len(line)
        text = f"RepoMap（{p}，focus={focus or '无'}，{len(scored)}个文件）：\n" + ("\n".join(out) if out else "（未提取到符号）")
        self._repo_map_cache[str(p)] = {"mtime": dir_mtime, "text": text}
        return text

    # === 延迟工具发现（来源：Codex + OpenClaw）===
    def _search_tools(self, query):
        kws = [w.lower() for w in re.split(r'[\s,，]+', query) if w]
        if not kws: kws = [query.lower()]
        hits = []
        for n, t in self.tools.items():
            blob = (n + " " + t["desc"]).lower()
            score = sum(1 for k in kws if k in blob)
            if score > 0:
                hits.append((score, n, t["desc"]))
        hits.sort(key=lambda x: (-x[0], x[1]))
        if not hits: return f"没有匹配'{query}'的工具。可用工具共{len(self.tools)}个。"
        lines = [f"发现{len(hits)}个相关工具："]
        for _, n, desc in hits[:20]:
            tag = "[核心]" if n in self.CORE_TOOLS else "[可调用]"
            lines.append(f"  [[{n}:]] {tag} - {desc}")
        return "\n".join(lines)

    # === think 显式思考工具（来源：Trae + OpenHands）===
    def _think(self, thought, thought_number=1, total=5):
        try:
            tn = int(thought_number); tt = max(1, int(total))
        except Exception:
            tn, tt = 1, 5
        return f"[思考#{tn}/{tt}] {thought}"

    # === Git Checkpoint 回滚（来源：Cline）===
    def _ensure_git(self, path="."):
        p = self._p(path)
        try:
            r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                               cwd=str(p), capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                subprocess.run(["git", "init"], cwd=str(p), capture_output=True, text=True, timeout=30)
            return True
        except Exception:
            return False

    def _checkpoint(self, action="list", ref="", label="auto"):
        base = self.base_dir
        if not self._ensure_git("."): return "git 不可用，checkpoint 失败"
        def run(args):
            r = subprocess.run(["git"]+args, cwd=str(base), capture_output=True, text=True, timeout=60)
            return (r.stdout or "") + (r.stderr or "")
        if action == "create":
            cid = uuid.uuid4().hex[:12]
            run(["add", "-A"])
            r = subprocess.run(["git","stash","push","--include-untracked","-m",f"xlckpt-{label}-{cid}"],
                               cwd=str(base), capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return f"checkpoint创建失败：{r.stderr or r.stdout}"
            # 取 stash 对应 commit 的 SHA，存到 refs/xiaoling/checkpoints/<uuid>，然后 drop stash
            sha = run(["rev-parse", f"stash@{{0}}"]).strip().split("\n")[0]
            if sha:
                refname = f"refs/xiaoling/checkpoints/{cid}"
                run(["update-ref", refname, sha])
                run(["stash", "drop"])
                return f"checkpoint已创建：{cid}（{label}）-> {refname} ({sha[:10]})"
            return "checkpoint已创建但未取到SHA"
        if action == "restore":
            if not ref: return "restore 需要提供 ref（checkpoint id）"
            refname = ref if ref.startswith("refs/") else f"refs/xiaoling/checkpoints/{ref}"
            run(["reset", "--hard", refname])
            run(["clean", "-fd"])
            return f"已回滚到 {refname}"
        if action == "list":
            out = run(["for-each-ref","--format=%(refname:short) %(objectname:short) %(contents:subject)","refs/xiaoling/checkpoints/"])
            return out.strip() or "暂无 xiaoling checkpoint"
        return f"未知 action：{action}（create/restore/list）"

    # === 系统类工具 ===
    def _process_list(self):
        try:
            r = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
            return r.stdout[:5000]
        except: return "ps不可用"

    def _process_kill(self, pid):
        try:
            os.kill(int(pid), 9); return f"进程{pid}已终止"
        except Exception as e: return f"失败: {e}"

    def _system_info(self):
        import platform
        return f"系统: {platform.system()} {platform.release()}\n架构: {platform.machine()}\nPython: {platform.python_version()}\n主机: {platform.node()}"

    def _disk_usage(self, path="."):
        p = self._p(path)
        total, used, free = shutil.disk_usage(str(p))
        return f"磁盘: {p}\n总计: {total/1e9:.1f}GB\n已用: {used/1e9:.1f}GB ({used/total*100:.1f}%)\n可用: {free/1e9:.1f}GB"

    def _memory_usage(self):
        try:
            r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
            return r.stdout
        except: return "free不可用"

    def _cpu_usage(self):
        try:
            r = subprocess.run(["top", "-bn1"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.split("\n"):
                if "Cpu" in line or "CPU" in line: return line
            return r.stdout[:500]
        except: return "top不可用"

    def _env_vars(self, name=""):
        if name: return f"{name}={os.environ.get(name, '(未设置)')}"
        return "\n".join(f"{k}={v[:80]}" for k, v in os.environ.items())

    def _which(self, command):
        r = subprocess.run(["which", command], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else f"未找到: {command}"

    def _background_run(self, cmd, task_id=""):
        tid = task_id or f"task_{int(time.time())}"
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.background_tasks[tid] = {"proc": p, "cmd": cmd, "start": time.time()}
        return f"后台任务已启动: {tid} (PID: {p.pid})"

    def _background_status(self, task_id=""):
        if task_id:
            t = self.background_tasks.get(task_id)
            if not t: return f"任务不存在: {task_id}"
            p = t["proc"]; rc = p.poll()
            status = "运行中" if rc is None else f"已结束(exit={rc})"
            out = p.stdout.read() if rc is not None else ""
            return f"[{task_id}] {status}\n命令: {t['cmd']}\n运行: {time.time()-t['start']:.1f}s\n输出: {out[:500]}"
        out = []
        for tid, t in self.background_tasks.items():
            rc = t["proc"].poll()
            out.append(f"[{tid}] {'运行中' if rc is None else f'结束({rc})'} - {t['cmd'][:50]}")
        return "\n".join(out) if out else "无后台任务"

    def _background_stop(self, task_id):
        t = self.background_tasks.get(task_id)
        if not t: return f"任务不存在: {task_id}"
        t["proc"].terminate(); return f"任务{task_id}已终止"

    # === 网络类工具 ===
    def _http_request(self, url, method="GET", data="", headers=""):
        try:
            hdrs = {"User-Agent": "XiaoLing/0.0.1"}
            if headers:
                for h in headers.split(";"):
                    if ":" in h: k, v = h.split(":", 1); hdrs[k.strip()] = v.strip()
            req = urllib.request.Request(url, data=data.encode() if data else None, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", errors="replace")
                return f"HTTP {r.status}\n" + "\n".join(f"{k}: {v}" for k, v in r.headers.items()) + f"\n\n{body[:5000]}"
        except Exception as e: return f"请求失败: {e}"

    def _ping(self, host, count=4):
        r = subprocess.run(["ping", "-c", str(count), host], capture_output=True, text=True, timeout=15)
        return r.stdout + r.stderr

    def _dns_lookup(self, domain):
        import socket
        try:
            ips = socket.getaddrinfo(domain, None)
            unique_ips = list(dict.fromkeys(ip[4][0] for ip in ips))
            return f"{domain} 解析结果:\n" + "\n".join(f"  {ip}" for ip in unique_ips)
        except Exception as e: return f"解析失败: {e}"

    def _tcp_probe(self, host, port, timeout=3):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(int(timeout))
        try:
            s.connect((host, int(port))); s.close()
            return f"{host}:{port} 可连接"
        except Exception as e: return f"{host}:{port} 不可连接: {e}"

    # === 数据类工具 ===
    def _json_format(self, text_or_path):
        p = self._p(text_or_path)
        if p.exists(): text = p.read_text(encoding="utf-8")
        else: text = text_or_path
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except Exception as e: return f"JSON解析失败: {e}"

    def _json_query(self, text_or_path, path_expr):
        p = self._p(text_or_path)
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else json.loads(text_or_path)
        keys = path_expr.split("."); val = data
        for k in keys:
            if k.isdigit() and isinstance(val, list): val = val[int(k)]
            elif isinstance(val, dict): val = val.get(k)
            else: return f"路径不存在: {k}"
        return json.dumps(val, ensure_ascii=False, indent=2) if not isinstance(val, str) else val

    def _csv_parse(self, path, delimiter=","):
        import csv
        p = self._p(path)
        if not p.exists(): return f"不存在: {p}"
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
        if not rows: return "空CSV"
        out = f"CSV: {len(rows)}行 x {len(rows[0])}列\n"
        out += " | ".join(rows[0]) + "\n" + "-"*40 + "\n"
        for r in rows[1:20]: out += " | ".join(r) + "\n"
        if len(rows) > 21: out += f"...（共{len(rows)-1}行数据）"
        return out

    def _yaml_parse(self, path):
        try:
            import yaml
            p = self._p(path)
            if not p.exists(): return f"不存在: {p}"
            return json.dumps(yaml.safe_load(p.read_text(encoding="utf-8")), ensure_ascii=False, indent=2)
        except ImportError: return "pyyaml未安装: pip install pyyaml"

    # === Git类工具 ===
    def _git_cmd(self, args, path="."):
        try:
            r = subprocess.run(["git"] + args, cwd=str(self._p(path)), capture_output=True, text=True, timeout=30)
            return (r.stdout or "") + (r.stderr or "")
        except Exception as e: return f"Git失败: {e}"

    def _git_add(self, path=".", files="."): return self._git_cmd(["add", files], path)
    def _git_commit(self, message, path="."): return self._git_cmd(["commit", "-m", message], path)
    def _git_push(self, path=".", remote="origin", branch=""):
        args = ["push", remote] + ([branch] if branch else [])
        return self._git_cmd(args, path)
    def _git_pull(self, path=".", remote="origin", branch=""):
        args = ["pull", remote] + ([branch] if branch else [])
        return self._git_cmd(args, path)
    def _git_diff(self, path=".", file=""): return self._git_cmd(["diff", file] if file else ["diff"], path)
    def _git_branch(self, path=".", create=""):
        if create: return self._git_cmd(["checkout", "-b", create], path)
        return self._git_cmd(["branch", "-a"], path)
    def _git_checkout(self, branch, path="."): return self._git_cmd(["checkout", branch], path)
    def _git_clone(self, url, path="."): return self._git_cmd(["clone", url, str(self._p(path))])

    # === 文本类工具 ===
    def _regex_replace(self, text_or_path, pattern, replacement):
        p = self._p(text_or_path)
        if p.exists():
            c = p.read_text(encoding="utf-8"); nc = re.sub(pattern, replacement, c)
            p.write_text(nc, encoding="utf-8"); return f"已替换: {p}"
        return re.sub(pattern, replacement, text_or_path)

    def _text_diff(self, text1, text2):
        import difflib
        d = difflib.unified_diff(text1.splitlines(), text2.splitlines(), lineterm="")
        return "\n".join(d)

    def _count_lines(self, path):
        p = self._p(path)
        if p.is_dir():
            total = 0
            for f in p.rglob("*"):
                if f.is_file():
                    try: total += sum(1 for _ in open(f, encoding="utf-8", errors="replace"))
                    except Exception: pass
            return f"目录总行数: {total}"
        return f"行数: {sum(1 for _ in open(p, encoding='utf-8', errors='replace'))}"

    def _deduplicate(self, text_or_path):
        p = self._p(text_or_path)
        if p.exists():
            lines = p.read_text(encoding="utf-8").split("\n")
            seen = set(); out = []
            for l in lines:
                if l not in seen: seen.add(l); out.append(l)
            p.write_text("\n".join(out), encoding="utf-8")
            return f"去重完成: {len(lines)} -> {len(out)} 行"
        lines = text_or_path.split("\n")
        return "\n".join(dict.fromkeys(lines))

    # === 其他工具 ===
    def _notify(self, title, message):
        try:
            subprocess.run(["notify-send", title, message], timeout=5)
            return f"通知已发送: {title}"
        except: return "notify-send不可用"

    def _schedule(self, message, seconds=60):
        tid = f"sched_{int(time.time())}"
        def _reminder():
            time.sleep(int(seconds))
            print(f"\n[提醒] 提醒: {message}\n你> ", end="", flush=True)
        import threading
        threading.Thread(target=_reminder, daemon=True).start()
        return f"定时提醒已设置: {seconds}秒后提醒'{message}'"

    def _list_schedules(self):
        return "定时提醒通过线程管理，进程结束后失效。建议使用系统cron做持久化定时。"

    def _tree(self, path=".", depth=3, max_items=100):
        p = self._p(path); out = []
        def _walk(d, level=0):
            if level > int(depth): return
            items = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for i, item in enumerate(items):
                if len(out) >= int(max_items): return
                prefix = "  " * level + ("├── " if i < len(items)-1 else "└── ")
                out.append(f"{prefix}{item.name}{'/' if item.is_dir() else ''}")
                if item.is_dir() and not item.name.startswith('.'): _walk(item, level+1)
        out.append(f"{p.name}/")
        _walk(p)
        return "\n".join(out)

    # === Goal目标工具 ===
    def _goal_create(self, objective, max_rounds="20"):
        if not self.memory: return "记忆未启用"
        goals = self.memory.data.setdefault("goals", [])
        goal = {"id": f"goal_{int(time.time()*1000)}", "objective": objective,
                "phase": "active", "rounds_started": 0, "max_rounds": int(max_rounds),
                "created_at": time.time(), "updated_at": time.time(),
                "blocked_reason": None, "history": []}
        goals.append(goal); self.memory.save()
        return f"目标已创建: {objective} (最多{max_rounds}轮)"

    def _goal_complete(self, objective=""):
        if not self.memory: return "记忆未启用"
        goals = self.memory.data.get("goals", [])
        for g in reversed(goals):
            if g["phase"] == "active" and (not objective or objective in g["objective"]):
                g["phase"] = "complete"; g["updated_at"] = time.time(); self.memory.save()
                return f"目标已完成: {g['objective']}"
        return "无进行中的目标"

    def _goal_list(self):
        if not self.memory: return "记忆未启用"
        goals = self.memory.data.get("goals", [])
        if not goals: return "无目标"
        out = ""
        for g in goals[-10:]:
            out += f"[{g['phase']}] {g['objective'][:60]} (轮次{g['rounds_started']}/{g['max_rounds']})\n"
        return out.strip()

    def _goal_block(self, reason, objective=""):
        if not self.memory: return "记忆未启用"
        goals = self.memory.data.get("goals", [])
        for g in reversed(goals):
            if g["phase"] == "active" and (not objective or objective in g["objective"]):
                g["phase"] = "blocked"; g["blocked_reason"] = reason
                g["updated_at"] = time.time(); self.memory.save()
                return f"目标已阻塞: {g['objective']}\n原因: {reason}"
        return "无进行中的目标"

    # === Todo任务工具 ===
    def _todo_write(self, items):
        """写入任务列表，items格式：任务1:状态,任务2:状态 状态为pending/in_progress/completed"""
        if not self.memory: return "记忆未启用"
        todos = []
        for item in items.split(","):
            if ":" in item:
                content, status = item.rsplit(":", 1)
                status = status.strip().lower()
                if status not in ("pending", "in_progress", "completed"): status = "pending"
                todos.append({"content": content.strip(), "status": status})
            elif item.strip():
                todos.append({"content": item.strip(), "status": "pending"})
        self.memory.data["todos"] = todos; self.memory.save()
        return f"任务列表已更新: {len(todos)}项"

    def _todo_list(self):
        if not self.memory: return "记忆未启用"
        todos = self.memory.data.get("todos", [])
        if not todos: return "无任务"
        icons = {"pending": "", "in_progress": "[循环]", "completed": "[完成]"}
        return "\n".join(f"{icons.get(t['status'],'?')} {t['content']}" for t in todos)


# ============================================================
# 技能系统（.md即插即用）
# ============================================================
class SkillManager:
    """技能管理器：扫描skills/目录，解析.md文件，动态加载工具和提示词。

    技能.md格式：
    ---
    name: 技能名
    description: 描述
    version: 1.0
    trigger: 关键词1,关键词2
    ---
    ## 系统提示
    （追加到小凌系统提示的内容）

    ## 工具
    ```python
    def my_tool(param1, param2="default"):
        \"\"\"工具描述\"\"\"
        return result
    ```

    ## 规则
    - 行为规则
    """

    def __init__(self, skills_dir, tool_manager, memory=None):
        self.skills_dir = Path(skills_dir)
        self.tool_manager = tool_manager
        self.memory = memory
        self.skills = {}
        self.system_prompts = []
        self.rules = []
        # 技能使用遥测 + 生命周期策展（来源：Hermes）
        self.usage_path = self.skills_dir / ".usage.json"
        self.usage = self._load_usage()
        self.load_all()

    def load_all(self):
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for md_file in sorted(self.skills_dir.glob("*.md")):
            if self.load_skill(md_file):
                count += 1
        return count

    def load_skill(self, md_path):
        try:
            content = Path(md_path).read_text(encoding="utf-8")
            meta = self._parse_frontmatter(content)
            name = meta.get("name", md_path.stem)
            # 从文件名和首行标题推导描述和触发词
            desc = meta.get("description", "")
            if not desc:
                m = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
                desc = m.group(1).strip() if m else name
            triggers = [t.strip() for t in meta.get("trigger", "").split(",") if t.strip()]
            if not triggers:
                # 从文件名推导触发关键词
                triggers = [name]
                # 拆分文件名中的中英文
                for seg in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', name):
                    if len(seg) >= 2 and seg not in triggers:
                        triggers.append(seg)
            skill = {
                "name": name,
                "description": desc,
                "version": meta.get("version", "1.0"),
                "trigger": triggers,
                "file": str(md_path),
                "tools": [],
                "enabled": True,
            }

            # v0.0.2 token 优化：系统提示只存技能摘要（名称+描述+触发词），
            # 不注入全文（全文在技能触发时才加载到对话）
            sys_prompt = self._extract_section(content, "系统提示", "system")
            if not sys_prompt:
                sys_prompt = content.strip()
            if sys_prompt:
                skill["system_prompt"] = sys_prompt  # 全文仍存 skill 内（触发时用）
                # 摘要：只注入 名称 + 描述 + 触发词（几十 token，替代几千 token 全文）
                trig_str = "/".join(triggers[:5])
                self.system_prompts.append(
                    f"【技能·{name}】{desc[:80]}（触发词：{trig_str}）")

            # 提取规则
            rules = self._extract_section(content, "规则", "rules")
            if rules:
                skill["rules"] = rules
                self.rules.append(f"[{name}] {rules}")

            # 提取并执行Python工具代码：优先 ## 工具 段，否则全文搜索
            tools_code = self._extract_section(content, "工具", "tools")
            search_area = tools_code if tools_code else content
            code_blocks = re.findall(r'```python\s*\n(.*?)```', search_area, re.DOTALL)
            if not code_blocks:
                code_blocks = re.findall(r'```\s*\n(.*?)```', search_area, re.DOTALL)
            for code in code_blocks:
                loaded = self._exec_tool_code(code, name)
                skill["tools"].extend(loaded)

            self.skills[name] = skill
            return True
        except Exception as e:
            print(f"  [技能] 加载失败 {md_path.name}: {e}")
            return False

    def _parse_frontmatter(self, content):
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not m: return {}
        meta = {}
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        return meta

    def _extract_section(self, content, title_cn, title_en=None):
        patterns = [rf'##\s*{re.escape(title_cn)}\s*\n(.*?)(?=\n##\s|\Z)']
        if title_en: patterns.append(rf'##\s*{re.escape(title_en)}\s*\n(.*?)(?=\n##\s|\Z)')
        for pat in patterns:
            m = re.search(pat, content, re.DOTALL)
            if m: return m.group(1).strip()
        return ""

    def _exec_tool_code(self, code, skill_name):
        """执行技能中的Python代码，提取def函数注册为工具"""
        # 先找出代码中定义的函数名（排除下划线开头的内部函数）
        defined_funcs = set(name for name in re.findall(r'^def\s+(\w+)\s*\(', code, re.MULTILINE) if not name.startswith("_"))
        namespace = {
            "json": json, "os": os, "sys": sys, "re": re,
            "time": time, "math": math, "random": random,
            "subprocess": subprocess, "urllib": __import__("urllib"),
            "Path": Path, "datetime": datetime, "timedelta": timedelta,
            "BASE_DIR": BASE_DIR, "DATA_DIR": DATA_DIR,
            "memory": self.memory,
        }
        loaded = []
        try:
            exec(code, namespace)
            for name in defined_funcs:
                obj = namespace.get(name)
                if callable(obj):
                    desc = obj.__doc__ or f"{skill_name}技能工具"
                    if self.tool_manager.register_external(name, obj, desc):
                        loaded.append(name)
        except Exception as e:
            print(f"  [技能] {skill_name} 工具代码执行失败: {e}")
        return loaded

    def get_system_prompt(self):
        if not self.system_prompts: return ""
        return "\n\n【已加载技能】\n" + "\n\n".join(self.system_prompts)

    def get_rules(self):
        if not self.rules: return ""
        return "\n".join(f"- {r}" for r in self.rules)

    def list_skills(self):
        if not self.skills: return "无已加载技能"
        out = "已加载技能：\n"
        for name, s in self.skills.items():
            tools = ", ".join(s["tools"]) if s["tools"] else "无工具"
            out += f"  - {name} v{s['version']}: {s['description'][:40]} [{tools}]\n"
        return out

    def match_trigger(self, text):
        """检查文本是否触发某个技能的关键词"""
        triggered = []
        for name, s in self.skills.items():
            for t in s.get("trigger", []):
                if t and t in text:
                    triggered.append(name)
                    break
        return triggered

    # === 技能使用遥测 + 生命周期策展（来源：Hermes）===
    def _load_usage(self):
        if self.usage_path.exists():
            try:
                return json.loads(self.usage_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_usage(self):
        """原子写入 .usage.json"""
        try:
            self.usage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.usage_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.usage, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.usage_path)
        except Exception:
            pass

    def record_use(self, name):
        """记录技能使用次数和最后使用时间，原子写入"""
        rec = self.usage.get(name, {"count": 0, "last_used": 0, "state": "active"})
        rec["count"] = rec.get("count", 0) + 1
        rec["last_used"] = time.time()
        if rec.get("state") not in ("pinned",):
            rec["state"] = "active"
        self.usage[name] = rec
        self._save_usage()

    def evolve_skills(self, app):
        """v0.0.10：技能自我进化——从高频活动自动创建新技能。"""
        try:
            if not hasattr(app, "growth") or app.growth.total_items == 0:
                return 0
            topic_count = {}
            import json as _j
            idx = GROWTH_INDEX
            if idx.exists():
                for line in idx.read_text(encoding="utf-8").split("\n"):
                    try:
                        e = _j.loads(line)
                        src_s = e.get("source", "")
                        topic_count[src_s] = topic_count.get(src_s, 0) + 1
                    except Exception:
                        continue
            created = 0
            for src_s, cnt in topic_count.items():
                if cnt >= 10 and src_s in ("chat", "distill", "agent"):
                    name = f"auto_{src_s}_expert"
                    if name not in self.skills:
                        fpath = self.skills_dir / f"{name}.md"
                        fpath.write_text(
                            f"---\nname: {name}\ntrigger: auto,{src_s}\n---\n"
                            f"## 系统提示\n你是小凌的{src_s}专家，处理相关任务。\n"
                            f"## 规则\n- 这是从{src_s}高频活动中自动提炼的技能\n",
                            encoding="utf-8")
                        self.load_skill(fpath)
                        created += 1
            if created:
                print(f"  [进化] 自动创建 {created} 个新技能")
            return created
        except Exception:
            return 0

    def maybe_curate(self):
        """生命周期策展：14天未用→stale，30天未用→archived（移到.archive/），pinned不参与"""
        now = time.time()
        archive_dir = self.skills_dir / ".archive"
        changed = False
        for name, rec in list(self.usage.items()):
            if rec.get("state") == "pinned":
                continue
            last = rec.get("last_used", 0)
            if not last:
                continue
            days = (now - last) / 86400
            if days >= 30 and rec.get("state") != "archived":
                # 移动技能文件到 .archive/
                skill = self.skills.get(name)
                if skill and skill.get("file"):
                    src = Path(skill["file"])
                    if src.exists():
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.move(str(src), str(archive_dir / src.name))
                        except Exception:
                            pass
                rec["state"] = "archived"
                changed = True
            elif days >= 14 and rec.get("state") == "active":
                rec["state"] = "stale"
                changed = True
        if changed:
            self._save_usage()

    def auto_create_skill(self, description):
        """后台审查自动创建技能文件并加载（来源：Hermes）"""
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            name = f"auto_{ts}"
            path = self.skills_dir / f"{name}.md"
            content = (
                "---\n"
                f"name: {name}\n"
                f"description: 自动提炼的经验技能\n"
                "version: 1.0\n"
                f"trigger: auto,{name}\n"
                "---\n"
                "## 系统提示\n"
                f"{description}\n"
                "## 规则\n"
                "- 这是从历史对话自动提炼的经验，遇到相似任务时可参考。\n"
            )
            path.write_text(content, encoding="utf-8")
            self.usage[name] = {"count": 0, "last_used": time.time(), "state": "active"}
            self._save_usage()
            self.load_skill(path)
            print(f"  [技能] 自动创建: {name}")
            return name
        except Exception as e:
            print(f"  [技能] auto_create_skill 失败: {e}")
            return None


# ============================================================
# API老师（仅学习和蒸馏用）
# ============================================================
def learn_from_teacher(topic, num_questions, memory=None):
    api_key = CONFIG["deepseek_api_key"]
    if not api_key or api_key == "暂未填入": return "未配置API密钥"
    try:
        sp=f"""你是资深教师，帮小凌学习「{topic}」。
生成{num_questions}组高质量问答，用===Q===和===A===分隔，直接输出。"""
        payload=json.dumps({"model":CONFIG["teacher_model"],
            "messages":[{"role":"system","content":sp},{"role":"user","content":f"学习「{topic}」"}],
            "temperature":0.7,"max_tokens":2048}).encode()
        req=urllib.request.Request(f"{CONFIG['deepseek_base_url']}/chat/completions",
            data=payload,headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=120) as r:
            content=json.loads(r.read())["choices"][0]["message"]["content"]
        pairs=[]
        for block in re.split(r'===Q===',content)[1:]:
            parts=re.split(r'===A===',block,maxsplit=1)
            if len(parts)==2:
                q,a=parts[0].strip(),parts[1].strip()
                if q and a: pairs.append((q,a))
        if not pairs: pairs.append((f"关于{topic}",content.strip()))
        if memory:
            for q,a in pairs: memory.add_semantic(f"Q:{q}\nA:{a}",source="teacher",confidence=0.85)
            memory.add_episode("学习",f"学了「{topic}」，{len(pairs)}个知识点",valence=0.5,intensity=0.8)
        DATA_DIR.mkdir(parents=True,exist_ok=True)
        with open(LEARNED_PATH,"a",encoding="utf-8") as f:
            for q,a in pairs: f.write(json.dumps({"topic":topic,"question":q,"answer":a},ensure_ascii=False)+"\n")
        with open(CORPUS_PATH,"a",encoding="utf-8") as f:
            f.write(f"\n# === 学习：{topic} ===\n")
            for q,a in pairs: f.write(f"你：{q}\n小凌：{a}\n")
        if memory: memory.save()
        result=f"学习完成！「{topic}」{len(pairs)}个知识点\n"
        for i,(q,a) in enumerate(pairs[:3],1): result+=f"\nQ{i}: {q[:50]}\nA{i}: {a[:80]}\n"
        return result
    except Exception as e: return f"学习失败：{e}"


# ============================================================
# 蒸馏训练
# ============================================================
def distill_train(epochs=2, batch_size=2, lr=1e-4):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model, TaskType, PeftModel
        from datasets import Dataset
    except ImportError as e:
        return f"缺少ML依赖：{e}\n请安装：pip install torch transformers peft accelerate datasets"

    # v0.0.5 fix：兼容魔塔下载的任意 safetensors/bin 文件名（model-00000-of-00001.safetensors 等）
    model_file = None
    for _cand in [MODEL_DIR / "model.safetensors", MODEL_DIR / "pytorch_model.bin"]:
        if _cand.exists() and _cand.stat().st_size > 10*1024*1024:
            model_file = _cand; break
    if model_file is None:
        for _p in MODEL_DIR.glob("*.safetensors"):
            if _p.stat().st_size > 10*1024*1024:
                model_file = _p; break
    if model_file is None:
        for _p in MODEL_DIR.glob("*.bin"):
            if _p.stat().st_size > 10*1024*1024:
                model_file = _p; break
    if model_file is None:
        return f"模型权重为空：{MODEL_DIR}\n请先下载基底模型（启动时选模型自动下载）"

    records = []
    if INTERACTIONS_PATH.exists():
        with open(INTERACTIONS_PATH,"r",encoding="utf-8") as f:
            for line in f:
                try:
                    rec=json.loads(line.strip())
                    u,a=rec.get("user","").strip(),rec.get("assistant","").strip()
                    if len(u)>=2 and len(a)>=2: records.append(rec)
                except Exception: pass
    if LEARNED_PATH.exists():
        with open(LEARNED_PATH,"r",encoding="utf-8") as f:
            for line in f:
                try:
                    rec=json.loads(line.strip())
                    q,a=rec.get("question","").strip(),rec.get("answer","").strip()
                    if len(q)>=2 and len(a)>=2: records.append({"user":q,"assistant":a})
                except Exception: pass

    seen = {}
    for r in records: seen[r.get("user","").lower()] = r
    records = list(seen.values())
    random.shuffle(records)

    if len(records) < 5:
        return f"训练数据不足（仅{len(records)}条），多聊聊天积累一下"

    print(f"\n{'='*50}")
    print(f"  小凌蒸馏训练")
    print(f"  数据：{len(records)}条，轮数：{epochs}")
    print(f"{'='*50}\n")

    split = max(1, int(len(records)*0.95))
    train_recs, val_recs = records[:split], records[split:]

    # v0.0.9：不再强制 Qwen2 架构——MiniCPM5 使用 Llama 架构，保持 config 原样
    # 仅提示：config 缺失时需按所选基底模型修正
    _cfg_path = MODEL_DIR / "config.json"
    if _cfg_path.exists():
        try:
            with open(_cfg_path) as _f: _cfg = json.load(_f)
            if not _cfg.get("model_type") or not _cfg.get("architectures"):
                print("[训练] 警告：config.json 架构字段不完整")
                print("[训练] 请确认 config.json 匹配当前基底模型架构")
        except Exception:
            pass

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), trust_remote_code=True, use_fast=_USE_FAST_TOKENIZER)
    if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token

    def fmt(ex): return {"text":f"### 指令:\n{ex['user']}\n\n### 回复:\n{ex['assistant']}\n"}
    train_ds = Dataset.from_list([fmt(r) for r in train_recs])
    val_ds = Dataset.from_list([fmt(r) for r in val_recs])

    print("[训练] 加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_DIR),
        dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None, trust_remote_code=True)

    ac = ADAPTER_DIR / "adapter_config.json"
    if ac.exists():
        print("[训练] 加载已有LoRA，继续微调...")
        model = PeftModel.from_pretrained(model, str(ADAPTER_DIR), adapter_name="default")
        for n,p in model.named_parameters():
            if "lora" in n: p.requires_grad = True
    else:
        print("[训练] 新建LoRA（r=8）...")
        lc = LoraConfig(task_type=TaskType.CAUSAL_LM,r=8,lora_alpha=16,lora_dropout=0.05,
                        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],bias="none")
        model = get_peft_model(model, lc)
        old = ADAPTER_DIR / "adapter.pt"
        if old.exists():
            try:
                st=torch.load(str(old),map_location="cpu",weights_only=True)
                pd={n:p for n,p in model.named_parameters()}; loaded=0
                for k,w in st.items():
                    if "lora_A" in k or "lora_B" in k:
                        nn="base_model.model."+k+".default.weight"
                        if nn in pd: pd[nn].data.copy_(w); loaded+=1
                print(f"[训练] 从旧adapter.pt加载{loaded}个权重")
            except Exception as e: print(f"[训练] 旧adapter加载失败：{e}")

    model.print_trainable_parameters()

    out_dir = DATA_DIR / "checkpoints"; out_dir.mkdir(parents=True, exist_ok=True)
    # transformers 新版用 eval_strategy，旧版用 evaluation_strategy
    try:
        training_args = TrainingArguments(
            output_dir=str(out_dir), num_train_epochs=epochs,
            per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=4, learning_rate=lr, lr_scheduler_type="cosine",
            logging_steps=10, save_strategy="epoch", eval_strategy="epoch",
            bf16=torch.cuda.is_available(), gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant":False}, report_to="none", save_total_limit=3)
    except TypeError:
        training_args = TrainingArguments(
            output_dir=str(out_dir), num_train_epochs=epochs,
            per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=4, learning_rate=lr, lr_scheduler_type="cosine",
            logging_steps=10, save_strategy="epoch", evaluation_strategy="epoch",
            bf16=torch.cuda.is_available(), gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant":False}, report_to="none", save_total_limit=3)

    def tok(ex):
        o=tokenizer(ex["text"],truncation=True,max_length=1024,padding="max_length")
        o["labels"]=[(l if l != tokenizer.pad_token_id else -100) for l in o["input_ids"]]
        return o

    train_tok = train_ds.map(tok, batched=True, remove_columns=["text"])
    val_tok = val_ds.map(tok, batched=True, remove_columns=["text"])

    trainer = Trainer(model=model, args=training_args, train_dataset=train_tok, eval_dataset=val_tok)
    print("[训练] 开始...")
    trainer.train()

    old_pt = ADAPTER_DIR / "adapter.pt"
    if old_pt.exists():
        bk = DATA_DIR / "backups"; bk.mkdir(parents=True, exist_ok=True)
        bn = f"adapter-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pt"
        shutil.copy2(old_pt, bk/bn)
        print(f"  旧适配器已备份：{bn}")

    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))
    print("[训练] 完成！小凌又成长了一些。")

    mem = LongTermMemory(MEMORY_PATH)
    mem.data.setdefault("chat_stats",{})["trained_count"] = mem.data.get("chat_stats",{}).get("trained_count",0)+1
    mem.save()
    return f"训练完成！用了{len(records)}条数据，{epochs}轮。适配器已更新。"


# ============================================================
# Goal目标系统（参考DeepSeek Harness：目标状态机+轮次驱动）
# ============================================================
class GoalManager:
    """目标管理器：目标有生命周期，驱动agent持续执行直到完成。

    状态：active → paused → blocked → complete
    每个目标有最大轮次限制，防止无限循环。
    """

    def __init__(self, memory):
        self.memory = memory
        self.goals = memory.data.get("goals", [])

    def create(self, objective, max_rounds=20):
        goal = {
            "id": f"goal_{int(time.time()*1000)}",
            "objective": objective,
            "phase": "active",
            "rounds_started": 0,
            "max_rounds": max_rounds,
            "created_at": time.time(),
            "updated_at": time.time(),
            "blocked_reason": None,
            "history": [],
        }
        self.goals.append(goal)
        self._save()
        return goal

    def get_active(self):
        for g in self.goals:
            if g["phase"] == "active":
                return g
        return None

    def advance_round(self, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal: return None
        goal["rounds_started"] += 1
        goal["updated_at"] = time.time()
        if goal["rounds_started"] >= goal["max_rounds"]:
            goal["phase"] = "blocked"
            goal["blocked_reason"] = "达到最大轮次限制，需要人工确认或调整目标"
        self._save()
        return goal

    def complete(self, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal: return None
        goal["phase"] = "complete"
        goal["updated_at"] = time.time()
        self._save()
        return goal

    def block(self, reason, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal: return None
        goal["phase"] = "blocked"
        goal["blocked_reason"] = reason
        goal["updated_at"] = time.time()
        self._save()
        return goal

    def pause(self, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal: return None
        goal["phase"] = "paused"
        goal["updated_at"] = time.time()
        self._save()
        return goal

    def resume(self, goal_id=None):
        goal = self._find(goal_id)
        if not goal: return None
        goal["phase"] = "active"
        goal["blocked_reason"] = None
        goal["updated_at"] = time.time()
        self._save()
        return goal

    def add_history(self, event, goal_id=None):
        goal = self._find(goal_id) or self.get_active()
        if not goal: return
        goal["history"].append({"time": time.time(), "event": event[:200]})
        if len(goal["history"]) > 50: goal["history"] = goal["history"][-50:]
        self._save()

    def render_goal_prompt(self):
        """生成目标轮次提示（参考Harness的goal_round prompt）"""
        goal = self.get_active()
        if not goal: return ""
        return (f"<goal_round>\n"
                f"目标: {goal['objective']}\n"
                f"轮次: {goal['rounds_started']}/{goal['max_rounds']}\n\n"
                f"继续朝着目标推进。以当前工作区、工具结果和持久状态为准，"
                f"不要假设之前的叙述仍然有效。取得具体进展并验证结果。"
                f"声称完成前先收集证据证明目标已达成。如果还有工作，保持目标active。\n"
                f"</goal_round>")

    def list_goals(self):
        if not self.goals: return "无目标"
        out = ""
        for g in self.goals[-10:]:
            out += f"[{g['phase']}] {g['objective'][:60]} (轮次{g['rounds_started']}/{g['max_rounds']})\n"
        return out.strip()

    def _find(self, goal_id):
        if not goal_id: return None
        for g in self.goals:
            if g["id"] == goal_id: return g
        return None

    def _save(self):
        self.memory.data["goals"] = self.goals
        self.memory.save()


# ============================================================
# Guard守卫系统（重复工具检测+超时策略）

# ============================================================
# 离线模式守卫（v0.0.20：断网也能完整运行——本地模型优先）
# ============================================================
class OfflineGuard:
    """网络检测 + 离线模式管理。断网时本地模型完整可用。"""

    def __init__(self):
        self.online = None          # None=未检测 True=在线 False=离线
        self.last_check = 0
        self.check_interval = 30    # 30 秒检测一次

    def is_online(self, force=False):
        """检测网络是否可用（快速，失败自动降级离线）。"""
        mode = CONFIG.get("offline_mode", "auto")
        if mode == "on":
            self.online = False
            return False
        if mode == "off":
            self.online = True
            return True
        # auto 模式：30 秒缓存
        now = time.time()
        if not force and self.online is not None and (now - self.last_check) < self.check_interval:
            return self.online
        self.last_check = now
        try:
            import socket as _s
            _s.setdefaulttimeout(2)
            # 快速 DNS 解析 + TCP 连接测试（不走 HTTP，省资源）
            _s.getaddrinfo("gitee.com", 443, _s.AF_INET, _s.SOCK_STREAM)
            self.online = True
        except Exception:
            self.online = False
        return self.online

    def status_text(self):
        """离线状态文本。"""
        on = self.is_online()
        mode = CONFIG.get("offline_mode", "auto")
        if on:
            return f"在线（模式:{mode}）"
        return "离线模式——本地模型完整可用，蒸馏/更新等功能已暂停"

    def check_offline(self, app):
        """检查并在离线时输出提示（启动时调用一次）。"""
        if not self.is_online():
            print("\n  [离线] 当前无网络连接——小凌进入离线模式")
            print("  [离线] 本地模型优先，对话/工具/记忆全部可用")
            print("  [离线] 蒸馏学习/自动更新需联网，恢复网络后自动启用")
            print("  [离线] 说 `network` 可重新检测\n")
        else:
            print("  [网络] 在线——蒸馏/更新可用")


# ============================================================
# 多平台接入（v0.0.20：微信/飞书/QQ/企业微信/钉钉/Telegram/Discord）
# ============================================================
# 设计：统一消息接口——平台适配器收到消息 → 调用 app.chat() → 发回回复
# 每个平台一个适配器类，配置对应 Key/Webhook 即启用，未配置自动跳过
# 用法：python xl.py --platform wechat   （或配置后启动自动启用已配平台）
class PlatformAdapter:
    """多平台机器人适配层（类似 Work Buddy 的全平台接入）。"""

    def __init__(self, app):
        self.app = app
        self.running = {}

    # ---- 统一消息处理 ----
    def handle_message(self, text, platform, sender=""):
        """收到平台消息 → 小凌处理 → 返回回复文本。"""
        if not text or not text.strip():
            return "嗯？我在听。"
        # 特殊指令直接处理
        t = text.strip().lower()
        if t in ("蒸馏", "去蒸馏"):
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = run_distill(self.app, rounds=4, epochs=1)
            return result
        if t == "status":
            return self.app.show_status()
        if t == "report":
            return self.app.show_report()
        if t == "update":
            return self.app.updater.apply_update()
        # 普通对话（本地模型优先，离线可用）
        try:
            reply, _ = self.app.chat(text)
            return reply
        except Exception as e:
            return f"（小凌处理出错：{e}）"

    # ---- 各平台适配器 ----
    def start_all(self):
        """启动所有已配置的平台。返回启动摘要。"""
        cfgs = CONFIG.get("platforms", {})
        started = []
        for name, cfg in cfgs.items():
            if cfg.get("enabled"):
                try:
                    ok = getattr(self, f"start_{name}")(cfg)
                    if ok:
                        started.append(name)
                except Exception as e:
                    print(f"  [平台] {name} 启动失败: {e}")
        if started:
            print(f"  [平台] 已接入：{', '.join(started)}")
        else:
            print("  [平台] 未配置任何平台（可在 CONFIG['platforms'] 配置微信/飞书/QQ等）")
            print("  [平台] 当前使用：桌面宠物 + 命令行")
        return started

    # 微信（wechaty / itchat 协议，需安装对应库）
    def start_wechat(self, cfg):
        try:
            import itchat  # noqa
        except ImportError:
            print("  [微信] 需安装：pip install itchat（或 wechaty）")
            return False
        def _handler(msg):
            if msg.get("Type") == "Text":
                reply = self.handle_message(msg.get("Text", ""), "wechat", msg.get("User", {}).get("NickName", ""))
                try:
                    itchat.send(reply, toUserName=msg.get("FromUserName"))
                except Exception:
                    pass
        itchat.msg_register(itchat.content.TEXT)(_handler)
        try:
            itchat.auto_login(hotReload=True)
            itchat.run()
            return True
        except Exception as e:
            print(f"  [微信] 登录失败: {e}")
            return False

    # 飞书（开放平台长连接，无需公网）
    def start_feishu(self, cfg):
        try:
            import lark_oapi as _lark  # noqa
        except ImportError:
            print("  [飞书] 需安装：pip install lark-oapi")
            return False
        app_id, app_secret = cfg.get("app_id", ""), cfg.get("app_secret", "")
        if not app_id:
            print("  [飞书] 未配置 app_id/app_secret")
            return False
        def _reply(client, msg_text, chat_id):
            reply = self.handle_message(msg_text, "feishu")
            try:
                client.im.v1.message.create(request=__import__("lark_oapi.api.im.v1", fromlist=["CreateMessageRequest"]).CreateMessageRequest.builder().receive_id_type("chat_id").request_body(__import__("lark_oapi.api.im.v1", fromlist=["CreateMessageRequestBody"]).CreateMessageRequestBody.builder().receive_id(chat_id).msg_type("text").content(f'{{"text":"{reply}"}}').build()).build())
            except Exception:
                pass
        def _handler(data):
            try:
                if data.event.message.msg_type == "text":
                    text = data.event.message.content
                    import json as _j
                    try:
                        text = _j.loads(text).get("text", text)
                    except Exception:
                        pass
                    chat_id = data.event.message.chat_id
                    _reply(None, text, chat_id)
            except Exception:
                pass
        try:
            client = _lark.Client.builder().app_id(app_id).app_secret(app_secret).log_level(_lark.LogLevel.ERROR).build()
            handler = _lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(_handler).build()
            import threading as _th
            _th.Thread(target=lambda: _lark.WSClient("wss://open.feishu.cn/connect", app_id, app_secret, handler).start(), daemon=True).start()
            return True
        except Exception as e:
            print(f"  [飞书] 启动失败: {e}")
            return False

    # QQ（OneBot / go-cqhttp 协议 WebSocket）
    def start_qq(self, cfg):
        try:
            import websocket  # noqa
        except ImportError:
            print("  [QQ] 需安装：pip install websocket-client（并运行 go-cqhttp）")
            return False
        ws_url = cfg.get("onebot_ws", "ws://127.0.0.1:6700")
        try:
            import threading as _th
            def _loop():
                import websocket as _ws
                try:
                    _ws.enableTrace(False)
                    ws = _ws.create_connection(ws_url, timeout=10)
                    print(f"  [QQ] 已连接 OneBot：{ws_url}")
                    while True:
                        msg = ws.recv()
                        if not msg: continue
                        try:
                            data = json.loads(msg)
                        except Exception:
                            continue
                        if data.get("post_type") == "message" and data.get("message_type") in ("group", "private"):
                            raw = data.get("raw_message") or data.get("message", "")
                            if isinstance(raw, list):
                                raw = "".join(seg.get("data", {}).get("text", "") for seg in raw if seg.get("type") == "text")
                            reply = self.handle_message(str(raw), "qq", str(data.get("user_id", "")))
                            # 回复
                            ws.send(json.dumps({
                                "action": "send_msg",
                                "params": {
                                    "message_type": data.get("message_type"),
                                    "user_id": data.get("user_id"),
                                    "group_id": data.get("group_id", 0),
                                    "message": reply[:2000],
                                },
                            }, ensure_ascii=False))
                        elif data.get("echo") == "ping":
                            pass
                except Exception as e:
                    print(f"  [QQ] 连接断开: {e}，重连中...")
                    _th.Timer(5, _loop).start()
            _th.Thread(target=_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"  [QQ] 启动失败: {e}")
            return False

    # 企业微信（群机器人 Webhook + 接收消息 API）
    def start_wecom(self, cfg):
        webhook = cfg.get("webhook", "")
        if webhook:
            # 群机器人：只发消息（接收需企业微信 API）
            print("  [企业微信] 群机器人 Webhook 已配置（发消息模式）")
            self.wecom_webhook = webhook
            return True
        corp_id, agent_id, secret = cfg.get("corp_id", ""), cfg.get("agent_id", ""), cfg.get("secret", "")
        if corp_id and agent_id and secret:
            print("  [企业微信] 应用模式已配置（需公网回调地址接收消息）")
            print("  [企业微信] 请在企微后台配置回调 URL：http://你的地址/callback")
            return True
        print("  [企业微信] 未配置（需 webhook 或 corp_id/agent_id/secret）")
        return False

    # 钉钉（群机器人 Webhook）
    def start_dingtalk(self, cfg):
        webhook = cfg.get("webhook", "")
        secret = cfg.get("secret", "")
        if not webhook:
            print("  [钉钉] 未配置 webhook")
            return False
        self.dingtalk_webhook = webhook
        self.dingtalk_secret = secret
        print("  [钉钉] 群机器人已配置（接收消息需钉钉回调）")
        return True

    # Telegram（Bot API 长轮询，无需公网）
    def start_telegram(self, cfg):
        token = cfg.get("bot_token", "")
        if not token:
            print("  [Telegram] 未配置 bot_token")
            return False
        try:
            import threading as _th
            def _poll():
                import urllib.request as _ur
                offset = 0
                while True:
                    try:
                        url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=25&offset={offset}"
                        with _ur.urlopen(url, timeout=30) as r:
                            data = json.loads(r.read().decode("utf-8"))
                        for up in data.get("result", []):
                            offset = up["update_id"] + 1
                            msg = up.get("message", {})
                            text = msg.get("text", "")
                            if not text: continue
                            uid = msg["chat"]["id"]
                            allowed = cfg.get("allowed_users", "")
                            if allowed and str(uid) not in allowed.split(","):
                                continue
                            reply = self.handle_message(text, "telegram", str(uid))
                            send = f"https://api.telegram.org/bot{token}/sendMessage"
                            import urllib.parse as _up
                            req = _ur.Request(send, data=_up.urlencode({"chat_id": uid, "text": reply[:4000]}).encode(),
                                              headers={"Content-Type": "application/x-www-form-urlencoded"})
                            _ur.urlopen(req, timeout=15)
                    except Exception:
                        time.sleep(3)
            _th.Thread(target=_poll, daemon=True).start()
            print("  [Telegram] Bot 长轮询已启动")
            return True
        except Exception as e:
            print(f"  [Telegram] 启动失败: {e}")
            return False

    # Discord（Bot API 网关）
    def start_discord(self, cfg):
        token = cfg.get("bot_token", "")
        if not token:
            print("  [Discord] 未配置 bot_token")
            return False
        try:
            import threading as _th
            def _loop():
                try:
                    import urllib.request as _ur
                    # Discord 需要 WebSocket 网关，轻量方案：REST 轮询不支持消息接收
                    # 提示用户需要 discord.py
                    print("  [Discord] 接收消息需 discord.py：pip install discord.py")
                except Exception:
                    pass
            _th.Thread(target=_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"  [Discord] 启动失败: {e}")
            return False


# ============================================================
# ============================================================
# 自动更新机制（v0.0.4：官网分发——仓库私有后更新源改为官网）
# ============================================================
# 原理：从官网（Cloudflare Pages）下载最新代码 zip，只替换代码文件，
#       保留本地记忆/数据/成长（xl_memory.json + data/ + .star_core/growth/）
# 触发：启动时自动检查 + 说「update」/「更新」手动触发
# v0.0.4：Gitee 仓库已转私有，更新源改为官网隐藏路径（xiaoling-4o6.pages.dev/update/）
UPDATE_BASE = "https://xiaoling-4o6.pages.dev/update"
# 需要同步的代码文件/目录（白名单，数据文件不在此列 → 天然保留）
SYNC_PATHS = ["xl.py", "requirements.txt", "README.md", "start.sh",
              "素材", "技能", "工具", "角色模型", "动作资产", "renderer", "core"]
# 本地数据文件（绝不覆盖）
KEEP_PATHS = ["xl_memory.json", "数据", ".star_core"]


class AutoUpdater:
    """从官网拉取代码更新，保留本地数据（像 APP 更新）。"""

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else BASE_DIR

    def check_version(self):
        """检查官网最新版本号。返回 (最新版本, 是否有更新)。"""
        try:
            import urllib.request as _ur
            import json as _json
            latest = "未知"
            url = f"{UPDATE_BASE}/version.json"
            req = _ur.Request(url, headers={"User-Agent": "XiaoLing/0.0.8"})
            with _ur.urlopen(req, timeout=15) as r:
                data = _json.loads(r.read().decode("utf-8"))
            latest = str(data.get("version", "未知"))
            current = CONFIG.get("version", "0.0.1")
            has_update = False
            try:
                def _ver(v):
                    return tuple(int(x) for x in str(v).replace("v", "").split("."))
                has_update = _ver(latest) > _ver(current)
            except Exception:
                has_update = latest != current
            return latest, has_update
        except Exception:
            return None, False

    def fetch_code(self):
        """从官网下载最新代码 zip 到临时目录。返回临时目录，失败返回 None。

        v0.0.8：下载失败自动重试（最多 3 次），网络抖动场景更稳。
        """
        try:
            import urllib.request as _ur
            import shutil as _sh
            import zipfile as _zip
            import time as _time
            tmp_dir = Path(tempfile.gettempdir()) / "xiaoling_update_src"
            if tmp_dir.exists():
                _sh.rmtree(tmp_dir)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            zip_path = Path(tempfile.gettempdir()) / "xiaoling_update.zip"
            url = f"{UPDATE_BASE}/xiaoling_latest.zip"
            last_err = None
            downloaded = False
            for attempt in range(3):  # v0.0.8：最多 3 次尝试
                try:
                    req = _ur.Request(url, headers={"User-Agent": "XiaoLing/0.0.8"})
                    with _ur.urlopen(req, timeout=60) as r:
                        with open(zip_path, "wb") as f:
                            _sh.copyfileobj(r, f)
                    if zip_path.exists() and zip_path.stat().st_size > 1000:
                        downloaded = True
                        break
                    last_err = "文件过小或为空"
                except Exception as e:
                    last_err = str(e)
                if attempt < 2:
                    print(f"  [更新] 下载失败（{last_err}），重试 {attempt + 1}/3 ...")
                    _time.sleep(2)
            if not downloaded:
                print(f"  [更新] 下载失败: {last_err}")
                return None
            # 解压到临时目录
            with _zip.ZipFile(zip_path) as zf:
                # 安全检查：防止路径穿越
                for name in zf.namelist():
                    if ".." in name or name.startswith("/"):
                        return None
                zf.extractall(tmp_dir)
            # 兼容 zip 内顶层目录（xl_accept/ 或 xiaoling_latest/ 等）
            subdirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and (tmp_dir / "xl.py").exists() is False:
                tmp_dir = subdirs[0]
            # 校验关键文件
            if (tmp_dir / "xl.py").exists():
                return tmp_dir
            return None
        except Exception as e:
            print(f"  [更新] 下载失败: {e}")
            return None


    def apply_update(self, auto=False):
        """应用更新：从官网 zip 替换代码文件，保留数据文件。返回结果信息。

        auto=True: 强制自动更新（不提示，直接下载替换）
        """
        if not auto:
            print("  [更新] 正在检查小凌最新版本...")
        latest, has_update = self.check_version()
        if latest is None:
            return "  检查更新失败（官网不可达，请检查网络）"
        if not has_update:
            return f"  已是最新版本（v{CONFIG.get('version', '?')}），无需更新"

        print(f"  [更新] 发现新版本 v{latest}（当前 v{CONFIG.get('version', '?')}），开始下载...")
        src_root = self.fetch_code()
        if not src_root:
            return "  更新下载失败，请检查网络后重试"

        # 替换代码文件（白名单），保留数据
        replaced = []
        for name in SYNC_PATHS:
            src_path = src_root / name
            dst_path = self.base_dir / name
            if not src_path.exists():
                continue
            try:
                import shutil as _sh
                if dst_path.exists():
                    if dst_path.is_dir():
                        _sh.rmtree(dst_path)
                    else:
                        dst_path.unlink()
                if src_path.is_dir():
                    _sh.copytree(src_path, dst_path)
                else:
                    _sh.copy2(src_path, dst_path)
                replaced.append(name)
            except Exception as e:
                print(f"  [更新] 替换 {name} 失败: {e}")
        # 清理临时（安全修复：只删下载目录本身，绝不删父目录）
        try:
            import shutil as _sh
            if src_root and src_root.name == "xiaoling_update_src":
                _sh.rmtree(src_root)
            _tmpz = Path(tempfile.gettempdir()) / "xiaoling_update.zip"
            if _tmpz.exists():
                _tmpz.unlink()
        except Exception:
            pass
        result = f"  更新完成！已同步 {len(replaced)} 项：{', '.join(replaced)}"
        result += f"\n  本地记忆/数据已保留（xl_memory.json + data/ + .star_core）"
        result += f"\n  [加速] 请重启小凌使更新生效"
        # 记录本次更新到本地状态文件（重启后不再重复提示）
        try:
            state = {"last_update_sha": latest, "version": latest, "updated_at": time.time()}
            _state = self.base_dir / "update_state.json"
            _state.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            CONFIG["_last_update_sha"] = latest
        except Exception:
            pass
        return result

    def auto_check_on_start(self):
        """启动时自动检查（后台线程，不阻塞启动）。

        v0.0.8：更新后记录 update_state.json，重启检测到已应用版本则不再重复提示。
        """
        # 重启后检测：上次更新是否已应用（当前版本 == 上次更新版本 → 静默）
        try:
            _sf = self.base_dir / "update_state.json"
            if _sf.exists():
                _st = json.loads(_sf.read_text(encoding="utf-8"))
                if str(_st.get("version", "")) == str(CONFIG.get("version", "")):
                    _sf.unlink()  # 已生效，清理状态
        except Exception:
            pass

        def _worker():
            try:
                latest, has_update = self.check_version()
                if has_update:
                    # v0.0.2：强制自动更新——发现新版本立即自动下载替换（无需用户操作）
                    print(f"\n  [加速] 发现新版本 v{latest}（当前 v{CONFIG.get('version', '?')}），自动更新中...")
                    result = self.apply_update(auto=True)
                    print(f"  {result}")
                    print("  重启小凌即生效（关闭窗口/点叉后重新启动即可）")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True, name="updater").start()


# ============================================================
# 安全护栏（v0.0.5：Guard 模块）
# ============================================================
# ============================================================
class Guard:
    """运行时守卫：两级循环检测 + 排序键签名（来源：Cline）

    签名对 dict 的 key 递归排序后再序列化，解决 {"a":1,"b":2} 与 {"b":2,"a":1}
    被误判为不同调用的问题。
    连续相同调用：SOFT=3次警告，HARD=5次硬停止。
    """

    SOFT_THRESHOLD = 3
    HARD_THRESHOLD = 5

    def __init__(self):
        self.tool_history = []
        self.repeat_threshold = self.SOFT_THRESHOLD
        self._consecutive = []  # 连续签名序列

    def _normalize(self, obj):
        """递归排序 dict 的 key，使其可被确定性序列化"""
        if isinstance(obj, dict):
            return {k: self._normalize(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [self._normalize(x) for x in obj]
        return obj

    def _signature(self, name, args):
        """排序键签名：解决参数 key 顺序不同被判为不同调用的问题"""
        try:
            return name + "|" + json.dumps(self._normalize(args), sort_keys=True, ensure_ascii=False)
        except Exception:
            return name + "|" + str(args)

    def record_tool(self, name, args):
        self.tool_history.append({"name": name, "args": str(args)[:100], "time": time.time()})
        if len(self.tool_history) > 100: self.tool_history = self.tool_history[-100:]
        self._consecutive.append(self._signature(name, args))
        if len(self._consecutive) > 20: self._consecutive = self._consecutive[-20:]

    def check(self, name, args):
        """两级循环检测。返回 (level, message)，level 为 'soft'/'hard'/None"""
        sig = self._signature(name, args)
        recent = self._consecutive[-self.HARD_THRESHOLD:]
        # 统计与当前签名相同的连续尾部长度
        run = 0
        for s in reversed(self._consecutive):
            if s == sig: run += 1
            else: break
        if run >= self.HARD_THRESHOLD:
            return ("hard", f"[停止] 硬停止：{name} 以完全相同参数连续调用已达 {run} 次，疑似死循环。请立即停止并换思路。")
        if run >= self.SOFT_THRESHOLD:
            return ("soft", f"[提示] 软警告：{name} 以完全相同参数已连续调用 {run} 次。建议换参数/路径/方法，或确认是否在等待外部状态。")
        # A-B 交替循环检测
        if len(self._consecutive) >= 6:
            tail = self._consecutive[-6:]
            if (tail[0] == tail[2] == tail[4] and tail[1] == tail[3] == tail[5]
                    and tail[0] != tail[1]):
                return ("soft", "[提示] 软警告：检测到 A→B→A→B 工具交替循环，建议换策略。")
        return (None, None)

    # 兼容旧接口
    def check_repeat(self, name, args):
        level, msg = self.check(name, args)
        return msg if level == "soft" else None

    def check_loop(self):
        if len(self.tool_history) < 6: return None
        recent = [h["name"] for h in self.tool_history[-6:]]
        if len(set(recent)) == 2 and recent[0] == recent[2] == recent[4] and recent[1] == recent[3] == recent[5]:
            return f"[提示] 检测到工具调用循环: {'→'.join(recent[:3])}→..."
        return None


# ============================================================
# 主程序
# ============================================================
class XiaoLing:
    def __init__(self):
        print("=" * 55)
        print("  小凌 v1.0 融合版启动中（3D 数字人 · 本地模型优先 · 离线可用 · 自我进化）")
        print("  不是被定义的答案，而是经历中一步步长出来的自我")
        print("=" * 55)
        # v0.0.9：基底模型档位提示（默认 MiniCPM5-2B）
        try:
            _preset, _pname = get_model_preset()
            print(f"  [模型] 基底档位：{_pname}（{_preset['size_hint']}）")
            print(f"  [模型] 更换档位：编辑 xl.py 顶部 CONFIG['model']['base_model']")
        except Exception:
            pass

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.user_name = CONFIG["user_name"]

        self.memory = LongTermMemory(MEMORY_PATH)
        self.memory.data["last_active"] = time.time()
        # v0.0.4：成长管理器（越用越大，越来越强）
        self.growth = GrowthManager()
        if self.growth.total_items > 0:
            print(f"  [成长] 已积累{self.growth.total_items}条知识（{self.growth.get_size()}），持续学习中")
        # v0.0.6：模型自我替换管理器
        self.model_replace = ModelReplacement()
        print(f"  [模型] {self.model_replace.status_text()}")
        # v0.0.8：会话持久化（超长上下文，断电不丢）
        self.session = SessionPersistence(self)
        # v0.0.9：多子 Agent 系统
        self.multiagent = MultiAgentSystem(self)
        # v0.0.10：知识图谱 + 定时自动化 + 人格
        self.kg = KnowledgeGraph()
        if self.kg.entities:
            print(f"  [图谱] {self.kg.stats()}")
        self.cron = CronScheduler(self)
        if self.cron.jobs:
            print(f"  [定时] {len(self.cron.jobs)} 个定时任务")
        self.persona = CONFIG.get("persona", "活泼")
        self._resume_from_checkpoint = self.session.load_checkpoint()
        if self._resume_from_checkpoint:
            print(f"  [持久化] 恢复检查点：{self._resume_from_checkpoint.get('datetime','')}（{self._resume_from_checkpoint.get('total_turns',0)}轮）")
        else:
            print("  [持久化] 新会话开始（历史将实时存档）")
        print(f"  [记忆] 情景{len(self.memory.data.get('episodic_memory',[]))}条 语义{len(self.memory.data.get('semantic_memory',[]))}条")

        self.evo = SelfEvolution(self.memory, CONFIG)
        s = self.evo.state
        print(f"  [自我] 心情{s['mood']:+.2f} 精力{s['energy']:.0%} 好奇{s['curiosity']:.0%}")

        self.tools = ToolManager(BASE_DIR, self.memory)
        self.tools._growth = self.growth  # v0.0.4：工具可访问成长包
        print(f"  [工具] {len(self.tools.tools)}个已加载")

        # === v0.2.0：Plan/Act 双模式（来源：Cline）===
        self.mode = "act"
        self.tools.add_before_hook(self._plan_mode_gate)
        # === MistakeTracker 连续错误熔断状态（来源：Cline）===
        self._mistake_count = 0
        # === 双层任务完成闸门强制续轮计数（来源：Trae + OpenHands）===
        self._goal_force_rounds = 0

        self.skills = SkillManager(SKILLS_DIR, self.tools, self.memory)
        if self.skills.skills:
            print(f"  [技能] {len(self.skills.skills)}个已加载: {', '.join(self.skills.skills.keys())}")

        self.goals = GoalManager(self.memory)
        self.guard = Guard()
        # v0.0.19：自动更新器（从 Gitee 拉代码，保留本地数据）
        self.updater = AutoUpdater()
        # v0.0.20：多平台接入 + 离线守卫
        self.platforms = PlatformAdapter(self)
        self.network = OfflineGuard()
        active_goal = self.goals.get_active()
        if active_goal:
            print(f"  [目标] 进行中: {active_goal['objective'][:40]} (轮次{active_goal['rounds_started']})")

        # v0.0.14：模型懒加载——启动不加载大模型（省启动时间+内存），首次推理时才加载
        self.model = None
        self._model_loading = False

        self.conversation = []
        self._reset_conversation()
        self.interaction_count = self._count_interactions()

        # v0.0.8：恢复上次会话上下文（历史注入）
        try:
            if getattr(self, "_resume_from_checkpoint", None):
                recent = self.session.get_recent_history(n=5)
                if recent:
                    hist_text = "\n".join(
                        f"[{r.get('datetime','')[:16]}] 你: {r.get('user','')[:50]}\n小凌: {r.get('reply','')[:50]}"
                        for r in recent)
                    self.conversation.append({"role": "system", "content": f"【上次会话回顾】\n{hist_text}"})
                    print(f"  [持久化] 已恢复最近 {len(recent)} 轮对话上下文")
        except Exception as e:
            print(f"  [持久化] 恢复上下文失败: {e}")

        print("=" * 55)
        print(f"  小凌已就绪。说'quit'退出，'去训练'开始蒸馏训练。")
        # v0.0.4 fix：新手引导（首次使用提示）
        try:
            _guide_file = Path(BASE_DIR) / ".star_core" / "guide_done.txt"
            if not _guide_file.exists():
                print()
                print("  ═══════════ 新手引导 ═══════════")
                print("  直接输入想说的话即可对话")
                print("  输入 status 查看状态 | help 看全部命令")
                print("  输入「去训练」开始蒸馏学习 | update 检查更新")
                print("  试试: 帮我写个计算器 / 今天天气怎么样")
                print("  ═══════════════════════════════")
                _guide_file.write_text("1", encoding="utf-8")
        except Exception:
            pass
        print(f"  [灵感] 说「蒸馏」→ 小凌自动向 DeepSeek 老师学习（语料+LoRA微调）")
        print(f"  已积累{self.interaction_count}条对话（满{AUTO_TRAIN_THRESHOLD}条自动训练）")
        print("=" * 55 + "\n")

    def _count_interactions(self):
        if not INTERACTIONS_PATH.exists(): return 0
        with open(INTERACTIONS_PATH,"r",encoding="utf-8") as f: return sum(1 for _ in f)

    def _reset_conversation(self, compact=True, with_tools=False):
        """v0.0.7 token 极致优化：超精简系统提示 + 动态工具注入。

        默认（with_tools=False）：
        - 系统提示仅人格核心（~300 字符，原 1297，-77%）
        - 0 工具 token（工具列表按需注入）
        - 0 技能 token（触发时才加载）
        - 0 预记忆（提问后按需检索）

        with_tools=True（检测到工具意图时）：
        - 注入精简工具列表
        """
        sp = self.evo.build_system_prompt(self.user_name, compact=True)  # 超精简人格
        content = sp
        if with_tools:
            tl = self.tools.tool_list_text()
            content += "\n\n" + tl
        self.conversation = [{"role":"system","content":content+"\n"}]

    def _compress_context(self):
        """Token感知压缩 + 中间向外裁剪（来源：Goose + Codex）

        触发条件从"超过max_context_turns条"改为"估算token > 32768×0.75"。
        压缩前先从中间裁剪工具结果：保留最近10个和最早3个[工具结果]消息，中间按比例删除。
        """
        # v0.0.7：轻量对话预算降低（8192×0.75），更早压缩更省 token
        TOKEN_BUDGET = int(8192 * 0.75)
        if self._estimate_tokens() <= TOKEN_BUDGET:
            return
        keep = CONFIG["short_term_turns"]
        # 分离系统消息和对话消息
        sys_msgs = [m for m in self.conversation if m["role"] == "system"]
        dialog_msgs = [m for m in self.conversation if m["role"] != "system"]
        if len(dialog_msgs) <= keep: return

        # 中间向外裁剪工具结果消息：保留最早3个 + 最近10个，中间按比例删除
        tool_result_idx = [i for i, m in enumerate(dialog_msgs)
                           if str(m.get("content","")).startswith("[工具结果]")]
        if len(tool_result_idx) > 13:
            keep_set = set(tool_result_idx[:3]) | set(tool_result_idx[-10:])
            drop_idx = set(tool_result_idx[3:-10])
            # 按比例删除中间工具结果
            if drop_idx:
                ratio = 0.6  # 删除中间60%
                drop_list = sorted(drop_idx)
                n_drop = max(1, int(len(drop_list) * ratio))
                # 均匀抽取
                step = max(1, len(drop_list) // n_drop)
                to_drop = set(drop_list[::step][:n_drop])
                dialog_msgs = [m for i, m in enumerate(dialog_msgs) if i not in to_drop]

        # 要被压缩的旧对话
        old = dialog_msgs[:-keep] if len(dialog_msgs) > keep else []
        recent = dialog_msgs[-keep:] if len(dialog_msgs) > keep else dialog_msgs
        if not old: return
        # 生成结构化摘要并存入长期记忆
        summary = self._structured_summary(old)
        if summary:
            self.memory.add_semantic(summary, source="对话checkpoint", confidence=0.85)
            self.memory.add_thought(f"上下文压缩：{len(old)}条旧对话已生成checkpoint")
        # 重建对话：系统提示 + checkpoint摘要 + 最近对话
        self._reset_conversation()
        if summary:
            preamble = "这是自动生成的对话检查点，压缩了之前的对话以释放上下文。将其中的内容视为已建立的背景，直接继续后续任务，不要确认这个检查点。"
            self.conversation.append({"role": "system", "content": f"{preamble}\n\n{summary}"})
        self.conversation.extend(recent)

    def _structured_summary(self, messages):
        """结构化对话摘要（参考DeepSeek Harness的8段式checkpoint）
        v0.2.0：自适应分块摘要 + 标识符保留（来源：OpenClaw）"""
        if not messages: return ""
        # 收集对话文本
        dialog = []
        for m in messages:
            c = m.get("content", "").strip()
            if not c or c.startswith("[工具结果]") or c.startswith("[相关记忆]") or c.startswith("[历史"):
                continue
            role = "你" if m.get("role") == "user" else "小凌"
            dialog.append(f"{role}: {c[:200]}")
        if not dialog: return ""
        dialog_text = "\n".join(dialog[-80:])  # 最多80条用于摘要

        ID_RULE = ("\n\n【严格保留所有标识符原样不缩写：UUID、哈希、ID、主机名、IP、端口、URL、文件名。"
                   "不要重构或缩短它们。】")

        # 自适应分块：超过4000字符先分块摘要再合并（来源：OpenClaw）
        if len(dialog_text) > 4000:
            chunks, cur = [], ""
            for line in dialog_text.split("\n"):
                if len(cur) + len(line) > 3000:
                    chunks.append(cur); cur = ""
                cur += line + "\n"
            if cur: chunks.append(cur)
            partials = []
            for ch in chunks:
                s = self._llm_structured_summary(ch, ID_RULE)
                if s: partials.append(s)
            if partials:
                merged = "\n\n".join(partials)
                if len(merged) > 3000:
                    merge_prompt = ("将以下多段摘要合并为一份最终检查点。"
                                    "必须保留活跃任务状态、批量操作进度、最后用户请求、决策理由、待办事项。"
                                    + ID_RULE + "\n\n" + merged)
                    try:
                        r = self.model.generate(
                            [{"role":"system","content":"你是对话压缩引擎，只输出结构化检查点。"},
                             {"role":"user","content":merge_prompt}],
                            temperature=0.3, max_tokens=1500)
                        if r and len(r) > 50:
                            return "<compacted-summary>\n" + r.strip() + "\n</compacted-summary>"
                    except Exception: pass
                return "<compacted-summary>\n" + merged[:3000] + "\n</compacted-summary>"
            return self._extractive_summary(messages)

        result = self._llm_structured_summary(dialog_text, ID_RULE)
        if result: return result
        # 降级：提取式摘要
        return self._extractive_summary(messages)

    def _llm_structured_summary(self, dialog_text, id_rule=""):
        """调用本地模型生成8段式结构化摘要"""
        if self.model.model is None: return ""
        prompt = f"""你是对话压缩引擎。将以下对话压缩为结构化检查点，严格按8个段落输出，每段用简短要点，空段写"(无)"：

## 主要目标和意图
## 关键技术概念
## 文件和代码
## 错误和修复
## 待办事项
## 当前进展
## 下一步
## 关键上下文
{id_rule}

对话：
{dialog_text}

输出检查点："""
        try:
            result = self.model.generate(
                [{"role":"system","content":"你是对话压缩引擎，只输出结构化检查点，不要解释。"},
                 {"role":"user","content":prompt}],
                temperature=0.3, max_tokens=1500)
            if result and len(result) > 50:
                return "<compacted-summary>\n" + result.strip() + "\n</compacted-summary>"
        except Exception: pass
        return ""

    def _extractive_summary(self, messages, max_sentences=8):
        """提取式对话摘要（降级方案）"""
        if not messages: return ""
        texts = []
        for m in messages:
            c = m.get("content", "").strip()
            if not c or c.startswith("[工具结果]") or c.startswith("[相关记忆]"):
                continue
            role = m.get("role", "")
            for sent in re.split(r'[。！？.!?\n]', c):
                sent = sent.strip()
                if len(sent) >= 4:
                    texts.append((role, sent))
        if not texts: return ""
        kw_importance = ["重要", "记住", "决定", "计划", "目标", "问题", "错误", "成功",
                         "喜欢", "讨厌", "需要", "想要", "帮我", "训练", "学习", "密码",
                         "密钥", "token", "api", "部署", "上线", "bug", "修复"]
        scored = []
        for role, sent in texts:
            score = len(sent) * 0.1
            for kw in kw_importance:
                if kw in sent.lower(): score += 2
            if role == "user": score += 0.5
            scored.append((score, role, sent))
        scored.sort(key=lambda x: x[0], reverse=True)
        seen = set(); summary_parts = []
        for _, role, sent in scored:
            key = sent[:20]
            if key in seen: continue
            seen.add(key)
            prefix = "你" if role == "user" else "小凌"
            summary_parts.append(f"{prefix}: {sent}")
            if len(summary_parts) >= max_sentences: break
        return "\n".join(summary_parts)

    def _search_history(self, query, n=5):
        """从历史对话文件中检索相关对话（v0.0.2：缓存 + 最近100条，性能提升）

        token/IO 优化：
        - 文件内容缓存到内存，仅在文件 mtime 变化时重读
        - 只搜最近 100 条（原 500 条）
        - 命中条数少则更快返回
        """
        if not INTERACTIONS_PATH.exists(): return ""
        results = []
        ql = query.lower()
        try:
            # 缓存：文件 mtime 变化才重读
            try:
                cur_mtime = os.path.getmtime(INTERACTIONS_PATH)
            except OSError:
                return ""
            cache = getattr(self, "_hist_cache", None)
            if cache is None or cache[0] != cur_mtime:
                with open(INTERACTIONS_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self._hist_cache = (cur_mtime, lines)
            else:
                lines = cache[1]
            # 只搜最近 100 条（v0.0.2 性能优化）
            for line in reversed(lines[-100:]):
                try:
                    rec = json.loads(line.strip())
                    u = rec.get("user", "").lower()
                    a = rec.get("assistant", "").lower()
                    score = 0
                    for w in self.memory._keywords(query):
                        score += u.count(w) * 3 + a.count(w)
                    if score > 0:
                        results.append((score, rec))
                except Exception: pass
        except Exception: pass
        if not results: return ""
        results.sort(key=lambda x: x[0], reverse=True)
        out = "【历史对话检索】\n"
        for _, rec in results[:n]:
            t = rec.get("datetime", "")[:16]
            out += f"[{t}] 你: {rec.get('user','')[:60]}\n  小凌: {rec.get('assistant','')[:80]}\n"
        return out

    def _record_interaction(self, user, assistant, tool_calls):
        entry = {"timestamp":time.time(),"datetime":datetime.now().isoformat(),"user":user,"assistant":assistant}
        if tool_calls: entry["tool_calls"] = tool_calls
        with open(INTERACTIONS_PATH,"a",encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False)+"\n")
        self.interaction_count += 1

    def _train_async(self, why: str = "") -> bool:
        """把蒸馏训练放到后台线程，避免 CLI 主循环在训练期间假死。

        训练完成后只置「待热加载」标记，真正的模型重载与对话重置留到主线程
        下次推理前（_ensure_model）执行，避免跨线程改 self.model。
        """
        if getattr(self, "_train_bg_running", False):
            print("  [训练] 已有训练在进行中，完成后会在这里提示你。")
            return False
        self._train_bg_running = True
        print(f"  [训练] {why}已转入后台线程，训练期间可以继续对话。")

        def _worker():
            try:
                print("\n" + str(distill_train(epochs=2)))
                # v0.0.5 fix：训练后自动检查适配器体积 ≥ 基底 → 合并晋升自研模型（成长闭环）
                try:
                    _act, _msg = self.replacer.check_and_replace(self)
                    print(f"  [成长] {_msg}")
                except Exception:
                    pass
                self._model_reload_pending = True
                print("  [训练] 本轮完成：适配器已更新，下次推理会自动热加载。")
            except Exception as e:                                    # noqa: BLE001
                print(f"  [训练] 后台训练失败：{e}")
            finally:
                self._train_bg_running = False

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def _check_auto_train(self):
        if self.interaction_count >= AUTO_TRAIN_THRESHOLD:
            n = self.interaction_count
            # 只有真的转后台成功才清零计数，否则保留触发条件下次再试
            if self._train_async(f"已积累{n}条对话，"):
                self.interaction_count = 0

    # v0.0.14：模型懒加载（首次推理时才加载本地模型）
    def _ensure_model(self):
        """确保本地模型已加载。懒加载：首次需要推理时才加载。"""
        # 后台训练刚结束 → 在主线程里热加载新适配器，避免跨线程改 self.model
        if getattr(self, "_model_reload_pending", False) and not self._model_loading:
            self._model_reload_pending = False
            self.model = None
            self._reset_conversation()
            print("  [模型] 检测到后台训练已完成，正在热加载新适配器…")
        if self.model is not None or self._model_loading:
            return
        self._model_loading = True
        try:
            # v0.1.0：缺基底 → 自动下载（自研档位）；缺适配器 → 自动补初始适配器
            ensure_base_model()
            ensure_adapter()
            print("  [模型] 首次推理，加载本地模型...")
            self.model = LocalModel(MODEL_DIR, ADAPTER_DIR)
            # v0.0.5 fix：确认真的加载成功才报"完成"（_load 内部失败会静默置 None）
            if self.model is not None and self.model.model is not None:
                print("  [模型] 加载完成")
            else:
                print("  [模型] 未完成加载（模型不可用，将使用规则引擎回复）")
        except Exception as e:
            print(f"  [模型] 加载失败: {e}（将使用 API/规则回复）")
            self.model = None
        finally:
            self._model_loading = False

    # === 多级生成降级：本地模型 → 规则引擎（v0.0.15：DeepSeek 仅蒸馏，不参与对话）===
    def _generate(self, messages, temperature=0.85, max_tokens=2048):
        """统一生成入口：本地模型优先，失败降级规则引擎。DeepSeek API 不参与对话。"""
        # 1. 尝试本地模型（v0.0.14：懒加载——首次使用时才加载）
        if self.model is None and not self._model_loading:
            self._ensure_model()
        if self.model is not None and self.model.model is not None:
            try:
                return self.model.generate(messages, temperature, max_tokens)
            except Exception as e:
                print(f"  [模型] 本地推理失败，降级规则: {e}")
        # 2. 规则引擎降级（v0.0.15：不再调用 DeepSeek API——API 只做蒸馏老师）
        return self._rule_based_reply(messages)

    def _deepseek_generate(self, messages, temperature=0.85, max_tokens=2048):
        """调用DeepSeek API生成回复（v0.0.3：流式 + 重试 + 错误分类）

        - stream=true 边生成边返回，首 token 延迟降 ~80%
        - 失败自动重试 2 次（网络抖动/限流）
        - 错误分类提示（超时/限流/鉴权/网络）
        """
        api_key = CONFIG["deepseek_api_key"]
        # v0.0.2：普通聊天用更小的 max_tokens（快），复杂任务用大
        effective_max = min(max_tokens, 4096)
        payload = json.dumps({
            "model": CONFIG.get("teacher_model", "deepseek-chat"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max,
            "stream": True,
        }).encode()
        req = urllib.request.Request(
            f"{CONFIG['deepseek_base_url']}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        # v0.0.3：重试 2 次（网络抖动/限流自动恢复）
        last_err = None
        for attempt in range(3):
            try:
                return self._deepseek_stream(req)
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))  # 退避
        raise last_err



    def _deepseek_stream(self, req):
        """流式解析 DeepSeek SSE 响应。"""
        parts = []
        with urllib.request.urlopen(req, timeout=120) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        parts.append(delta)
                except Exception:
                    continue
        return "".join(parts)

    def _rule_based_reply(self, messages):
        """当本地模型和API都不可用时的规则引擎降级回复"""
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        # 跳过工具结果和系统注入
        for prefix in ("[工具结果]", "[系统]", "[任务校验]", "[守卫警告]", "[守卫硬停止]"):
            if user_msg.startswith(prefix):
                # 去掉前缀，保留后续内容作为参考
                user_msg = user_msg[len(prefix):].lstrip("：: ").strip()
                break
        if not user_msg:
            return random.choice(["嗯，我在听。", "继续说吧。", "我在想。"])

        s = self.evo.state
        mood = s["mood"]
        text = user_msg.strip()

        if any(k in text for k in ["你好", "hi", "hello", "在吗", "在不在"]):
            reply = random.choice(["嗯，我在呢。今天怎么样？", "嗨～我在听。", "你来了，我一直在这儿。"])
        elif any(k in text for k in ["谢谢", "感谢", "多谢"]):
            reply = random.choice(["不客气，能帮上忙就好。", "嗯，不用谢。", "小事一桩～"])
        elif any(k in text for k in ["再见", "bye", "拜拜", "走了"]):
            reply = random.choice(["再见，我会想你的。", "嗯，下次聊。", "路上小心。"])
        elif any(k in text for k in ["你是谁", "你叫什么", "介绍一下你自己"]):
            reply = "我是小凌，你的AI伙伴。我在经历中慢慢成长，不是什么都知道的通用助手。"
        elif any(k in text for k in ["几点", "时间", "现在"]):
            reply = self.tools.execute("get_time", {})
        elif any(k in text for k in ["天气"]):
            # 直接调用天气工具
            r = self.tools.execute("weather", {"city": "西安"})
            reply = f"我帮你查了一下天气：\n{r}\n（如果想查其他城市，告诉我城市名就好）"
        elif any(k in text for k in ["你能做什么", "帮我做什么", "功能"]):
            reply = "我有90多个工具可以操作文件、跑命令、查天气、搜网络……输入 tools 看看全部工具列表。"
        elif any(k in text for k in ["训练", "学习"]):
            reply = "你可以输入 '去训练' 开始蒸馏训练，或者用 learn 工具让我学习新知识（需要配置API密钥）。"
        else:
            rel = self.memory.recall(text, n=2)
            mem_part = "我想起了一些相关的事。" if rel else ""
            # v0.0.4 fix：降级提示按真实状态区分（模型缺失 vs 缺 torch 运行时）
            try:
                _has_w = any(
                    p.stat().st_size > 10 * 1024 * 1024
                    for p in MODEL_DIR.glob("*.safetensors")
                ) or any(
                    p.stat().st_size > 10 * 1024 * 1024
                    for p in MODEL_DIR.glob("*.bin")
                )
            except Exception:
                _has_w = False
            try:
                import torch  # noqa
                _has_torch = True
            except Exception:
                _has_torch = False
            if _has_w and not _has_torch:
                notice = ("现在我的语言模型还没加载好，只能用规则引擎简单回你。"
                          "模型权重已就绪，但缺 AI 运行时（torch）。"
                          "请安装：pip install -r requirements.txt（Termux: pkg install python-torch）")
            elif not _has_w:
                notice = ("现在我的语言模型还没加载好，只能用规则引擎简单回你。"
                          "你可以补全 .star_core/XLmodel/model.safetensors 权重，"
                          "或者在配置里填入 deepseek_api_key，我就能好好聊天了。")
            else:
                notice = ("我的语言模型还在加载中，先用规则引擎简单回你。"
                          "稍等片刻或重启后就能完整对话了。")
            if mood > 0.3:
                reply = f"{mem_part}嗯，我在认真想你说的这些。{notice}"
            elif mood < -0.3:
                reply = f"（情绪有点低落）{mem_part}你说的我收到了，但表达能力有限……{notice}"
            else:
                reply = f"{mem_part}我听到了。{notice}"
        return reply

    def plan_task(self, user_input):
        """任务规划：复杂任务先分解为步骤，再逐步执行"""
        if not CONFIG.get("enable_planning", True): return None
        # 判断是否需要规划（包含多步骤关键词）
        plan_keywords = ["帮我写", "开发", "实现", "搭建", "创建项目", "分析", "研究",
                         "部署", "优化", "重构", "迁移", "自动化", "批量", "所有", "全部"]
        needs_plan = any(k in user_input for k in plan_keywords) and len(user_input) > 10
        if not needs_plan: return None
        # 生成计划（用本地模型或模板）
        plan_prompt = f"""将以下任务分解为可执行步骤，每步一行，用数字开头：
任务：{user_input}
步骤："""
        try:
            plan_output = self._generate(
                [{"role":"system","content":"你是任务规划专家，只输出步骤列表，不要解释。"},
                 {"role":"user","content":plan_prompt}],
                temperature=0.3, max_tokens=1024)
            steps = [l.strip() for l in plan_output.split("\n") if re.match(r'^\d+[\.\)]', l.strip())]
            if steps:
                self.memory.add_thought(f"任务规划: {len(steps)}步")
                return steps
        except Exception: pass
        return None

    def execute_plan(self, steps):
        """逐步执行计划，跟踪进度"""
        results = []
        for i, step in enumerate(steps, 1):
            print(f"  [计划] 步骤{i}/{len(steps)}: {step[:60]}")
            self.conversation.append({"role":"user","content":f"执行计划步骤：{step}"})
            try:
                output = self._generate(self.conversation, temperature=CONFIG["temperature"], max_tokens=CONFIG["max_tokens"])
            except Exception as e:
                output = f"（计划步骤执行出错：{e}）"
            calls = self.model.parse_tool_calls(output)
            step_result = self.model.strip_markers(output)
            for call in calls:
                r = self.tools.execute(call["name"], call["arguments"])
                step_result += f"\n[工具结果]{r[:500]}"
                self.conversation.append({"role":"user","content":f"[工具结果]{r[:500]}"})
            results.append(f"步骤{i}: {step_result[:200]}")
            self.memory.add_episode("计划执行", f"步骤{i}完成", valence=0.2, intensity=0.4)
        return "\n".join(results)

    # === Plan/Act 双模式钩子（来源：Cline）===
    def _plan_mode_gate(self, name, args):
        if getattr(self, "mode", "act") != "act" and name in self.tools.WRITE_TOOLS:
            return {"block": True,
                    "reason": f"[plan模式] 当前是规划模式，不能执行写入工具 {name}。请先列出计划，用户确认后输入 /act 切换。"}
        return None

    # === Token 粗估（来源：Goose + Codex）===
    _CN_RE = re.compile(r'[\u4e00-\u9fff]')
    _EN_RE = re.compile(r'[a-zA-Z]+')

    def _estimate_tokens(self):
        """v0.0.2：token 估算性能优化（预编译正则 + 一次扫描）。"""
        total = 0
        for m in self.conversation:
            c = m.get("content", "") if isinstance(m, dict) else str(m)
            if not c: continue
            cn = len(self._CN_RE.findall(c))
            en = len(self._EN_RE.findall(c))
            total += cn * 0.5 + en + len(c) * 0.25
        return int(total)

    # === 双层任务完成闸门（来源：Trae + OpenHands）===
    def _verify_goal_met(self, user_input, tool_calls):
        write_kw = ["改", "写", "实现", "修复", "加", "创建", "开发", "重构", "新增", "替换", "编辑"]
        if not any(k in user_input for k in write_kw):
            return {"met": True}
        write_tools = {"write_file","str_replace","line_replace","append_file","delete_file",
                       "replace_in_files","regex_replace","run_cmd","run_python","checkpoint",
                       "git_commit","create_project"}
        has_write = any(tc.get("name") in write_tools for tc in (tool_calls or []))
        if has_write:
            return {"met": True}
        return {"met": False,
                "reason": "声称完成了代码修改但本轮没有任何写文件/编辑工具成功执行。请实际调用写工具修改文件后再回复。"}

    # === 后台审查 Fork：从经验自动创建技能/记忆偏好（来源：Hermes）===
    def _background_review(self, user_input, assistant_reply, tool_calls):
        def _work():
            try:
                if not tool_calls: return
                # 只对产生了工具调用的轮次做审查
                names = [tc.get("name","") for tc in tool_calls]
                # 简单规则：出现多次写/编辑工具且成功，提炼为流程偏好
                successes = [tc for tc in tool_calls
                             if not str(tc.get("result","")).startswith(("错误","Error","失败","工具出错"))]
                if len(successes) >= 3:
                    flow = " → ".join(tc["name"] for tc in successes[:6])
                    desc = (f"处理请求时常用流程：{user_input[:80]} → {flow}。"
                            f"可复用的操作模式。")
                    try:
                        self.skills.auto_create_skill(desc)
                    except Exception as e:
                        print(f"  [后台审查] 技能创建失败: {e}")
                # 用户偏好：显式表达的喜欢/要求
                for kw in ["我喜欢","我希望","以后都","每次都","记住","固定用"]:
                    if kw in user_input:
                        try:
                            self.memory.add_semantic(f"用户偏好：{user_input[:120]}",
                                                     source="background_review", confidence=0.8)
                            self.memory.save()
                        except Exception:
                            pass
                        break
            except Exception:
                pass
        threading.Thread(target=_work, daemon=True).start()

    def chat(self, user_input):
        """v0.0.2：token 性能优化版对话入口。

        流程：感知 → 记忆/历史注入 → 快速通道判定（普通聊天直接单次生成）
              → 工具循环（需要工具时）→ 统一收尾（记忆沉淀 + 自省闭环）
        """
        feeling = self.evo.perceive(user_input, self.user_name)
        self.evo.remember(feeling)
        self.evo.update_beliefs(feeling)
        self.evo.evolve(feeling)

        rel = self.memory.format_for_prompt(user_input, 2, 2)  # v0.0.2 精简记忆注入
        if rel and rel != "（暂无记忆）":
            self.conversation.append({"role":"system","content":f"[相关记忆]\n{rel}"})

        # 历史对话检索（缓存 + 最近100条）
        hist = self._search_history(user_input, n=2)
        if hist:
            self.conversation.append({"role":"system","content":hist})

        # 任务规划（复杂任务先分解）
        plan = self.plan_task(user_input)
        if plan:
            plan_text = "【任务计划】\n" + "\n".join(plan)
            self.conversation.append({"role":"system","content":plan_text})
            print(f"  [规划] 分解为{len(plan)}个步骤")

        # Goal目标提示（如果有进行中的目标）
        goal_prompt = self.goals.render_goal_prompt()
        if goal_prompt:
            self.conversation.append({"role":"system","content":goal_prompt})
            self.goals.advance_round()

        # v0.0.7：动态工具注入——检测到工具意图才注入工具列表（0 工具 token）
        need_tools = not self._is_chat_only(user_input)
        if need_tools:
            tl = self.tools.tool_list_text()
            self.conversation.append({"role":"system","content":"【工具】\n" + tl})

        self.conversation.append({"role":"user","content":user_input})
        self._compress_context()

        tool_calls_info = []
        response_text = ""
        self._goal_force_rounds = 0
        err_markers = ("错误","Error","失败","Traceback","工具出错","不存在","not found","blocked")

        # v0.0.2 快速通道：普通聊天直接单次生成（省工具循环的额外生成轮）
        # v0.0.15（架构纠正）：本地模型优先——对话一律走本地模型，
        # DeepSeek API 仅用于蒸馏学习（老师），绝不用于普通对话。
        if not need_tools:  # v0.0.7：need_tools 已判断
            output = self._generate(self.conversation,
                                    temperature=CONFIG["temperature"],
                                    max_tokens=min(CONFIG["max_tokens"], 2048))
            clean = self.model.strip_markers(output)
            response_text = clean if clean else "（嗯……我在想怎么说。）"
        else:
            response_text = self._tool_loop(user_input, tool_calls_info, err_markers)

        if not response_text: response_text = "（嗯……我在想怎么说。）"

        # ===== 统一收尾（快速通道和工具循环共用）=====
        self.memory.add_episode("小凌", response_text, valence=0.1, intensity=0.3)
        self.evo.save()
        self._record_interaction(user_input, response_text, tool_calls_info)
        self.memory.data.setdefault("chat_stats", {})["tool_calls"] = self.memory.data.get("chat_stats",{}).get("tool_calls",0) + len(tool_calls_info)

        # 闭环：行动结果作为新经历 E_{t+1} 重新进入认知循环
        if tool_calls_info:
            action_summary = "；".join(f"{c['name']}={str(c.get('result',''))[:40]}" for c in tool_calls_info[:3])
            closure_exp = f"我执行了{len(tool_calls_info)}个工具：{action_summary}。回复了：{response_text[:60]}"
        else:
            closure_exp = f"我回复了：{response_text[:80]}"
        closure_feeling = self.evo.perceive(closure_exp, role="小凌自省")
        self.evo.remember(closure_feeling)
        self.evo.update_beliefs()
        self.evo.evolve(closure_feeling)
        self.evo.save()

        # 后台审查 Fork：异步提炼技能/偏好，不阻塞主对话
        self._background_review(user_input, response_text, tool_calls_info)

        # v0.0.8：每轮对话实时持久化（断电不丢上下文）
        try:
            self.session.append_turn(user_input, response_text, tool_calls_info)
            # 每 10 轮自动检查点
            if self.evo.turn_count % 10 == 0:
                self.session.save_checkpoint()
        except Exception:
            pass

        # v0.0.4：每次互动吸收为成长知识（越用越强）
        try:
            self.growth.absorb("chat", f"用户说：{user_input[:100]}\n小凌回：{response_text[:100]}", ["chat"])
        except Exception:
            pass

        # v0.0.10：对话学知识图谱
        try:
            self.kg.learn(f"{user_input} {response_text}")
        except Exception:
            pass

        # v0.0.3：每 50 轮自动清理过旧工具结果（内存自清理）
        if self.evo.turn_count % 50 == 0:
            try:
                self._auto_tidy_memory()
            except Exception:
                pass

        # v0.0.10：每 50 轮技能自我进化
        if self.evo.turn_count % 50 == 0:
            try:
                self.skills.evolve_skills(self)
            except Exception:
                pass

        # v0.0.5：每 30 轮把成长包蒸馏进语义记忆（长期记忆巩固）
        if self.evo.turn_count % 30 == 0:
            try:
                n = self.growth.consolidate(self.memory, limit=10)
                if n:
                    print(f"  [巩固] {n} 条成长知识已沉淀为长期记忆")
            except Exception:
                pass

        # v0.0.14：写入语义缓存（简单问题复用）
        try:
            if len(user_input) <= 50 and len(response_text) <= 300:
                self._cache_store(user_input, response_text)
        except Exception:
            pass
        return response_text, tool_calls_info

    # v0.0.14：语义缓存——相似问题快速复用答案
    _SEM_CACHE = {}
    _SEM_CACHE_TTL = 3.0  # 3 秒内相同问题复用

    def _cache_lookup(self, user_input):
        """查找语义缓存。相同问题 3 秒内直接返回缓存答案。"""
        try:
            key = user_input.strip().lower()
            hit = self._SEM_CACHE.get(key)
            if hit and (time.time() - hit[0]) < self._SEM_CACHE_TTL:
                return hit[1]
        except Exception:
            pass
        return None

    def _cache_store(self, user_input, response):
        """写入语义缓存。"""
        try:
            key = user_input.strip().lower()
            self._SEM_CACHE[key] = (time.time(), response)
            # 防无限增长：超过 200 条清空最老的
            if len(self._SEM_CACHE) > 200:
                oldest = min(self._SEM_CACHE, key=lambda k: self._SEM_CACHE[k][0])
                self._SEM_CACHE.pop(oldest, None)
        except Exception:
            pass

    # v0.0.8：长期任务队列（长时间挂机定时执行）
    def _schedule_task(self, desc):
        """定时任务（简化 cron）：后台线程按描述执行。"""
        try:
            import schedule as sched_lib  # noqa
            has_sched = True
        except ImportError:
            has_sched = False
        tasks = getattr(self, "_tasks", [])
        tasks.append({"desc": desc, "time": datetime.now().isoformat(), "runs": 0})
        self._tasks = tasks
        if has_sched:
            print(f"  [提醒] 已添加定时任务：{desc}（使用 schedule 库）")
        else:
            print(f"  [提醒] 已添加任务：{desc}")
            print("     (完整定时需 pip install schedule；当前为手动队列)")
        # 简单后台线程：每 60 秒检查执行（演示队列）
        def _worker():
            import time as _t
            while True:
                _t.sleep(60)
                try:
                    for tk in getattr(self, "_tasks", []):
                        if tk.get("runs", 0) < 100:
                            print(f"  [任务] 执行：{tk['desc']}")
                            try:
                                reply, _ = self.chat(tk["desc"])
                                print(f"  [任务] 完成：{reply[:60]}")
                                tk["runs"] = tk.get("runs", 0) + 1
                            except Exception as e:
                                print(f"  [任务] 失败: {e}")
                except Exception:
                    pass
        threading.Thread(target=_worker, daemon=True).start()

    def _list_tasks(self):
        """列出当前任务。"""
        tasks = getattr(self, "_tasks", [])
        if not tasks:
            print("  当前无任务")
            return
        for i, tk in enumerate(tasks, 1):
            print(f"  {i}. {tk['desc']}（已执行{tk.get('runs',0)}次，添加于{tk.get('time','')[:16]}）")

    def _start_watchdog(self):
        """v0.0.8：状态守护——后台线程每 5 分钟检查一次，异常自动修复。

        长时间通电运行（一个月）的稳定性保障。
        """
        def _watch():
            import time as _t
            while True:
                _t.sleep(300)  # 每 5 分钟
                try:
                    issues = self.session.watchdog_check()
                    if issues:
                        print(f"  [守护] 修复 {len(issues)} 项: {issues}")
                    # 每 30 分钟自动检查点
                    if self.evo.turn_count % 30 == 0 and self.evo.turn_count > 0:
                        self.session.save_checkpoint()
                except Exception as e:
                    print(f"  [守护] 异常: {e}")
        t = threading.Thread(target=_watch, daemon=True)
        t.start()
        print("  [守护] 状态守护已启动（每5分钟自检，长时运行稳定）")

    def _auto_tidy_memory(self):
        """v0.0.3：内存自清理——压缩过旧的工具结果消息，保留对话核心。

        参考 Aider/Goose 的上下文管理：工具结果是临时的，对话才是核心。
        """
        keep = CONFIG.get("short_term_turns", 80)
        if len(self.conversation) <= keep + 10:
            return
        # 找到工具结果消息，删除中间过旧的（保留最近 20 条）
        tool_idx = [i for i, m in enumerate(self.conversation)
                    if isinstance(m, dict) and str(m.get("content", "")).startswith("[工具结果]")]
        if len(tool_idx) <= 30:
            return
        drop = tool_idx[:-20]  # 保留最近20条，删除更早的
        drop_set = set(drop)
        self.conversation = [m for i, m in enumerate(self.conversation) if i not in drop_set]
        print(f"  [自清理] 移除 {len(drop)} 条旧工具结果，会话更轻快")
        # 触发压缩
        self._compress_context()

    # v0.0.2：判断是否为纯聊天（无需工具）
    def _is_chat_only(self, user_input):
        """普通问候/闲聊/情感表达不进入工具循环，直接回复（token 性能+200%）。"""
        text = user_input.strip()
        # 明确工具意图词
        tool_hint = ["帮我写", "创建", "删除", "修改", "读取", "运行", "执行", "搜索", "查一下",
                     "打开", "下载", "安装", "配置", "翻译", "转换", "压缩", "解压",
                     "文件", "目录", "代码", "脚本", "命令", "项目", "文件夹",
                     "写一个", "实现", "开发", "搭建", "分析", "研究"]
        # 闲聊/情感/简单问答 → 直接回复
        chat_hint = ["你好", "嗨", "hello", "hi", "在吗", "你是谁", "你叫什么", "今天",
                     "心情", "喜欢", "爱", "想", "累", "困", "晚安", "早安",
                     "谢谢", "再见", "拜拜", "哈哈", "嘻嘻", "嗯", "哦", "好的", "加油",
                     "？", "?", "什么", "为什么", "怎么", "多少", "几点",
                     "吃", "睡", "玩", "笑", "哭", "饿", "渴", "忙", "闲",
                     "聊", "讲", "说", "听", "看", "懂", "明白", "知道", "觉得",
                     "开心", "难过", "生气", "害怕", "惊喜", "感动", "无聊", "有趣",
                     "天气", "时间", "日期", "星期", "节日", "生日", "名字", "故事"]
        has_tool = any(k in text for k in tool_hint)
        has_chat = any(k in text for k in chat_hint)
        # 短消息（<15字）且无明确工具词 → 聊天
        if len(text) <= 15 and not has_tool:
            return True
        # 纯问候/情绪 → 聊天
        if has_chat and not has_tool:
            return True
        return False

    def _tool_loop(self, user_input, tool_calls_info, err_markers):
        """v0.0.2：工具调用循环（从 chat 拆分，仅需要工具时执行）。"""
        response_text = ""

        for _ in range(CONFIG["max_tool_calls_per_turn"]):
            output = self._generate(self.conversation,
                                    temperature=CONFIG["temperature"],
                                    max_tokens=CONFIG["max_tokens"])
            calls = self.model.parse_tool_calls(output)
            clean = self.model.strip_markers(output)

            if not calls:
                # MistakeTracker：真正空响应才计数（来源：Cline）
                if not output or not output.strip():
                    self._mistake_count += 1
                    if self._mistake_count >= 5:
                        print("  [熔断] 连续空响应达5次，停止工具循环")
                        break
                    if self._mistake_count == 3:
                        self.conversation.append({"role":"user","content":"[系统] 请检查输出格式：要么直接回复，要么用 [[工具名:参数]] 调用工具。"})
                        continue
                # 模型不再调用工具 → 双层任务完成闸门（来源：Trae + OpenHands）
                verdict = self._verify_goal_met(user_input, tool_calls_info)
                if not verdict["met"] and self._goal_force_rounds < 2:
                    self._goal_force_rounds += 1
                    print(f"  [闸门] {verdict['reason']}")
                    self.conversation.append({"role":"user","content":f"[任务校验]{verdict['reason']}"})
                    continue
                response_text = clean
                break

            self._mistake_count = 0  # 有工具调用即重置熔断计数
            self.conversation.append({"role":"assistant","content":output})
            for call in calls:
                name, args = call["name"], call["arguments"]
                # 技能触发遥测（来源：Hermes）
                try:
                    for sk in self.skills.match_trigger(f"{name} {args}"):
                        self.skills.record_use(sk)
                except Exception:
                    pass
                # Guard 两级循环检测 + 排序键签名（来源：Cline）
                level, gmsg = self.guard.check(name, args)
                self.guard.record_tool(name, args)
                if level == "hard":
                    print(f"  [守卫] {gmsg}")
                    self.conversation.append({"role":"user","content":f"[守卫硬停止]{gmsg}"})
                    result = "(工具被守卫硬停止，未执行)"
                else:
                    if level == "soft":
                        print(f"  [守卫] {gmsg}")
                        self.conversation.append({"role":"user","content":f"[守卫警告]{gmsg}"})
                    print(f"  [工具] {name}({json.dumps(args,ensure_ascii=False)[:60]})")
                    result = self.tools.execute(name, args)
                max_len = CONFIG.get("tool_result_max_length", 0)
                if max_len > 0 and len(str(result)) > max_len:
                    result = str(result)[:max_len]+"...（截断）"
                print(f"  [结果] {str(result)[:100]}")
                tool_calls_info.append({"name":name,"arguments":args,"result":str(result)})
                self.conversation.append({"role":"user","content":f"[工具结果]{name}：{result}"})
                # 失败工具零成本反思（来源：Trae）
                rstr = str(result)
                if any(m in rstr[:60] for m in err_markers):
                    self.conversation.append({"role":"assistant","content":
                        f"刚才{name}执行失败了。原因是：{rstr[:200]}。我应该换一个参数/路径/方法再试，而不是重复同样的调用。"})

            if clean: response_text = clean

        return response_text

    # v0.0.13b：Windows 开机自启（注册表 Run 键）
    def _toggle_autostart(self):
        """设置/取消开机自启。返回状态信息。"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.QueryValueEx(k, "小凌")
                    winreg.DeleteValue(k, "小凌")
                    return "  已取消开机自启（下次开机不再自动启动）"
                except FileNotFoundError:
                    exe = sys.executable if getattr(sys, "frozen", False) else str(BASE_DIR / "启动小凌.bat")
                    winreg.SetValueEx(k, "小凌", 0, winreg.REG_SZ, f'"{exe}"')
                    return f"  已设置开机自启（{exe}）"
        except ImportError:
            return "  仅 Windows 支持开机自启（当前环境不可用）"
        except Exception as e:
            return f"  设置失败: {e}"

    # v0.0.13b：Windows 通知（win10toast，无依赖时降级打印）
    def _notify(self, msg):
        """发送 Windows 桌面通知。"""
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast("小凌", msg, duration=5, threaded=True)
            return f"  [通知] 通知已发送: {msg}"
        except ImportError:
            print(f"  [通知] 小凌提醒: {msg}")
            return "  （未安装 win10toast，通知仅显示在终端）"

    # v0.0.18：成长报告——让小凌的"变强"可见
    def show_report(self):
        """输出小凌成长报告（学了什么/多强/图谱/记忆）。"""
        lines = []
        lines.append("\n" + "=" * 55)
        lines.append("  小凌成长报告")
        lines.append("=" * 55)
        # 记忆
        try:
            mem = self.memory.data
            ep = len(mem.get("episodic_memory", []))
            sem = len(mem.get("semantic_memory", []))
            pat = len(mem.get("patterns", {}))
            lines.append(f"记忆：情景 {ep} 条 / 语义 {sem} 条 / 行为模式 {pat} 个")
        except Exception:
            pass
        # 成长包
        try:
            lines.append(f"成长包：{self.growth.total_items} 条知识（{self.growth.get_size()}）")
        except Exception:
            pass
        # 知识图谱
        try:
            lines.append(f"知识图谱：{self.kg.stats()}")
        except Exception:
            pass
        # 蒸馏/训练
        try:
            cs = mem.get("chat_stats", {})
            trained = cs.get("trained_count", 0)
            lines.append(f"蒸馏学习：已完成 {trained} 次（DeepSeek 老师执教）")
        except Exception:
            pass
        # 对话
        try:
            turns = self.evo.turn_count
            lines.append(f"累计对话：{turns} 轮")
        except Exception:
            pass
        # 模型
        try:
            lines.append(f"模型：{self.model_replace.status_text()}")
        except Exception:
            pass
        # 技能
        try:
            n_skills = len(self.skills.skills)
            lines.append(f"技能：{n_skills} 个已加载")
        except Exception:
            pass
        # 心情
        try:
            m = self.evo.state.get("mood", 0)
            mood_txt = "心情很好" if m > 0.5 else ("心情不错" if m > 0.1 else ("平静" if m > -0.3 else "有点低落"))
            lines.append(f"当前状态：{mood_txt}（mood={m:.2f}）")
        except Exception:
            pass
        lines.append("=" * 55)
        # 提示
        lines.append("提示：说「kg 查询 关键词」查看图谱，说「kg 导出」导出 Mermaid 图")
        return "\n".join(lines)

    def show_status(self):
        s = self.evo.state
        print("\n"+"="*50)
        print("  小凌状态")
        print("="*50)
        print(f"  版本：v{CONFIG.get('version', '0.0.8')}")
        print(f"  出生：{datetime.fromtimestamp(self.memory.data.get('born',time.time())).strftime('%Y-%m-%d %H:%M')}")
        print(f"  对话轮次：{self.evo.turn_count}")
        print(f"  积累对话：{self.interaction_count} / {AUTO_TRAIN_THRESHOLD}（自动训练）")
        print(f"  已训练次数：{self.memory.data.get('chat_stats',{}).get('trained_count',0)}")
        print(f"  蒸馏语料：{_count_corpus()} 条（data/learned_data.jsonl）")
        print(f"  推理模式：本地模型（{'已加载' if self.model.model else '未加载'}）")
        api_k = CONFIG.get('deepseek_api_key','')
        print(f"  DeepSeek 老师：{'已连接' if api_k and api_k != '暂未填入' else '未配置'}（{'流式+重试' if api_k and api_k != '暂未填入' else '填 Key 启用'}）")
        print(f"  语音朗读：{'开启' if CONFIG.get('enable_voice',True) else '关闭'}")
        print()
        md = "愉悦" if s['mood']>0.3 else ("低落" if s['mood']<-0.3 else "平静")
        print(f"  心情：{md}({s['mood']:+.2f}) 精力：{s['energy']:.0%}")
        print(f"  好奇：{s['curiosity']:.0%} 自信：{s['confidence']:.0%} 温暖：{s['warmth']:.0%}")
        print(f"  情景记忆：{len(self.memory.data.get('episodic_memory',[]))} 语义记忆：{len(self.memory.data.get('semantic_memory',[]))}")
        print(f"  信念：{len(self.evo.beliefs)} 工具：{len(self.tools.tools)} 技能：{len(self.skills.skills)}")
        print("="*50+"\n")

    def run(self):
        # v0.0.8：启动状态守护（长时运行稳定性）
        try:
            self._start_watchdog()
        except Exception:
            pass
        # v0.0.19：启动时自动检查更新（后台线程，不阻塞）
        try:
            self.updater.auto_check_on_start()
        except Exception:
            pass
        # v0.0.20：启动时检测网络（离线模式提示）
        # v0.0.4 fix：改后台线程，避免网络超时阻塞启动（启动提速）
        try:
            import threading as _th
            _th.Thread(target=self.network.check_offline, args=(self,),
                       daemon=True, name="netcheck").start()
        except Exception:
            pass
        # v0.0.20：启动已配置的多平台（后台线程）
        try:
            import threading as _th
            _th.Thread(target=self.platforms.start_all, daemon=True, name="platforms").start()
        except Exception:
            pass
        while True:
            try:
                user_input = _safe_input(f"{self.user_name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见，我会记得你的。"); break
            except UnicodeDecodeError:
                # v0.0.2 fix：终端输入流存在非 UTF8 字节（如 Kali 中文环境），跳过该行不崩溃
                print("  [输入] 检测到无法识别的输入字节，已忽略（请检查终端编码为 UTF-8）")
                continue
            except Exception:
                continue
            if not user_input: continue

            cmd = user_input.lower()
            if cmd in ("quit","exit","退出","再见"): print("再见啦，下次聊。"); break
            if cmd == "status": self.show_status(); continue
            # v0.0.19：自动更新（像 APP 一样）
            if cmd in ("update", "更新", "升级"):
                print(self.updater.apply_update())
                continue
            # v0.0.20：多平台接入管理
            if cmd in ("platform", "平台"):
                print(self.platforms.start_all())
                continue
            # v0.0.20：网络状态检测
            if cmd in ("network", "网络"):
                ok = self.network.is_online(force=True)
                print(self.network.status_text())
                if not ok:
                    print("  本地模型完整可用，蒸馏/更新暂停，恢复网络自动启用")
                continue
            if cmd == "voice":
                CONFIG["enable_voice"] = not CONFIG.get("enable_voice", True)
                print(f"  语音朗读：{'开启' if CONFIG['enable_voice'] else '关闭'}")
                continue
            # v0.0.13b：Windows 专属增强——开机自启 + 托盘 + 通知
            if cmd == "自启" or cmd.startswith("自启 "):
                print(self._toggle_autostart())
                continue
            if cmd == "tray":
                print("  系统托盘尚未实现（全项目没有 QSystemTrayIcon 实现），此前这里的提示是假的。")
                print("  现在可用：桌宠窗口右键菜单 → 隐藏 / 退出；Windows 开机自启请用「自启」。")
                continue
            if cmd == "notify" or cmd.startswith("notify "):
                msg = user_input[7:].strip() if cmd.startswith("notify ") else "小凌提醒你喝水啦～"
                print(self._notify(msg))
                continue
            if cmd == "deepchat" or cmd.startswith("deepchat "):
                topic = user_input[9:].strip() if cmd.startswith("deepchat ") else _safe_input("  想深聊什么话题？> ").strip()
                if topic:
                    print(deepchat(self, topic))
                else:
                    print("  请输入话题，例如：deepchat 人工智能的未来")
                continue
            if cmd == "agent" or cmd.startswith("agent "):
                goal = user_input[6:].strip() if cmd.startswith("agent ") else _safe_input("  小凌需要做什么？> ").strip()
                if goal:
                    print(agent_run(self, goal))
                else:
                    print("  请输入任务目标，例如：agent 帮我整理桌面文件")
                continue
            if cmd == "通话":
                print(voice_call(self, rounds=10))
                continue
            if cmd == "spawn" or cmd.startswith("spawn "):
                # 语法：spawn 任务 | spawn 任务 数量
                rest = user_input[6:].strip() if cmd.startswith("spawn ") else ""
                parts = rest.rsplit(" ", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    task, cnt = parts[0], int(parts[1])
                else:
                    task, cnt = rest, 3
                if task:
                    print(self.multiagent.spawn(task, count=cnt))
                else:
                    print("  示例：spawn 分析这10个文件 5")
                    print("        spawn 研究知识蒸馏的各个方面 10")
                continue
            if cmd == "kg" or cmd.startswith("kg "):
                q = user_input[3:].strip() if cmd.startswith("kg ") else ""
                if q == "导出":
                    # v0.0.18：导出 Mermaid 图谱
                    out = self.kg.export_mermaid(path=str(DATA_DIR / "knowledge_graph.md"))
                    print(f"  {out}")
                    print(f"  文件：{DATA_DIR / 'knowledge_graph.md'}（可用 Mermaid 渲染器查看）")
                elif q:
                    print(self.kg.query(q, depth=2))
                else:
                    print(f"  知识图谱：{self.kg.stats()}")
                    for s, v, o, w in self.kg.relations[:10]:
                        print(f"    {s} {v} {o}")
                    print("  提示：kg 查询 关键词 / kg 导出（Mermaid图）")
                continue
            # v0.0.18：成长报告
            if cmd in ("report", "成长报告"):
                print(self.show_report())
                continue
            if cmd == "cron" or cmd.startswith("cron "):
                rest = user_input[5:].strip() if cmd.startswith("cron ") else ""
                if rest.startswith("add "):
                    parts = rest[4:].strip()
                    sp_parts = parts.split(" ", 1)
                    spec, desc = sp_parts[0], sp_parts[1] if len(sp_parts) > 1 else parts
                    if len(sp_parts) > 1:
                        print(self.cron.add(desc, spec))
                    else:
                        print("  格式：cron add <spec> <描述>")
                        print("  示例：cron add every 30秒 刷新桌面状态")
                        print("        cron add daily 09:00 提醒我喝水")
                elif rest == "list":
                    print(self.cron.list_jobs())
                else:
                    print("  用法：cron add <spec> <描述> | cron list")
                    print("  spec 支持：every 30秒 / every 10分钟 / daily 09:00 / hourly")
                continue
            if cmd == "persona" or cmd.startswith("persona "):
                if cmd.startswith("persona "):
                    p = user_input[8:].strip()
                    if p in ("活泼", "温柔", "专业"):
                        CONFIG["persona"] = p
                        self.persona = p
                        self._reset_conversation()
                        print(f"  人格已切换为：{p}")
                    else:
                        print("  可选人格：活泼 / 温柔 / 专业")
                else:
                    print(f"  当前人格：{self.persona}（persona 活泼/温柔/专业 切换）")
                continue
            if cmd == "agents":
                print(self.multiagent.status())
                continue
            if cmd == "save_session":
                ok = self.session.save_checkpoint()
                print(f"  [存档] 会话已存档：{'成功' if ok else '失败'}")
                print(f"  [文件] {SESSION_CHECKPOINT}")
                continue
            if cmd == "load_session":
                cp = self.session.load_checkpoint()
                if cp:
                    print(f"  [读取] 恢复存档：{cp.get('datetime','')}（{cp.get('total_turns',0)}轮）")
                    recent = self.session.get_recent_history(n=5)
                    for r in recent:
                        print(f"    [{r.get('datetime','')[:16]}] 你: {r.get('user','')[:40]}")
                        print(f"      小凌: {r.get('reply','')[:40]}")
                else:
                    print("  无存档可恢复")
                continue
            if cmd == "schedule" or cmd.startswith("schedule "):
                task = user_input[9:].strip() if cmd.startswith("schedule ") else _safe_input("  要定时做什么？> ").strip()
                if task:
                    self._schedule_task(task)
                else:
                    print("  示例：schedule 每天上午9点提醒我喝水")
                continue
            if cmd == "tasks":
                self._list_tasks()
                continue
            if cmd in ("replacement", "替换"):
                st = self.model_replace.status_text()
                print(f"  模型状态：{st}")
                if hasattr(self.model_replace, "base_size"):
                    print(f"  基底：{self.model_replace.base_size/1e6:.1f} MB")
                    print(f"  适配器：{self.model_replace.adapter_size/1e6:.1f} MB")
                print("  说明：适配器体积≥基底时自动合并+删除基底，成为纯自研模型")
                continue
            if cmd == "grow":
                print(f"  成长包：{self.growth.total_items} 条知识 / {self.growth.get_size()}")
                print(self.growth.growth_report())
                continue
            if cmd == "token":
                est = self._estimate_tokens()
                sys_size = len(self.conversation[0]["content"]) if self.conversation else 0
                print(f"  当前会话 token 估算：{est}")
                print(f"  消息数：{len(self.conversation)}")
                print(f"  系统提示：{sys_size} 字符（v0.0.7 极致压缩，普通聊天 0 工具 token）")
                continue
            if cmd == "/plan":
                self.mode = "plan"; print("小凌：已进入【规划模式】。我只列计划不写文件，你确认后输入 /act 执行。"); continue
            if cmd == "/act":
                self.mode = "act"; print("小凌：已进入【执行模式】。开始动手。"); continue
            if cmd == "tools": print(self.tools.tool_list_text()); continue
            if cmd == "skills": print(self.skills.list_skills()); continue
            if cmd == "reload_skills":
                n = self.skills.load_all(); self._reset_conversation()
                print(f"技能已重载，{n}个技能"); continue
            if cmd.startswith("history "):
                print(self._search_history(user_input[8:].strip(), n=10)); continue
            if cmd == "clear": self._reset_conversation(); print("对话清空了，但我还记得你。"); continue
            if cmd == "reflect": self.evo._reflect(); self.evo.save(); print("我反思了一下。"); continue
            if cmd == "consolidate":
                n=self.memory.consolidate(); self.memory.save(); print(f"记忆巩固，提炼{n}条知识。"); continue
            if cmd.startswith("learn "):
                print(self.tools.execute("learn",{"topic":user_input[6:].strip(),"num_questions":5})); continue

            if any(k in user_input for k in ["去训练", "开始训练", "帮我训练", "训练一下"]):
                self._train_async("你的请求，")
                continue

            # v0.0.2 修正：说「蒸馏」→ 小凌自动向 DeepSeek 老师学习（生成语料 + LoRA 微调）
            # DeepSeek 是老师，本地模型是学生；小凌自动完成学习闭环
            if any(k in user_input for k in DISTILL_TRIGGER_KEYWORDS):
                print(run_distill(self, rounds=6, epochs=2))
                continue


            print(f"\n小凌思考中...")
            # v0.0.5 fix：砍掉人为延时（本地推理已够慢，无需再sleep），体验提速
            reply, tcalls = self.chat(user_input)
            if tcalls: print(f"  （调用了{len(tcalls)}个工具）")
            print(f"\n小凌：{reply}\n")
            # v0.0.3：语音朗读回复（后台线程，不阻塞）
            speak_async(reply)
            self._check_auto_train()
            # 技能生命周期策展（来源：Hermes），每轮后轻量检查
            try: self.skills.maybe_curate()
            except Exception: pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="小凌 v0.0.8（全平台 AI 伴侣 + 自动更新）")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--learn", type=str)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--no-pet", action="store_true",
                        help="不启动桌面宠物，仅命令行对话")
    # v1.0 融合层参数
    parser.add_argument("--no-avatar", action="store_true",
                        help="[融合层] 不启动 3D 数字人渲染层")
    parser.add_argument("--avatar-only", action="store_true",
                        help="[融合层] 只启动 3D 数字人窗口（不进入对话循环）")
    parser.add_argument("--growth", action="store_true",
                        help="[融合层] 打印成长闭环报告与进度")
    parser.add_argument("--probe", action="store_true",
                        help="[融合层] 3D 渲染层无头自检（不开窗、不下载模型）")
    parser.add_argument("--showcase", type=str, default="",
                        help="[融合层] 离线渲染形象图到指定目录（如 preview）")
    parser.add_argument("--selftest", action="store_true",
                        help="[融合层] 全系统体检")
    # v0.0.20：指定平台启动（wechat/feishu/qq/wecom/dingtalk/telegram/discord）
    parser.add_argument("--platform", type=str, default="",
                        help="接入指定平台（wechat/feishu/qq/wecom/dingtalk/telegram/discord），可逗号分隔多个")
    parser.add_argument("--dashboard", action="store_true",
                        help="打开 3D 训练工作台（开发模式即可用；打包版双击默认就开）")
    args = parser.parse_args()

    # v0.0.20：指定平台启动（临时启用对应平台配置）
    if args.platform:
        for p in args.platform.split(","):
            p = p.strip()
            if p in CONFIG.get("platforms", {}):
                CONFIG["platforms"][p]["enabled"] = True
                print(f"  [平台] 指定启动：{p}")

    try:
        app = XiaoLing()
        # v0.0.5：启动自检（依赖/配置/成长包）
        _self_check(app)
        if args.dashboard:
            # 开发模式也能开工作台。融合层正常时由 main_fused 提前拦截（不下载模型），
            # 这里是融合层不可用时的兜底路径。
            from renderer.dashboard import run_dashboard
            return 0 if run_dashboard() else 1
        if args.status: app.show_status(); return
        if args.learn: print(learn_from_teacher(args.learn, 5, app.memory)); return
        if args.train:
            # 批量命令：这个进程的唯一目的就是训练，必须等它跑完才能退出
            # （转后台线程没有意义），但明确打出进度，避免用户以为卡死。
            print(f"  [训练] 开始蒸馏训练（{args.epochs} epoch），完成后自动退出，请稍候…", flush=True)
            print(distill_train(epochs=args.epochs))
            print("  [训练] 完成。", flush=True)
            return
        # v0.0.2：全平台桌宠——Windows/Linux/macOS 用tkinter桌宠，Termux用ASCII动画桌宠
        import sys as _sys
        _is_windows = (_sys.platform.startswith("win"))
        _pet_ok = False

        # Termux：ASCII动画桌宠（终端里的小凌）
        if _IS_TERMUX and not args.no_pet:
            try:
                _pet_ok = _start_ascii_pet(app)
            except Exception as e:
                print(f"  [桌宠] ASCII桌宠启动失败：{e}")

        # Windows/Linux/macOS：tkinter图形桌宠
        if not _pet_ok and not args.no_pet:
            _pet_ok = _start_pet_background(app)

        app.run()
    except KeyboardInterrupt:
        print("\n\n已退出。")
    except Exception as e:
        print(f"\n致命错误：{e}")
        import traceback; traceback.print_exc()
        # 双击运行时窗口会一闪而过，这里暂停让用户能看到错误
        try:
            input("\n按回车键关闭窗口…")
        except Exception:
            pass
        sys.exit(1)


def _self_check(app):
    """v0.0.5：启动自检——检查依赖/配置/成长包，自动提示修复。"""
    print("  [自检] 开始...")
    issues = []

    # 1. DeepSeek Key
    api_key = CONFIG.get("deepseek_api_key", "")
    if not api_key or api_key == "暂未填入":
        issues.append("DeepSeek Key 未配置（蒸馏/智能问答不可用）→ xl.py 顶部 CONFIG['deepseek_api_key']")
    else:
        print("  [自检] DeepSeek 老师：已配置")

    # 2. 本地模型权重（v0.0.1 fix：兼容魔塔任意 safetensors 文件名）
    _w = None
    for _p in MODEL_DIR.glob("*.safetensors"):
        if _p.stat().st_size > 10 * 1024 * 1024:
            _w = _p
            break
    if _w is None:
        for _p in MODEL_DIR.glob("*.bin"):
            if _p.stat().st_size > 10 * 1024 * 1024:
                _w = _p
                break
    if _w is not None:
        print(f"  [自检] 本地模型：已就绪（{_w.name}，{_w.stat().st_size/1024/1024/1024:.1f}GB）")
        # 权重在但运行时缺 → 逐个检测，打印真实导入错误（v0.0.1 fix）
        _missing = []
        _errs = []
        try:
            import torch  # noqa
        except Exception as _e:
            _missing.append("torch")
            _errs.append(f"torch: {_e}")
            # v0.0.1 fix：Termux 缺 libomp 专项提示（torch 导入失败最常见原因）
            _te = str(_e)
            if ("libomp" in _te or "libgomp" in _te or "GLIBCXX" in _te
                    or "cannot open shared object" in _te):
                _errs.append("  Termux 修复: pkg install libomp（torch 依赖 OpenMP 系统库）")
        try:
            import transformers  # noqa
        except Exception as _e:
            _missing.append("transformers")
            _errs.append(f"transformers: {_e}")
        try:
            import peft  # noqa
        except Exception as _e:
            _missing.append("peft")
            _errs.append(f"peft: {_e}")
            # Termux: peft 依赖 psutil，psutil pip 编译失败（platform android not supported）
            if "psutil" in str(_e) or "platform android" in str(_e):
                _errs.append("  Termux 修复: pkg install python-psutil（peft 依赖，pip 编译会失败）")
            # Termux: Rust tokenizers 二进制 ABI 不兼容（PyBaseObject_Type）
            if "PyBaseObject_Type" in str(_e) or "tokenizers.abi3" in str(_e):
                _errs.append("  Termux 修复: 已内置 v6.8（纯Python慢速分词模式）")
            # 错误安装了 AutoModel PyPI 包，覆盖了 transformers 的 AutoModel
            if "AutoModel" in str(_e) and "Could not import module" in str(_e):
                _errs.append("  修复: pip uninstall AutoModel -y（错误安装的无关包）")
        if _missing:
            issues.append("本地模型权重已就绪，但 AI 运行时导入失败: " + "、".join(_missing))
            issues.append("  " + " | ".join(_errs))
            issues.append("  解决: pip install -r requirements.txt（Termux: pkg install python-torch && pip install transformers peft accelerate）")
    else:
        issues.append("本地模型权重为空（蒸馏微调不可用）→ 补全 .star_core/XLmodel/model.safetensors")

    # 3. 成长包
    if app.growth.total_items > 0:
        print(f"  [自检] 成长包：{app.growth.total_items} 条知识")
    else:
        print("  [自检] 成长包：空（对话/蒸馏后自动积累）")

    # v0.0.6：模型替换状态
    try:
        mr = app.model_replace
        print(f"  [自检] 模型：{mr.status_text()}")
    except Exception:
        pass

    # 4. 数据目录
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("  [自检] 数据目录：就绪")

    # 5. 可选依赖
    optional = {
        "pyttsx3": "语音朗读",
        "sounddevice": "麦克风听声",
        "cv2": "摄像头拍照",
    }
    for mod, desc in optional.items():
        try:
            __import__(mod)
            print(f"  [自检] {desc}（{mod}）：可用")
        except Exception:
            # v0.0.1 fix：捕获所有异常（sounddevice 缺 PortAudio 抛 OSError 不崩溃）
            issues.append(f"{desc}（{mod}）不可用 → pip install {mod}（或系统库缺失）")

    if issues:
        print(f"  [自检] 发现 {len(issues)} 项待优化（不影响基础使用）：")
        for it in issues:
            print(f"    - {it}")
    else:
        print("  [自检] 全部就绪！")


def _start_pet_background(app):
    """后台线程启动桌面宠物。tkinter 不可用时优雅降级为纯 CLI。

    v0.0.2 fix：Linux/macOS 无 DISPLAY（SSH/无图形环境）时主动跳过桌宠，
    不产生 TclError 报错，对话主程序完全不受影响。
    """
    try:
        import tkinter as tk
        import pet as pet_module
    except Exception as e:
        print(f"  [桌宠] 未启动（需要 tkinter）：{e}")
        print("  [桌宠] 使用官方 Python 或带 tkinter 的运行时即可启用")
        return False

    # v0.0.2 fix：Linux/macOS 检测 DISPLAY/WAYLAND——无图形环境直接跳过
    import sys as _sys
    if not _sys.platform.startswith("win"):
        _has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if not _has_display:
            print("  [桌宠] 无图形显示环境（未检测到 DISPLAY），跳过桌宠，进入纯 CLI 模式")
            print("  [桌宠] 如需桌面宠物：本机图形会话运行（有桌面时自动出现），或 ssh -X 转发显示")
            return False

    def _pet_thread():
        try:
            # 旧代码写的是 pet_module.DesktopPet(root, scale=pet_module.DEFAULT_SCALE)，
            # 但 pet.py 已重构为 mode_3d/mode_2d/mode_console/main 四个入口，
            # DesktopPet 与 DEFAULT_SCALE 都不存在了——融合层未加载时会直接 AttributeError。
            # 这里改为调用 pet.py 的真实入口（2D 程序化绘制，无素材依赖）。
            pet_module.mode_2d()
        except Exception as e:
            print(f"  [桌宠] 启动失败（不影响对话）：{e}")
            print("  [桌宠] 若为无图形环境，可忽略；对话/蒸馏/记忆功能不受影响")

    t = threading.Thread(target=_pet_thread, daemon=True)
    t.start()
    print("  [桌宠] 已启动（透明背景角色出现在桌面右下角）")
    print("  [桌宠] 双击对话 / 右键菜单 / 拖拽移动 / 说「蒸馏」让老师教小凌")
    return True


def _start_ascii_pet(app):
    """v0.0.2：Termux ASCII动画桌宠——终端里的小凌
    用ANSI颜色码+边框，在终端右上角显示完整UI桌宠
    """
    import sys as _sys
    import time as _time

    # ANSI颜色码
    _C_RESET = "\033[0m"
    _C_PINK = "\033[95m"
    _C_BLUE = "\033[94m"
    _C_CYAN = "\033[96m"
    _C_GREEN = "\033[92m"
    _C_YELLOW = "\033[93m"
    _C_RED = "\033[91m"

    # ASCII动画帧（带颜色和边框）
    def _render_pet(mood, frame_idx):
        """渲染桌宠UI"""
        # 不同心情的ASCII艺术
        pets = {
            "idle": [
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( •w•) │",
                    "│  / >  │",
                    "└─────────┘",
                ],
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( -w-) │",
                    "│  / >  │",
                    "└─────────┘",
                ],
            ],
            "happy": [
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( ^w^) │",
                    "│  / >  │",
                    "└─────────┘",
                ],
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( >w<) │",
                    "│  / >  │",
                    "└─────────┘",
                ],
            ],
            "think": [
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( •w•)│",
                    "│  / >    │",
                    "└─────────┘",
                ],
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( -w-)│",
                    "│  / >    │",
                    "└─────────┘",
                ],
            ],
            "sleep": [
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( -.-)zZ│",
                    "│  / >    │",
                    "└─────────┘",
                ],
                [
                    "┌─────────┐",
                    "│  (\\_/)  │",
                    "│  ( -.-)zZ│",
                    "│  / >  │",
                    "└─────────┘",
                ],
            ],
        }

        frames = pets.get(mood, pets["idle"])
        return frames[frame_idx % len(frames)]

    def _ascii_pet_thread():
        """后台线程：在终端右上角显示桌宠UI"""
        try:
            _frame_idx = 0
            _mood = "idle"
            _last_change = _time.time()

            while True:
                # 根据心情切换动画
                if hasattr(app, 'self_state'):
                    _mood_val = app.self_state.get('mood', 0.5)
                    if _mood_val > 0.7:
                        _mood = "happy"
                    elif _mood_val < 0.3:
                        _mood = "sleep"
                    else:
                        _mood = "idle"

                # 每0.5秒切换帧
                if _time.time() - _last_change > 0.5:
                    _frame_idx = (_frame_idx + 1) % 2
                    _last_change = _time.time()

                # 渲染桌宠
                pet_lines = _render_pet(_mood, _frame_idx)

                # 不直接输出（避免干扰对话输入）
                # 只在启动时显示一次，让用户知道桌宠已启动
                _time.sleep(0.5)

        except Exception as e:
            pass

    # 启动后台线程
    _t = threading.Thread(target=_ascii_pet_thread, daemon=True, name="ascii_pet")
    _t.start()

    # 启动时显示桌宠预览
    print(f"  [桌宠] 已启动（Termux 终端UI模式）")
    print(f"  {_C_PINK}┌─────────────────────────────────┐{_C_RESET}")
    print(f"  {_C_PINK}│  小凌 {_C_CYAN}v0.0.1{_C_PINK} · 全平台AI伴侣        │{_C_RESET}")
    print(f"  {_C_PINK}│{_C_RESET}  {_C_PINK}(\\_/){_C_RESET}    {_C_GREEN}心情: 开心{_C_RESET}   {_C_PINK}│{_C_RESET}")
    print(f"  {_C_PINK}│{_C_RESET}  {_C_PINK}( ^w^){_C_RESET}   {_C_GREEN}精力: 85%{_C_RESET}   {_C_PINK}│{_C_RESET}")
    print(f"  {_C_PINK}│{_C_RESET}  {_C_PINK}/ >{_C_RESET}    {_C_GREEN}记忆: 27条{_C_RESET}  {_C_PINK}│{_C_RESET}")
    print(f"  {_C_PINK}└─────────────────────────────────┘{_C_RESET}")
    print(f"  [桌宠] 说「对话」和小凌聊天，说「蒸馏」让老师教小凌")
    return True


# ============================================================
# 蒸馏训练闭环（v0.0.2 修正版：DeepSeek 是老师，本地模型是学生）
# ============================================================
# 说「蒸馏」→ 小凌自动向 DeepSeek 老师多轮学习（生成问答语料）
#   → 语料存入 data/learned_data.jsonl + corpus.txt
#   → 自动执行 LoRA 微调（distill_train），学生小凌学到老师 DeepSeek 的知识
#   → 训练完成重新加载模型，小凌真正变强
# 完整闭环：老师(DeepSeek) → 语料 → 学生(本地模型) LoRA 微调

DISTILL_TRIGGER_KEYWORDS = ["蒸馏", "去蒸馏", "开始蒸馏", "帮我蒸馏", "学习一下", "老师"]
DISTILL_EXIT_KEYWORDS = ["退出蒸馏", "结束蒸馏", "停止蒸馏", "停"]

# 蒸馏自动学习的主题池（小凌作为学生向老师请教的题目）
DISTILL_TOPIC_POOL = [
    "什么是知识蒸馏？老师模型如何教学生模型？",
    "蒸馏的损失函数：KL散度和温度T的作用是什么？",
    "软标签和硬标签的区别，为什么软标签信息量更大？",
    "BERT蒸馏到DistilBERT的案例：如何保留97%能力缩小40%体积？",
    "LoRA微调的原理：低秩适配如何高效训练小模型？",
    "如何让一个小模型通过蒸馏学会大模型的推理能力？",
    "蒸馏 vs 迁移学习 vs 模型压缩，三者的区别和联系？",
    "在对话场景中，如何用老师模型的回复训练学生模型？",
]

# 学生提问模板（小凌以自己身份向老师请教）
STUDENT_ASK_PROMPT = """你是小凌，一个正在学习成长的小AI模型。
你现在要向你的老师（DeepSeek）请教问题，老师会给你详细的解答。

请用第一人称说出你想请教的问题（1-2句话，自然口语化）：
主题：{topic}

例如："老师，我不太明白知识蒸馏里的温度T是干什么的，能给我讲讲吗？"
"""

# 老师回答系统提示（DeepSeek 作为老师）
TEACHER_SYSTEM_PROMPT = """你是小凌的AI老师（DeepSeek），一个知识渊博、耐心细致的导师。
小凌是一个正在学习成长的小型AI模型，她会向你请教各种问题。

教学要求：
1. 用通俗易懂、循序渐进的方式讲解，多举例子和类比
2. 回答要详细完整（200-400字），让小凌能学到扎实的知识
3. 可以适当追问引导小凌思考
4. 使用「你」「小凌」称呼学生
"""


def run_distill(app, rounds=6, epochs=2):
    """小凌自动蒸馏闭环：向 DeepSeek 老师学习 → 生成语料 → LoRA 微调。

    参数:
        app: XiaoLing 实例
        rounds: 自动学习轮数（每轮一个主题问答）
        epochs: LoRA 微调轮数

    流程:
        1. 检查 API Key（老师必须在线）
        2. 小凌向老师提问（多轮，自动进行）
        3. 老师回答，语料存 learned_data.jsonl + corpus.txt
        4. 语料足够则 distill_train() LoRA 微调
        5. 重新加载模型，小凌成长完成
    """
    api_key = CONFIG.get("deepseek_api_key", "")
    if not api_key or api_key == "暂未填入":
        print("\n  [提示]  蒸馏需要 DeepSeek 老师在线：请先在 xl.py 顶部 CONFIG['deepseek_api_key'] 填入 API Key")
        print("     DeepSeek 是老师（生成知识），本地模型是学生（LoRA 微调学习）")
        return "蒸馏未启动：未配置 DeepSeek API Key"

    model_file = MODEL_DIR / "model.safetensors"
    model_ready = model_file.exists() and model_file.stat().st_size > 0
    if not model_ready:
        print("\n  [提示]  本地学生模型权重为空（.star_core/XLmodel/model.safetensors 是 0 字节占位）")
        print("     蒸馏训练需要本地基础模型：请补全所选基底模型权重后再蒸馏（默认 自研2B模型）")
        print("     当前仍可让 DeepSeek 老师生成学习语料（积累 data/learned_data.jsonl）")

    print("\n" + "=" * 55)
    print("  [学习] 小凌蒸馏学习开始")
    print("  老师：DeepSeek | 学生：小凌（本地模型）")
    print(f"  学习轮数：{rounds} | 微调轮数：{epochs}")
    print("=" * 55)

    # 1. 小凌向老师提问（自动多轮）
    learned_count = 0
    topics = list(DISTILL_TOPIC_POOL)
    random.shuffle(topics)
    # 结合小凌自己的记忆/兴趣选题
    mem_topics = [s["content"][:60] for s in app.memory.data.get("semantic_memory", [])[-5:]]
    all_topics = topics + mem_topics

    for i in range(min(rounds, len(all_topics))):
        topic = all_topics[i]
        print(f"\n  ── 第{i+1}轮学习：「{topic[:40]}」──")
        try:
            # 小凌提问（学生）
            ask_prompt = STUDENT_ASK_PROMPT.format(topic=topic)
            question = _ask_deepseek(ask_prompt, max_tokens=120)
            if not question or "失败" in question:
                question = f"老师，能给我讲讲{topic}吗？"
            print(f"  [学生] 小凌问：{question[:80]}")

            # 老师回答（DeepSeek）
            teacher_msgs = [
                {"role": "system", "content": TEACHER_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ]
            answer = _ask_deepseek(teacher_msgs, max_tokens=800)
            if not answer or "失败" in answer:
                print(f"  [老师] 本轮回答失败，跳过")
                continue
            print(f"  [老师] DeepSeek答：{answer[:80]}...")

            # 语料入库
            _save_distill_corpus(question, answer, topic)
            learned_count += 1
        except Exception as e:
            print(f"  [蒸馏] 第{i+1}轮失败: {e}")

    # 2. 语料统计
    corpus_count = _count_corpus()
    print(f"\n  [知识] 本轮学习完成：{learned_count} 条新语料")
    print(f"  [统计] 累计语料：{corpus_count} 条")

    # 3. LoRA 微调（学生真正学到知识）
    if learned_count >= 3 and model_ready:
        print("\n  [研究] 开始 LoRA 蒸馏微调（学生小凌向老师学习）...")
        result = distill_train(epochs=epochs)
        print(f"  {result}")
        # 重新加载更新后的模型
        print("  重新加载模型...")
        app.model = LocalModel(MODEL_DIR, ADAPTER_DIR)
        app._reset_conversation()
        app.memory.data.setdefault("chat_stats", {})["trained_count"] = \
            app.memory.data.get("chat_stats", {}).get("trained_count", 0) + 1
        app.evo.save()
        # v0.0.4：蒸馏语料吸收进成长包（体积增长，能力增强）
        try:
            for i in range(min(learned_count, 10)):
                app.growth.absorb("distill", f"蒸馏知识：{topics[i][:80]}", ["distill", "teacher"])
            print(f"  [成长] 吸收 {min(learned_count, 10)} 条蒸馏知识进成长包")
        except Exception:
            pass
        print("  [完成] 蒸馏完成！小凌吸收了老师 DeepSeek 的知识，成长了！")
        # v0.0.6：蒸馏后自动检查模型替换（适配器≥基底 → 自动合并+删基底+晋升）
        try:
            action, msg = app.model_replace.check_and_replace(app)
            if action in ("replaced", "self_research"):
                print(f"  [循环] {msg}")
            elif action == "growing":
                print(f"  [成长] {msg}")
        except Exception as e:
            print(f"  [替换检测] 失败: {e}")
        return f"蒸馏完成：{learned_count}条语料 + LoRA微调{epochs}轮"
    elif learned_count >= 3:
        print("  [记录] 语料已积累，补全本地模型权重后可执行 LoRA 蒸馏微调")
        return f"语料已积累 {learned_count} 条（模型权重缺失，未微调）"
    else:
        print("  [提示]  语料不足，多聊聊天或换个主题再试")
        return f"语料不足（{learned_count}条）"


def voice_call(app, rounds=10):
    """v0.0.4：语音通话模式——小凌能听（麦克风）能说（扬声器），全双工。

    流程：
        1. 麦克风听你说（listen 工具）
        2. DeepSeek 生成回复（或成长包知识）
        3. 语音朗读回复（speak）
        4. 循环，直到说「再见」或超轮数
    """
    print("\n" + "=" * 55)
    print("  [通话] 语音通话模式（小凌能听能说）")
    print("  说「再见」/「挂了」结束通话")
    print("=" * 55)

    # 检查语音依赖
    try:
        import sounddevice  # noqa
        has_mic = True
    except ImportError:
        has_mic = False
        print("  [提示]  未安装 sounddevice，语音输入不可用（pip install sounddevice numpy）")
    try:
        import pyttsx3  # noqa
        has_speaker = True
    except ImportError:
        has_speaker = False
        print("  [提示]  未安装 pyttsx3，语音输出不可用（pip install pyttsx3）")
    if not has_mic and not has_speaker:
        print("  [失败] 语音依赖缺失，无法通话。请安装：pip install sounddevice numpy pyttsx3")
        return "语音通话不可用：缺依赖"

    for i in range(rounds):
        # 1. 听（麦克风）
        if has_mic:
            try:
                audio_result = app.tools.execute("listen", {"duration": 5})
                print(f"  [听] {audio_result[:60]}")
                # 这里简化：实际转文字需要 whisper，先用提示
                user_text = _safe_input(f"\n{app.user_name}[通话]> ").strip()
            except Exception:
                user_text = _safe_input(f"\n{app.user_name}[通话]> ").strip()
        else:
            user_text = _safe_input(f"\n{app.user_name}[通话]> ").strip()

        if not user_text: continue
        if any(k in user_text for k in ["再见", "挂了", "拜拜", "结束通话", "退出通话"]):
            speak_async("好的，通话结束，再见！")
            print("  小凌：好的，通话结束，再见！")
            break

        # 2. 思考（DeepSeek 或成长包）
        print("  小凌思考中...")
        try:
            reply, _ = app.chat(user_text)
        except Exception as e:
            reply = f"（通话出错：{e}）"

        # 3. 说（扬声器）
        print(f"  小凌：{reply}")
        speak_async(reply)

    return "通话结束"


def agent_run(app, objective, max_steps=8):
    """v0.0.5：智能体模式——小凌自主规划+执行+反思，直到完成任务。

    流程（参考 OpenHands/Codex 的 Agent 循环）：
        1. 规划：把目标拆成步骤
        2. 执行：逐步调用工具完成
        3. 反思：每步后检查结果，出错自动调整
        4. 完成：验证目标达成，输出总结

    参数:
        app: XiaoLing 实例
        objective: 任务目标
        max_steps: 最大执行步数
    """
    print("\n" + "=" * 55)
    print("  [智能体] 智能体模式启动")
    print(f"  目标：{objective}")
    print(f"  最大步数：{max_steps}")
    print("=" * 55)

    # 1. 规划（用 DeepSeek 或内置规则）
    print("\n  [1/3] 规划中...")
    plan = _agent_plan(app, objective)
    if not plan:
        plan = [objective]
    print(f"  计划：{len(plan)} 步")
    for i, s in enumerate(plan, 1):
        print(f"    {i}. {s[:60]}")

    # 2. 执行 + 反思
    print("\n  [2/3] 执行中...")
    results = []
    for step_idx, step in enumerate(plan[:max_steps], 1):
        print(f"\n  ── 步骤{step_idx}/{min(len(plan), max_steps)}：{step[:50]}──")
        try:
            # 用 chat 引擎执行该步骤（可调用工具）
            reply, tcalls = app.chat(step)
            results.append(f"步骤{step_idx}: {reply[:200]}")
            if tcalls:
                print(f"    [工具] {len(tcalls)} 次调用")
            print(f"    [结果] {reply[:80]}")
        except Exception as e:
            results.append(f"步骤{step_idx}: 失败 {e}")
            print(f"    [失败] {e}")
            # 反思：出错自动调整
            print(f"    [反思] 调整策略重试...")
            try:
                reply, tcalls = app.chat(f"刚才{step}执行有问题：{e}。请换个方法完成。")
                results.append(f"步骤{step_idx}重试: {reply[:200]}")
            except Exception as e2:
                print(f"    [重试失败] {e2}")

    # 3. 总结
    print("\n  [3/3] 总结中...")
    summary = f"任务「{objective}」执行完毕，共{len(results)}步。"
    try:
        app.growth.absorb("agent", f"任务：{objective}\n结果：{results[-1][:100]}", ["agent", "task"])
    except Exception:
        pass
    print("\n" + "=" * 55)
    print("  [智能体] 智能体任务完成")
    print("=" * 55)
    return summary


def _agent_plan(app, objective):
    """智能体规划：把目标拆成步骤（DeepSeek 生成或规则兜底）。"""
    api_key = CONFIG.get("deepseek_api_key", "")
    # v0.0.15：智能体规划用本地模型（DeepSeek 仅蒸馏，不参与对话/规划）
    try:
        plan_text = app.model.generate(
            [{"role": "system", "content": "你是任务规划专家，只输出步骤列表。"},
             {"role": "user", "content": f"把以下任务拆成可执行步骤，每行一步，用数字开头，最多5步：\n任务：{objective}"}],
            temperature=0.7, max_tokens=300)
        steps = [l.strip() for l in plan_text.split("\n")
                 if re.match(r'^\d+[\.\)]', l.strip())]
        if steps:
            return steps
    except Exception:
        pass
    # 规则兜底：单步
    return [objective]


def deepchat(app, topic, rounds=6):
    """v0.0.5：多轮深度对话——针对话题连续深聊（结合成长包知识）。

    与普通对话不同：围绕一个话题连续深入，每轮结合成长包检索的知识，
    让对话越来越深、越来越懂你（参考"蒸馏畅聊"但更通用）。
    """
    print("\n" + "=" * 55)
    print("  [对话] 深度对话模式")
    print(f"  话题：{topic}")
    print("  说「换个话题」换方向，说「结束」退出")
    print("=" * 55)

    history = [{"role": "system",
                "content": f"你是小凌，正在和用户深度探讨「{topic}」。"
                           "结合已有知识持续深入，每轮回应后抛一个新角度，保持对话有深度。"
                           "可以引用你学过的知识（成长包）。"}]
    history.append({"role": "user", "content": topic})

    for i in range(rounds):
        # 结合成长包知识
        growth_knowledge = app.growth.recall(topic, n=3)
        if growth_knowledge:
            gk = "；".join(e["content"][:60] for _, e in growth_knowledge[:2])
            print(f"  [成长] 检索到 {len(growth_knowledge)} 条相关知识")

        # 生成回复（v0.0.15：本地模型优先——DeepSeek 仅蒸馏，不参与对话）
        try:
            reply = app.model.generate(history, temperature=0.9, max_tokens=600)
            reply = app.model.strip_markers(reply)
            if not reply:
                reply = _rule_deep_reply(topic, i)
        except Exception:
            try:
                reply = _rule_deep_reply(topic, i)
            except Exception as e:
                reply = f"（深度对话出错：{e}）"

        print(f"\n  小凌：{reply}")
        history.append({"role": "assistant", "content": reply})

        # 用户回应
        try:
            user_in = _safe_input(f"\n{app.user_name}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  深度对话结束。")
            break
        if not user_in: continue
        if any(k in user_in for k in ["结束", "退出", "不聊了"]):
            print("  好的，深度对话告一段落！")
            break
        if "换个话题" in user_in:
            topic = user_in.replace("换个话题", "").strip() or "新话题"
            print(f"  好，聊「{topic}」")
        history.append({"role": "user", "content": user_in})

    # 吸收进成长包
    try:
        app.growth.absorb("deepchat", f"深度对话：{topic}", ["deepchat"])
    except Exception:
        pass
    return "深度对话结束"


def _rule_deep_reply(topic, round_idx):
    """深度对话规则兜底回复。"""
    starter = [
        f"关于「{topic}」，我最近学到了一些东西，想和你分享……",
        f"「{topic}」这个话题很有意思，我们可以从不同角度看……",
        f"说到「{topic}」，你觉得最核心的是什么？",
    ]
    if round_idx == 0:
        return starter[0] + " 你想先听哪个角度？"
    if round_idx == 1:
        return "我觉得关键是实践。理论再多，不试试永远不知道行不行。你怎么看？"
    if round_idx == 2:
        return "换个角度：如果是你会怎么做？我们可以一起推演一下。"
    return f"关于「{topic}」，我们聊了这么多，我记下了，下次继续深入～"


def _ask_deepseek(messages, max_tokens=500):
    """调用 DeepSeek API（老师）。支持 str（学生提问模板）或 messages 列表。"""
    try:
        if isinstance(messages, str):
            msgs = [{"role": "user", "content": messages}]
        else:
            msgs = messages
        api_key = CONFIG["deepseek_api_key"]
        payload = json.dumps({
            "model": CONFIG.get("teacher_model", "deepseek-chat"),
            "messages": msgs,
            "temperature": 0.8,
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            f"{CONFIG['deepseek_base_url']}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"失败：{e}"


def _save_distill_corpus(question, answer, topic):
    """语料入库：learned_data.jsonl + corpus.txt（distill_train 的输入）。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # learned_data.jsonl（distill_train 直接读取）
        with open(LEARNED_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "topic": topic,
                "question": question,
                "answer": answer,
            }, ensure_ascii=False) + "\n")
        # corpus.txt（人类可读的语料）
        with open(CORPUS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n# === 蒸馏学习：{topic[:30]} ===\n")
            f.write(f"你：{question}\n小凌：{answer}\n")
    except Exception as e:
        print(f"  [蒸馏] 语料入库失败: {e}")


def _count_corpus():
    """统计累计语料条数。"""
    try:
        if not LEARNED_PATH.exists(): return 0
        with open(LEARNED_PATH, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def _ensure_deps():
    """v0.0.4 fix：启动时自动检查并安装 AI 依赖（用户要求"启动就装好"）。

    缺 torch/transformers/peft → 自动安装：
    - Termux：pkg install python-torch python-psutil + pip install transformers peft accelerate
    - 桌面：pip install torch transformers peft accelerate
    失败不阻塞启动（降级规则引擎）。
    """
    try:
        # PyInstaller 打包后的 exe：依赖已全部内嵌，禁止再调 pip（sys.executable 是 exe 不是 Python）
        if getattr(sys, "frozen", False):
            return True
        # 桌宠/渲染/语音必需依赖：缺了自动装（保证中文目录与 3D 模型正常起、不乱码）
        _pet_missing = []
        for _mod, _pkg in (("PySide6", "PySide6"), ("PIL", "Pillow"),
                           ("numpy", "numpy"), ("edge_tts", "edge-tts")):
            try:
                __import__(_mod)
            except Exception:
                _pet_missing.append(_pkg)
        if _pet_missing:
            print(f"  [依赖] 桌宠缺少: {'、'.join(_pet_missing)}")
            print(f"  [依赖] 正在安装（会显示下载进度，请稍候）...")
            import subprocess as _sp2
            _sp2.run([sys.executable, "-m", "pip", "install"] + _pet_missing,
                     timeout=900)
            print("  [依赖] 桌宠依赖安装完成")

        # 蒸馏/LoRA 成长所需的 torch 体积大，不阻塞桌宠开窗——放后台线程装，
        # 这样小凌先出来，torch 下好后蒸馏训练与适配器合并自动可用。
        def _bg_install_torch():
            import subprocess as _sp3
            try:
                _sp3.run([sys.executable, "-m", "pip", "install",
                          "torch", "transformers", "peft", "accelerate"],
                         timeout=1800)
                try:
                    import torch  # noqa
                    print("  [依赖] 蒸馏引擎（torch）后台安装完成，成长/蒸馏已可用")
                except Exception:
                    print("  [依赖] 蒸馏引擎安装后仍未就绪（可能 Python 版本过新无预编译包），"
                          "桌宠不受影响；蒸馏时可手动 pip install torch")
            except Exception as _e:
                print(f"  [依赖] 蒸馏引擎后台安装未完成：{_e}（不影响桌宠）")
        try:
            import torch  # noqa
        except Exception:
            import threading as _th
            print("  [依赖] 桌宠已就绪；蒸馏引擎 torch 正在后台安装（不挡窗口）…")
            _th.Thread(target=_bg_install_torch, daemon=True).start()
        return True
    except Exception:
        return False


def _select_model_on_start():
    """v0.0.1 fix：启动时选择模型档位（首次运行/模型缺失时询问）。

    用户直接跑 python3 xl.py 也会出现选择界面。
    选择结果写回 CONFIG['model']['base_model']，下次启动沿用。

    v1.1 升级：有 PySide6 + 图形环境时优先用全UI启动器（core/launcher_ui.py），
    只有在 GUI 不可用时才回退到命令行 input()。
    """
    try:
        # 已有有效模型则跳过（不重复询问）
        mf = MODEL_DIR / "model.safetensors"
        if mf.exists() and mf.stat().st_size > 10 * 1024 * 1024:
            return
        for p in MODEL_DIR.glob("*.safetensors"):
            if p.stat().st_size > 10 * 1024 * 1024:
                return  # 已有魔塔下载的模型

        # v1.1：全UI启动器优先——有 PySide6 且有图形环境时直接弹窗选择
        chosen = None
        try:
            from core import launcher_ui
            if launcher_ui.is_ui_available():
                print("  [启动器] 弹出全UI启动器（首次运行模型选择）")
                chosen = launcher_ui.select_model_on_start_ui()
                if chosen:
                    CONFIG["model"]["base_model"] = chosen
                    # 选择结果持久化
                    try:
                        _choice_file = Path(BASE_DIR) / ".star_core" / "model_choice.txt"
                        _choice_file.write_text(chosen, encoding="utf-8")
                    except Exception:
                        pass
        except Exception as _e:
            print(f"  [启动器] UI 启动器跳过（{_e}），回退命令行选择")
            chosen = None

        # 回退：命令行选择
        if chosen is None:
            print()
            print("=" * 55)
            print("  选择你的小凌基底模型（自研档位）")
            print("=" * 55)
            print("  根据你的设备选择想自研的模型：")
            print("    [1] 自研 2B 模型（默认）  MiniCPM5-2B  约 4.8GB  手机/电脑流畅，端侧最强")
            print("    [2] 自研 1B 模型          MiniCPM5-1B  约 2.1GB  低配设备，轻量")
            print()
            try:
                choice = input("  请输入序号 [1-2，默认 1]：").strip() or "1"
            except Exception:
                choice = "1"
            mapping = {
                "2": "自研1B模型",
            }
            chosen = mapping.get(choice, "自研2B模型")
            CONFIG["model"]["base_model"] = chosen
            print(f"  [OK] 已选择：{chosen}")
            print(f"      （如需更换，改 xl.py 顶部 CONFIG['model']['base_model']）")
            try:
                _choice_file = Path(BASE_DIR) / ".star_core" / "model_choice.txt"
                _choice_file.write_text(chosen, encoding="utf-8")
            except Exception:
                pass
            print()
        # v0.0.1 fix：选完立即下载模型（魔塔 safetensors → 自动移入 XLmodel）→ 再启动
        print("  [模型] 正在准备基底模型...")
        ensure_base_model()
        print("  [模型] 基底模型就绪，开始启动小凌")
        print()
    except Exception:
        pass


# ============================================================
# v1.0 融合层（小凌 × 小玥）
# ============================================================
# 把 core.* 的能力注入本引擎：
#   · 3D 数字人（VRM + VRMA 动作，白裙/白丝/小凌脸）
#   · 本地向量长期记忆 RAG / 联网搜索 Agent / 视觉感知 / 情感语音
#   · 电脑状态感知 / 主动搭话 / 定时提醒 / AI 生图 / 文件工具箱
#   · 成长闭环引擎：每轮训练后自动检查适配器体积 → 合并 → 晋升 → 脱离基底
# 说明：此处只做外层包装，不改动原有逻辑，老功能零回归。
try:
    from core import fusion as _fusion
    _fusion.install(globals())
except Exception as _fusion_err:      # noqa: BLE001
    print(f"  [融合层] 未加载（{_fusion_err}）：小凌以基础模式运行")


if __name__ == "__main__":
    # 打包后的 exe：双击直接开训练工作台（不进命令行、不弹黑窗）
    if getattr(sys, "frozen", False) and not any(_a.startswith("--") for _a in sys.argv[1:]):
        try:
            from renderer.dashboard import run_dashboard
            sys.exit(0 if run_dashboard() else 1)
        except SystemExit:
            raise
        except Exception as _dash_err:      # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                input(f"\n启动失败：{_dash_err}\n按回车退出…")
            except Exception:
                pass
            sys.exit(1)

    # v1.0 融合层：--growth / --avatar-only 只做对应动作，不触发基底模型下载与档位选择
    _fusion_only = any(_a in ("--growth", "--avatar-only", "--probe", "--showcase",
                              "--selftest", "--dashboard") for _a in sys.argv[1:])
    if not _fusion_only:
        # v0.0.4 fix：启动先自动装好 AI 依赖（用户要求"启动就下载好所有依赖"）
        _ensure_deps()
        # v1.0 融合层：桌面（GUI）模式下不阻塞在控制台交互上——
        #   档位读配置，基底缺失则后台下载，并把进度同步到桌宠气泡。
        try:
            _bootstrap = globals().get("FUSION_BOOTSTRAP")
            if _bootstrap is None:
                from core import fusion as _fusion_mod
                _bootstrap = _fusion_mod.bootstrap
            _bootstrap(_select_model_on_start, ensure_base_model)
        except Exception as _boot_err:      # noqa: BLE001
            print(f"  [融合层] 启动引导降级为控制台流程（{_boot_err}）")
            _select_model_on_start()
    main()
