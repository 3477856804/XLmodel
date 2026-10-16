# -*- coding: utf-8 -*-
"""Web 实测面板 —— 无需 Flutter 也能验证后端是否真的可用。

本模块原先缺失，导致 main.py 启动后端退化为 sleep 空转（表面像卡死）。
此处按 main.py 的调用契约重建：`run_blocking(port=8765)` 阻塞运行。

提供：
    GET  /                 面板页面（单文件，无外部依赖）
    GET  /api/status       引擎状态
    POST /api/chat         对话（内部调用 engine.chat_stream）
    GET  /api/models       模型商店 / 本地登记 / API 接口汇总
    POST /api/model/dl     下载模型
    GET  /api/plugins      插件列表
    POST /api/plugin/toggle 切换插件开关（持久化）
    POST /api/command      执行指令（走 fusion 指令解析）
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

_ENGINE = {"obj": None, "at": 0.0}


def _get_engine():
    """复用后端引擎实例（延迟创建 + 短缓存，避免每请求重建）。"""
    now = time.time()
    if _ENGINE["obj"] is not None and now - _ENGINE["at"] < 30:
        return _ENGINE["obj"]
    try:
        from core.engine import XiaoLing
        _ENGINE["obj"] = XiaoLing()
        _ENGINE["at"] = now
    except Exception:
        _ENGINE["obj"] = None
    return _ENGINE["obj"]


def _chat(text: str) -> dict:
    eng = _get_engine()
    if eng is None:
        try:
            from backend.rpc.server import _quick_reply
            return {"ok": True, "reply": "".join(_quick_reply(text)),
                    "fallback": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"引擎未就绪：{type(e).__name__}: {e}"}
    try:
        buf = []
        for delta in eng.chat_stream(text):
            buf.append(str(delta))
        return {"ok": True, "reply": "".join(buf)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _status() -> dict:
    out = {"ok": True, "uptime_s": int(time.time() - _START)}
    try:
        eng = _get_engine()
        if eng is not None and hasattr(eng, "show_status"):
            out["engine"] = str(eng.show_status())
    except Exception as e:  # noqa: BLE001
        out["engine"] = f"读取失败：{e}"
    try:
        from core.model import ModelStore
        st = ModelStore()
        info = st.list_all()
        out["installed"] = [m.get("name") for m in info.get("installed", [])]
        out["local"] = [m.get("name") for m in info.get("local", [])]
        out["api"] = [a.get("name") for a in info.get("api", [])]
        out["disk"] = st.disk_usage().get("size", "0 B")
    except Exception as e:  # noqa: BLE001
        out["model_error"] = f"{type(e).__name__}: {e}"
    try:
        from core.config import PluginManager
        pl = PluginManager().list_plugins()
        out["plugins_total"] = len(pl)
        out["plugins_on"] = sum(1 for p in pl if p.get("enabled"))
    except Exception as e:  # noqa: BLE001
        out["plugin_error"] = f"{type(e).__name__}: {e}"
    return out


def _models() -> dict:
    try:
        from core.model import ModelStore
        return {"ok": True, **ModelStore().list_all()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _plugins() -> dict:
    try:
        from core.config import PluginManager
        return {"ok": True, "plugins": PluginManager().list_plugins()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _toggle_plugin(name: str, enabled: bool) -> dict:
    try:
        from core.config import PluginManager
        pm = PluginManager()
        ok = pm.set_enabled(name, bool(enabled))
        return {"ok": ok, "name": name, "enabled": pm.is_enabled(name)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _command(cmd: str) -> dict:
    try:
        from core import fusion
        out = fusion.try_command(_get_engine(), cmd)
        if out is None:
            return {"ok": False, "error": "不认识的指令（试试 help）"}
        try:
            return json.loads(out)
        except Exception:
            return {"ok": True, "output": str(out)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


_START = time.time()
_DL_LOCK = threading.Lock()
_DL_STATE = {"running": None, "log": []}


def _download_async(name: str) -> dict:
    """后台下载，避免 HTTP 请求被大模型下载阻塞。"""
    with _DL_LOCK:
        if _DL_STATE["running"]:
            return {"ok": False, "error": "已有下载任务在进行：" +
                    str(_DL_STATE["running"])}

        def worker():
            _DL_STATE["log"] = []
            try:
                from core.model import ModelStore
                st = ModelStore()
                r = st.download(name, progress_cb=lambda d, t: _DL_STATE["log"]
                                .append(f"{d/1e6:.0f}/{t/1e6:.0f} MB"))
                _DL_STATE["result"] = r
            except Exception as e:  # noqa: BLE001
                _DL_STATE["result"] = {"ok": False, "error": str(e)}
            finally:
                _DL_STATE["running"] = None

        _DL_STATE["running"] = name
        _DL_STATE["result"] = None
        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "message": f"已在后台开始下载 {name}"}


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>小凌 · 实测面板</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#252a34;--fg:#e6e9ef;--dim:#9aa4b2;
--acc:#ff7eb6;--ok:#4ade80;--warn:#fbbf24}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.6 "Microsoft YaHei",system-ui,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line);
display:flex;align-items:center;gap:12px}
h1{margin:0;font-size:16px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok)}
main{display:grid;grid-template-columns:1fr 340px;gap:16px;padding:16px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
padding:14px;margin-bottom:14px}
.card h2{margin:0 0 10px;font-size:13px;color:var(--dim);font-weight:600}
#log{height:320px;overflow:auto;background:#0b0d12;border-radius:8px;padding:12px;
white-space:pre-wrap;font-size:13px}
.msg{margin:6px 0}
.me{color:var(--acc)}
.ai{color:var(--fg)}
.sys{color:var(--dim);font-size:12px}
input,textarea,button,select{background:#0b0d12;color:var(--fg);
border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px}
button{background:var(--acc);color:#1a1020;border:none;cursor:pointer;
font-weight:700}
button:hover{filter:brightness(1.1)}
.row{display:flex;gap:8px;margin-top:10px}
.row input{flex:1}
ul{list-style:none;padding:0;margin:0}
li{padding:6px 0;border-bottom:1px solid var(--line);
display:flex;justify-content:space-between;align-items:center;gap:8px}
li:last-child{border:none}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;background:#222836;
color:var(--dim)}
.on{background:rgba(74,222,128,.15);color:var(--ok)}
pre{background:#0b0d12;padding:10px;border-radius:8px;overflow:auto;font-size:12px}
</style></head><body>
<header><span class="dot"></span><h1>小凌 · 实测面板</h1>
<span style="color:var(--dim);font-size:12px">后端自检页面（无需 Flutter）</span></header>
<main>
<div>
  <div class="card"><h2>对话</h2><div id="log"></div>
    <div class="row"><input id="txt" placeholder="说点什么…"
      onkeydown="if(event.key==='Enter')send()">
      <button onclick="send()">发送</button></div></div>
  <div class="card"><h2>指令（fusion）</h2>
    <div class="row"><input id="cmd" placeholder="model:listall  或  help"
      onkeydown="if(event.key==='Enter')runCmd()">
      <button onclick="runCmd()">执行</button></div>
    <pre id="cmdout" style="margin-top:10px">（结果）</pre></div>
</div>
<div>
  <div class="card"><h2>状态</h2><pre id="status">加载中…</pre></div>
  <div class="card"><h2>模型</h2><ul id="models"></ul>
    <div class="row"><select id="mdl"></select>
      <button onclick="dl()">下载</button></div>
    <pre id="dlout" style="margin-top:8px"></pre></div>
  <div class="card"><h2>插件（默认全关）</h2><ul id="plugins"></ul></div>
</div></main>
<script>
function add(cls,who,text){const d=document.createElement('div');
d.className='msg '+cls;d.textContent=who+text;
const l=document.getElementById('log');l.appendChild(d);l.scrollTop=l.scrollHeight;}
async function send(){const t=document.getElementById('txt');const v=t.value.trim();
if(!v)return;t.value='';add('me','你：',v);
const r=await (await fetch('/api/chat',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:v})})).json();
add('ai','小凌：',r.ok?r.reply:('[错误] '+r.error));}
async function runCmd(){const c=document.getElementById('cmd');const v=c.value.trim();
if(!v)return;const r=await (await fetch('/api/command',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({command:v})})).json();
document.getElementById('cmdout').textContent=JSON.stringify(r,null,2);}
async function refresh(){
const s=await (await fetch('/api/status')).json();
document.getElementById('status').textContent=JSON.stringify(s,null,2);
const m=await (await fetch('/api/models')).json();
const ul=document.getElementById('models');ul.innerHTML='';
const sel=document.getElementById('mdl');sel.innerHTML='';
if(m.ok){const ins=(m.installed||[]).map(x=>x.name);
(m.presets||[]).forEach(n=>{const li=document.createElement('li');
li.innerHTML='<span>'+n+'</span><span class="tag '+
(ins.includes(n)?'on':'')+'">'+(ins.includes(n)?'已安装':'未安装')+'</span>';
ul.appendChild(li);
const o=document.createElement('option');o.value=n;o.textContent=n;sel.appendChild(o);});
(m.local||[]).forEach(x=>{const li=document.createElement('li');
li.innerHTML='<span>'+x.name+' <span class="tag">本地</span></span>';ul.appendChild(li);});
(m.api||[]).forEach(x=>{const li=document.createElement('li');
li.innerHTML='<span>'+x.name+' <span class="tag">API</span></span>';
ul.appendChild(li);});}
const p=await (await fetch('/api/plugins')).json();
const pu=document.getElementById('plugins');pu.innerHTML='';
if(p.ok)p.plugins.forEach(x=>{const li=document.createElement('li');
li.innerHTML='<span>'+x.name+'</span><button onclick="tg(\\''+x.name+'\\','+
(!x.enabled)+')">'+(x.enabled?'关闭':'开启')+'</button>';pu.appendChild(li);});}
async function tg(n,e){await fetch('/api/plugin/toggle',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:n,enabled:e})});refresh();}
async function dl(){const n=document.getElementById('mdl').value;
const r=await (await fetch('/api/model/dl',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:n})})).json();
document.getElementById('dlout').textContent=JSON.stringify(r,null,2);}
refresh();setInterval(refresh,8000);
</script></body></html>"""


