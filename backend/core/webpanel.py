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
    """VRM 形象可能来自两处，都要能吐给前端：

    1. 随包自带的 ``resources/models``（开发态就是仓库里的那个目录，
       打包态在 exe 旁边）；
    2. 用户后来登记 / 下载的 ``<app>/.star_core/models``。

    只认这两个白名单目录，绝不开放任意路径读取。"""
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
    """在白名单模型目录里找 rel（只接受文件名，不接受 ../）。"""
    if not rel:
        return None
    if "/" in rel or "\\" in rel or rel.startswith(".."):
        return None
    for root in _model_roots():
        f = _safe_join(root, rel)
        if f is not None:
            return f
    return None


def _safe_join(root: Path | None, rel: str) -> Path | None:
    """把 rel 限制在 root 之内；越界返回 None。"""
    if root is None or not rel:
        return None
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("..") or "/../" in rel or rel.endswith("/.."):
        return None
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        return None
    cand = (root / rel).resolve()
    try:
        if not str(cand).startswith(str(root.resolve())):
            return None
    except Exception:
        return None
    return cand if cand.is_file() else None


def _list_vrm() -> dict:
    """列出可渲染的 VRM 形象（供前端形象选择器用）。"""
    out, seen = [], set()
    for root in _model_roots():
        if not root.is_dir():
            continue
        try:
            for p in sorted(root.iterdir()):
                if p.is_file() and p.suffix.lower() in (".vrm", ".glb") and p.name not in seen:
                    seen.add(p.name)
                    out.append({"name": p.name, "size": p.stat().st_size})
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


def _serve_file(handler, path: Path, cache: bool = False):
    try:
        data = path.read_bytes()
    except Exception as e:  # noqa: BLE001
        handler._json({"ok": False, "error": f"读取失败：{e}"}, 500)
        return
    ctype = _MIME.get(path.suffix.lower(), "application/octet-stream")
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Accept-Ranges", "bytes")
    if cache:
        handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    try:
        handler.wfile.write(data)
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

    def do_GET(self):
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
                _serve_file(self, f)
        elif path.startswith("/vendor/"):
            # URL 里的 /vendor/ 只是命名空间，真实文件在 <web 根>/vendor/ 下，
            # 所以这里要把 "vendor/" 拼回去，否则一律 404。
            f = _safe_join(_static_root("web")[0],
                           "vendor/" + unquote(path[len("/vendor/"):]))
            if f is None:
                self._json({"ok": False, "error": "not found"}, 404)
            else:
                _serve_file(self, f, cache=True)
        elif path.startswith("/models/"):
            f = _resolve_model(unquote(path[len("/models/"):]))
            if f is None:
                self._json({"ok": False, "error": "模型不存在"}, 404)
            else:
                _serve_file(self, f, cache=True)
        elif path == "/api/vrm/list":
            self._json(_list_vrm())
        else:
            self._json({"ok": False, "error": "not found"}, 404)

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
    一直白屏，所以这里直接往后找空位，并把**真实端口**回传给调用方。"""
    for p in range(int(port), int(port) + 20):
        try:
            return ThreadingHTTPServer((host, p), _Handler), p
        except OSError:
            continue
    return None, int(port)


def run_blocking(port: int = 8765, host: str = "127.0.0.1"):
    """阻塞运行 Web 面板（同时托管 3D 查看器）。"""
    srv, real = _make_server(port, host)
    if srv is None:
        print(f"  [Web 面板] 端口 {port}~{int(port) + 19} 都被占用，已跳过")
        return int(port)
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

    返回实际监听端口；失败返回 0。端口会写入
    ``<data>/web_port.json``，供前端直接读取，避免前后端口写死不同步。"""
    srv, real = _make_server(port, host)
    if srv is None:
        return 0
    threading.Thread(target=srv.serve_forever, daemon=True,
                     name="xl-web").start()
    try:
        from core import config
        d = Path(config.app_dir()) / "data"
    except Exception:
        d = Path.cwd() / "data"
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / "web_port.json").write_text(
            json.dumps({"port": real, "host": host}), encoding="utf-8")
    except Exception:
        pass
    print(f"  [3D 查看器] http://{host}:{real}/viewer.html")
    return real


if __name__ == "__main__":
    run_blocking()
