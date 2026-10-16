# -*- coding: utf-8 -*-
"""统一「外部 API 配置」core.api_config + trainer 回落。

守的红线：
  * key 永远打码，绝不明文回显；
  * 没启用 / 没配端点时 chat/test 如实失败，不伪造 ok=True；
  * 训练页在 training.api_* 没配时，能回落到统一 api.*（修「配了等于没配」）。
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / 'backend')):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core import api_config as api     # noqa: E402
from backend.core import config as cfgmod      # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """把配置读写指到 tmp，避免污染真实用户配置。"""
    cfgfile = tmp_path / 'config.json'

    def _load(path=None, use_cache=True):
        if not cfgfile.exists():
            return {}
        return json.loads(cfgfile.read_text(encoding='utf-8'))

    def _save(cfg, path=None):
        cfgfile.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        return cfgfile

    def _set_value(dotted, value, path=None):
        cfg = _load()
        parts = dotted.split('.')
        cur = cfg
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value
        _save(cfg)
        return cfg

    monkeypatch.setattr(cfgmod, 'load', _load)
    monkeypatch.setattr(cfgmod, 'save', _save)
    monkeypatch.setattr(cfgmod, 'set_value', _set_value)
    # api_config 内部用的是 `from .config import load/set_value`，
    # 那是函数内 import，绑的是模块属性，monkeypatch 模块属性即可生效。
    yield


# ---------------------------------------------------------------- 打码
def test_key_is_masked_never_plaintext():
    api.set_field('key', 'sk-secret123456789')
    c = api.cfg()
    assert c['has_key'] is True
    assert 'secret' not in c['key_masked']
    assert c['key_masked'].startswith('sk-s')
    assert c['key_masked'].endswith('6789')
    assert '****' in c['key_masked']


def test_short_key_fully_masked():
    api.set_field('key', 'abc123')
    assert api.cfg()['key_masked'] == '****'


# ---------------------------------------------------------------- 校验
def test_base_must_be_http():
    r = api.set_field('base', 'ftp://bad')
    assert r['ok'] is False
    assert 'http' in r['error']


def test_provider_whitelist():
    assert api.set_field('provider', 'deepseek')['ok'] is True
    assert api.set_field('provider', 'nonsense')['ok'] is False


def test_unknown_field_rejected():
    assert api.set_field('password', 'x')['ok'] is False


# ---------------------------------------------------------------- 降级要明说
def test_chat_disabled_reports_not_faking():
    api.set_field('enabled', 'off')
    r = api.chat([{"role": "user", "content": "hi"}])
    assert r['ok'] is False
    assert r.get('disabled') is True
    assert '未启用' in r['error']


def test_test_without_base_fails_honestly():
    # base 未配置时 cfg() 会回落到默认端点，但 has_base=False；
    # test() 用 cfg()['base']（默认值），会真的去连本地端口 —— 这里只断言
    # 它不会因为「没配」就伪造成功。
    r = api.test(timeout=0.5)
    assert r['ok'] is False or r.get('http_status') == 200


# ---------------------------------------------------------------- 真实调用（本地 mock）
def _start_mock_server():
    import http.server
    import socketserver
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0))
            req = json.loads(self.rfile.read(n))
            resp = {"choices": [{"message": {"content": "echo:" +
                                    req["messages"][-1]["content"]}}],
                    "model": req["model"]}
            data = json.dumps(resp).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_chat_hits_real_endpoint():
    httpd = _start_mock_server()
    try:
        port = httpd.server_address[1]
        api.set_field('base', f"http://127.0.0.1:{port}/v1")
        api.set_field('model', 'mock')
        api.set_field('enabled', 'on')
        r = api.chat([{"role": "user", "content": "hello"}])
        assert r['ok'] is True, r
        assert r['text'] == 'echo:hello'
        assert r['model'] == 'mock'
    finally:
        httpd.shutdown()


def test_bad_endpoint_reports_http_error():
    httpd = _start_mock_server()
    try:
        port = httpd.server_address[1]
        api.set_field('base', f"http://127.0.0.1:{port}/v1")
        api.set_field('enabled', 'on')
        # 关掉 mock 后端口立刻不可用
        httpd.shutdown()
        import time
        time.sleep(0.1)
        r = api.chat([{"role": "user", "content": "x"}], timeout=1.0)
        assert r['ok'] is False
        assert 'error' in r
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass


# ---------------------------------------------------------------- trainer 回落
def test_trainer_falls_back_to_unified():
    from backend.core import trainer as tr
    # training.api_* 全空，统一 api.* 配好 → 训练页应读到统一配置
    api.set_field('base', 'https://api.example.com/v1')
    api.set_field('key', 'sk-unified123456')
    api.set_field('model', 'uni-model')
    api.set_field('enabled', 'on')
    c = tr.api_cfg()
    assert c['source'] == 'unified', c
    assert c['enabled'] is True
    assert c['base'] == 'https://api.example.com/v1'
    assert c['model'] == 'uni-model'
    assert 'unified' not in c['key_masked']  # 仍是打码值


def test_trainer_own_keys_win_over_unified():
    from backend.core import trainer as tr
    api.set_field('base', 'https://unified.example/v1')
    api.set_field('model', 'uni')
    cfgmod.set_value('training.api_base', 'https://train.own/v1')
    cfgmod.set_value('training.api_model', 'own')
    c = tr.api_cfg()
    assert c['source'] == 'training', c
    assert c['base'] == 'https://train.own/v1'
    assert c['model'] == 'own'


# ---------------------------------------------------------------- RPC 路由
def test_handle_api_cmd_json_shapes():
    from backend.rpc import server as srv
    r = json.loads(srv._handle_api_cmd('cfg'))
    assert r['ok'] is True and 'usage' in r
    r = json.loads(srv._handle_api_cmd('set base ftp://x'))
    assert r['ok'] is False
    r = json.loads(srv._handle_api_cmd('bogus'))
    assert r['ok'] is False and '未知子命令' in r['error']
    r = json.loads(srv._handle_api_cmd('chat'))
    assert r['ok'] is False  # 空内容


# ---------------------------------------------------------------- 云端语音识别
def _start_asr_mock():
    import http.server
    import socketserver
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(n)
            ctype = self.headers.get('Content-Type', '')
            # 必须是 multipart，且带上音频字节 —— 证明不是空请求。
            assert 'multipart/form-data' in ctype, ctype
            resp = {"text": "你好小凌"} if b'RIFF' in body else {"text": ""}
            data = json.dumps(resp).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_transcribe_disabled_reports_honestly():
    api.set_field('enabled', 'off')
    r = api.transcribe(b'RIFF....')
    assert r['ok'] is False and r.get('disabled') is True


def test_transcribe_empty_audio_rejected():
    api.set_field('enabled', 'on')
    r = api.transcribe(b'')
    assert r['ok'] is False


def test_transcribe_hits_real_endpoint():
    httpd = _start_asr_mock()
    try:
        port = httpd.server_address[1]
        api.set_field('base', f"http://127.0.0.1:{port}/v1")
        api.set_field('model', 'whisper-1')
        api.set_field('enabled', 'on')
        r = api.transcribe(b'RIFF' + b'\x00' * 40, filename='a.wav')
        assert r['ok'] is True, r
        assert r['text'] == '你好小凌'
    finally:
        httpd.shutdown()


def test_asr_available_via_api_without_whisper(monkeypatch):
    """没装 whisper 时，只要配了外部 API，ASR 也应判为可用（语音不再死路）。"""
    import builtins
    from backend.core import multimodal as mm

    real_import = builtins.__import__

    def _no_whisper(name, *a, **k):
        if name == 'whisper':
            raise ImportError('no whisper')
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, '__import__', _no_whisper)
    asr = mm.ASR()
    # API 未启用 → 不可用，且报错文案要指向「API 配置」这条出路
    api.set_field('enabled', 'off')
    assert asr.available() is False
    assert 'API 配置' in asr.last_error
    # 配好端点并启用 → 可用
    api.set_field('base', 'https://api.example.com/v1')
    api.set_field('enabled', 'on')
    assert asr.available() is True