# --------------------------------------------------------------------------- 3D 查看器静态资源
# 桌面端 / 移动端都是用 WebView 打开 http://127.0.0.1:<port>/viewer.html 来渲染真 3D，
# 所以这里必须能把 viewer 页面、three.js 运行时、以及 .vrm 模型都吐出去。
# 安全约束：只认白名单根目录 + 只接受相对路径，任何 ../ 或绝对路径一律 404，
# 且服务只绑 127.0.0.1，不对外暴露。

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".svg": "image/svg+xml",
    ".vrm": "model/gltf-binary", ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json", ".bin": "application/octet-stream",
}


def _resource(*parts) -> Path | None:
    """解析 resources/ 下的文件（兼容开发态与 PyInstaller 打包态）。"""
    try:
        from core import config
        p = config.resource(*parts)
        return Path(p) if p and Path(p).exists() else None
    except Exception:
        try:
            from backend.core import config
            p = config.resource(*parts)
            return Path(p) if p and Path(p).exists() else None
        except Exception:
            return None


def _static_root(kind: str) -> tuple[Path | None, str]:
    """返回（根目录, 子路径前缀）。找不到就返回 (None, '')。"""
    if kind == "web":
        return _resource("web") or _resource("resources", "web"), "web"
    if kind == "models":
        return _model_roots()[0] if _model_roots() else None, "models"
    return None, ""


def _model_roots() -> list:
    """VRM 形象可能来自多处，都要能吐给前端：

    1. 随包自带的 ``resources/models``（开发态就是仓库里的那个目录，
       打包态在 exe 旁边）；
    2. 用户后来登记 / 下载的 ``<app>/.star_core/models``；
    3. 用户在配置里登记的额外目录 ``model_extra_dirs``（自定义扫描入口）。

    统一交给 :func:`core.config.model_roots` 决定，避免这里和
    ``server.ListModels`` 各维护一份白名单导致"能列出来却加载不了"。
    这里只做包路径解析差异的兜底（``core`` / ``backend.core`` 两种导入名）。"""
    for mod in ("core.config", "backend.core.config"):
        try:
            import importlib
            roots = importlib.import_module(mod).model_roots()
            return [Path(r) for r in roots]
        except Exception:
            continue
    # 兜底：config 不可用时退回旧的固定白名单，绝不让查看器整体挂掉。
    out: list = []
    for r in (_resource("models"), _resource("resources", "models")):
        if r:
            out.append(Path(r))
    try:
        from core import config
        base = Path(config.app_dir())
        for c in (base / "models", base / ".star_core" / "models"):
            if c.is_dir():
                out.append(c)
    except Exception:
        pass
    seen, res = set(), []
    for r in out:
        s = str(r)
        if s not in seen:
            seen.add(s)
            res.append(r)
    return res


def _resolve_model(rel: str) -> Path | None:
    """在模型目录里找 rel。

    只接受**相对路径**（允许子目录，如 ``角色/小凌.vrm``），但绝不接受
    ``../`` 越界、绝对路径或盘符 —— 越界一律返回 None。中文文件名由调用方
    ``unquote`` 后传入，这里按原样匹配，不做任何转义。"""
    if not rel:
        return None
    rel = str(rel).replace("\\", "/").strip()
    while rel.startswith("/"):
        rel = rel[1:]
    if not rel or rel.startswith("../") or "/../" in rel or rel.endswith("/.."):
        return None
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        return None
    # 1) 直接按相对路径命中（含子目录）
    for root in _model_roots():
        f = _safe_join(root, rel)
        if f is not None:
            return f
    # 2) 前端只传 basename（或文件在自定义目录的子目录里）时，
    #    递归在各根目录下按文件名找 —— 上面的 _safe_join 只探根目录一层，
    #    不会命中 ``<extra>/我的VRM/乙.vrm`` 这种嵌套位置。
    base = rel.rsplit("/", 1)[-1]
    if base:
        for root in _model_roots():
            try:
                for p in sorted(root.rglob(base)):
                    # 二次确认仍在根目录内，避免符号链接之类的意外越界
                    if p.is_file() and _safe_join(root, str(
                            p.relative_to(root))) is not None:
                        return p
            except Exception:
                continue
    return None


def _safe_join(root: Path | None, rel: str) -> Path | None:
    """把 rel 限制在 root 之内；越界返回 None。

    越界判定用 ``Path.relative_to`` 而不是字符串前缀比较 ——
    前缀比较会把 ``D:\\models2\\x.vrm`` 误判成在 ``D:\\models`` 之内。
    Windows 下大小写不敏感，比较前统一 lower()。
    """
    if root is None or not rel:
        return None
    rel = str(rel).replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("..") or "/../" in rel or rel.endswith("/.."):
        return None
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        return None
    try:
        base = root.resolve()
        cand = (root / rel).resolve()
        cand.relative_to(base)
    except Exception:
        return None
    return cand if cand.is_file() else None


def _list_vrm() -> dict:
    """列出可渲染的 3D 形象（供前端形象选择器用）。

    递归扫描各模型根（含用户自定义目录），按文件名去重。
    只读不删：任何目录读不动就跳过，不影响其余目录。"""
    out, seen = [], set()
    for root in _model_roots():
        try:
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*")):
                try:
                    if not p.is_file() or p.suffix.lower() not in (
                            ".vrm", ".fbx", ".glb", ".gltf"):
                        continue
                    if p.name in seen:
                        continue
                    seen.add(p.name)
                    out.append({"name": p.name, "size": p.stat().st_size})
                except Exception:
                    continue
        except Exception:
            continue
    return {"ok": True, "models": out}


def _lipsync(audio_path: str) -> dict:
    """分析音频文件，返回 viseme 时间轴。不可用时如实报错。"""
    if not audio_path:
        return {"ok": False, "error": "缺少音频路径", "visemes": []}
    p = Path(audio_path)
    if not p.is_file():
        return {"ok": False, "error": f"音频文件不存在：{audio_path}", "visemes": []}
    try:
        from .lip_sync import LipSync
    except Exception:
        try:
            from lip_sync import LipSync
        except Exception as e:
            return {"ok": False, "error": f"口型模块不可用：{e}", "visemes": []}
    try:
        return LipSync().analyze_viseme(str(p))
    except Exception as e:
        return {"ok": False, "error": f"口型分析失败：{type(e).__name__}: {e}",
                "visemes": []}


def _parse_range(header: str, size: int):
    """把 Range 头解析成 (start, end)（闭区间）。

    返回 None 表示"没有可用的范围请求"（包括多段范围 —— 我们不支持，
    按整文件返回是 RFC 7233 允许的降级做法，但必须如实，不能假装支持）。
    返回 False 表示格式合法但越界，应回 416。
    """
    if not header or not header.strip().lower().startswith("bytes="):
        return None
    spec = header.strip()[len("bytes="):]
    if "," in spec:  # 多段范围：不实现 multipart，退回整文件
        return None
    start, _, end = spec.partition("-")
    try:
        if start == "":
            if end == "":
                return None
            n = int(end)
            if n <= 0:
                return False
            s = max(0, size - n)
            return (s, size - 1)
        s = int(start)
        e = size - 1 if end == "" else int(end)
    except ValueError:
        return None
    if s < 0 or s >= size or e < s:
        return False
    return (s, min(e, size - 1))


def _serve_file(handler, path: Path, cache: bool = False, head: bool = False):
    """静态文件服务，支持 Range（分段下载）。

    为什么必须有 Range：three.js / GLTFLoader 走 XHR，WebView 与部分系统
    HTTP 栈会主动带 Range 头；如果这里无视 Range 直接回 200 全量，
    客户端按 206 的语义解析就会拿到错位的数据，表现正是"3D 形象加载不出来"。
    """
    try:
        size = path.stat().st_size
    except Exception as e:  # noqa: BLE001
        handler._json({"ok": False, "error": f"读取失败：{e}"}, 404 if isinstance(e, FileNotFoundError) else 500)
        return
    ctype = _MIME.get(path.suffix.lower(), "application/octet-stream")
    rng = _parse_range(handler.headers.get("Range", ""), size)
    if rng is False:
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{size}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    if rng is None:
        start, end, code = 0, size - 1, 200
    else:
        start, end = rng
        code = 206
    length = end - start + 1
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(length))
    handler.send_header("Accept-Ranges", "bytes")
    if code == 206:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    if cache:
        handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    if head:  # HEAD：只回头，不回体（内容协商探测用）
        return
    try:
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)
    except Exception:
        pass


# 访问日志默认静音（不然每次轮询都刷屏）。
# 排查 3D 白屏时打开：XIAOLING_ACCESS_LOG=1 —— 就能看到 WebView 到底有没有
# 来取 viewer.html / three.js / .vrm，还是压根没连上。
_ACCESS_LOG = os.environ.get("XIAOLING_ACCESS_LOG") == "1"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静音默认访问日志
        if _ACCESS_LOG:
            try:
                print("[http] " + (fmt % args), flush=True)
            except Exception:
                pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command == "HEAD":
            return  # HEAD 只回头，长度照样给（RFC 9110 §9.3.2）
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self, head: bool = False):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/status":
            self._json(_status())
        elif path == "/api/models":
            self._json(_models())
        elif path == "/api/plugins":
            self._json(_plugins())
        elif path == "/api/dl/state":
            self._json({"running": _DL_STATE.get("running"),
                        "result": _DL_STATE.get("result"),
                        "log": _DL_STATE.get("log", [])[-5:]})
        # ---- 3D 查看器 ----
        elif path in ("/viewer", "/viewer/", "/viewer.html"):
            f = _safe_join(_static_root("web")[0], "viewer.html")
            if f is None:
                self._json({"ok": False, "error": "未找到 resources/web/viewer.html"}, 404)
            else:
                _serve_file(self, f, head=head)
        elif path.startswith("/vendor/"):
            # URL 里的 /vendor/ 只是命名空间，真实文件在 <web 根>/vendor/ 下，
            # 所以这里要把 "vendor/" 拼回去，否则一律 404。
            f = _safe_join(_static_root("web")[0],
                           "vendor/" + unquote(path[len("/vendor/"):]))
            if f is None:
                self._json({"ok": False, "error": "not found"}, 404)
            else:
                _serve_file(self, f, cache=True, head=head)
        elif path.startswith("/models/"):
            f = _resolve_model(unquote(path[len("/models/"):]))
            if f is None:
                self._json({"ok": False, "error": "模型不存在"}, 404)
            else:
                _serve_file(self, f, cache=True, head=head)
        elif path == "/api/vrm/list":
            self._json(_list_vrm())
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    def do_HEAD(self):
        # 以前没有 do_HEAD → BaseHTTPRequestHandler 回 501，
        # WebView / 下载器拿不到探测结果就会把整条链路判成"服务不可用"。
        # 复用 GET 的路由，只是 _serve_file / _send 在 HEAD 下不发响应体。
        self.do_GET(head=True)

    def do_POST(self):
        path = urlparse(self.path).path
        b = self._body()
        if path == "/api/chat":
            self._json(_chat(str(b.get("text") or "")))
        elif path == "/api/command":
            self._json(_command(str(b.get("command") or "")))
        elif path == "/api/plugin/toggle":
            self._json(_toggle_plugin(str(b.get("name") or ""),
                                      b.get("enabled")))
        elif path == "/api/model/dl":
            self._json(_download_async(str(b.get("name") or "")))
        elif path == "/api/lipsync":
            self._json(_lipsync(str(b.get("path") or "")))
        else:
            self._json({"ok": False, "error": "not found"}, 404)


def _make_server(port: int, host: str = "127.0.0.1"):
    """建服务器；端口被占用时自动顺延最多 20 个。

    Windows 上后端可能被重复启动（或上次没退干净），死等 8765 会让 3D
    一直白屏，所以这里直接往后找空位，并把**真实端口**回传给调用方。

    探测必须显式独占 bind：http.server 默认 allow_reuse_address=1，
    Windows 的 SO_REUSEADDR 语义允许「抢占」别人已 listen 的端口并返回
    成功 —— 日志打印已监听，实际连到的却是别的软件（或根本不通），
    表现是「3D 一直加载不出来」。SO_EXCLUSIVEADDRUSE 才是 Windows 的
    独占语义；POSIX 无此项，退回默认行为。
    """
    for p in range(int(port), int(port) + 20):
        probe = None
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                probe.setsockopt(socket.SOL_SOCKET,
                                 socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind((host, p))
            probe.close()
            probe = None
            return ThreadingHTTPServer((host, p), _Handler), p
        except OSError:
            if probe is not None:
                try:
                    probe.close()
                except Exception:
                    pass
            continue
    return None, int(port)


# 真实监听端口。前端**不该**靠扫 8765~8785 猜：顺延一次就落在扫描窗口外，
# 表现是「3D 角色一直加载不出来」；更糟的是同号端口可能属于别的软件，
# 扫过去会渲染出莫名其妙的页面。这里记下真值，由 gRPC 的 system:ports
# 直接告诉前端，同时落一份 web_port.json 供外部工具查。
_WEB_STATE = {"port": 0, "host": "", "error": ""}


def web_state() -> dict:
    """当前查看器服务的真实状态（未启动时 port=0，并带 error 说明）。"""
    return dict(_WEB_STATE)


def _record_state(port: int, host: str, error: str = "") -> None:
    _WEB_STATE.update({"port": int(port or 0), "host": host, "error": error})
    try:
        from core import config
        d = Path(config.app_dir()) / "data"
    except Exception:
        d = Path.cwd() / "data"
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / "web_port.json").write_text(
            json.dumps({"port": int(port or 0), "host": host,
                        "error": error}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def run_blocking(port: int = 8765, host: str = "127.0.0.1"):
    """阻塞运行 Web 面板（同时托管 3D 查看器）。"""
    srv, real = _make_server(port, host)
    if srv is None:
        msg = f"端口 {port}~{int(port) + 19} 都被占用"
        _record_state(0, host, msg)
        print(f"  [Web 面板] {msg}，已跳过")
        return int(port)
    _record_state(real, host)
    print(f"  [Web 面板] http://{host}:{real}  （浏览器打开即可与后端对话）")
    print(f"  [3D 查看器] http://{host}:{real}/viewer.html")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            srv.server_close()
        except Exception:
            pass
    return real


def serve_background(port: int = 8765, host: str = "127.0.0.1") -> int:
    """后台线程运行（仅托管 3D 查看器与 API，不阻塞主线程）。

    `--no-web` 启动时需要它 —— 否则 Flutter 的 WebView 拿不到 viewer.html，
    桌面端就永远只能看 2D 占位图。

    返回实际监听端口；失败返回 0。真实端口写进 web_state() 与
    ``<data>/web_port.json``，前端通过 gRPC `system:ports` 直接问，
    不必再盲扫。"""
    srv, real = _make_server(port, host)
    if srv is None:
        _record_state(0, host, f"端口 {port}~{int(port) + 19} 都被占用")
        return 0
    threading.Thread(target=srv.serve_forever, daemon=True,
                     name="xl-web").start()
    _record_state(real, host)
    print(f"  [3D 查看器] http://{host}:{real}/viewer.html")
    return real


if __name__ == "__main__":
    run_blocking()
