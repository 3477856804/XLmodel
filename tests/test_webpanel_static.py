#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3D 资源服务链路回归测试（Range / HEAD / 真实 .vrm 可下载）。

为什么单独一个文件：这组用例直接打的是"前端 WebView 取形象"那条链路。
之前 webpanel 的 _serve_file 无视 Range、且类里没有 do_HEAD，
表现就是"3D 模型加载不出来"——而这条链路上没有任何测试，所以没人发现。
"""
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / 'backend'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest  # noqa: E402

from backend.core import webpanel  # noqa: E402

# --------------------------------------------------------------------------
# 纯函数：Range 解析
# --------------------------------------------------------------------------


@pytest.mark.parametrize("header,expect", [
    ("", None),                                  # 无 Range → 整文件
    ("bytes=0-99", (0, 99)),
    ("bytes=100-199", (100, 199)),
    ("bytes=200-", (200, 255)),                  # 开区间 → 到文件尾
    ("bytes=-50", (206, 255)),                   # 后缀范围 → 最后 50 字节
    ("bytes=0-9999", (0, 255)),                  # 超界 end → 截到文件尾
    ("BYTES=0-9", (0, 9)),                       # 大小写不敏感
    (" bytes=0-9 ", (0, 9)),                     # 前后空白
    ("bytes=0-9,20-29", None),                   # 多段：不实现，退回整文件（如实）
    ("items=0-9", None),                         # 非 bytes 单位
    ("bytes=abc-def", None),                     # 非法数字
    ("bytes=-", None),                           # 两头都空
])
def test_parse_range(header, expect):
    assert webpanel._parse_range(header, 256) == expect


@pytest.mark.parametrize("header", [
    "bytes=256-",          # start 越界（== size 也不算）
    "bytes=300-400",       # 完全越界
    "bytes=100-50",        # end < start
    "bytes=-0",            # 后缀 0 字节无意义
])
def test_parse_range_unsatisfiable(header):
    assert webpanel._parse_range(header, 256) is False


# --------------------------------------------------------------------------
# 端到端：起一个真服务器，取真文件
# --------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """在临时目录里放一个模型与一个 viewer.html，起真 HTTP 服务。"""
    web_dir = tmp_path / 'web'
    web_dir.mkdir()
    (web_dir / 'viewer.html').write_text('<html>ok</html>', encoding='utf-8')
    models_dir = tmp_path / 'models'
    models_dir.mkdir()
    payload = bytes(range(256)) * 4  # 1024 字节，位置可预测
    vrm = models_dir / '测试.vrm'
    vrm.write_bytes(payload)

    monkeypatch.setattr(webpanel, '_static_root',
                        lambda kind: (web_dir if kind == 'web' else None, kind))
    monkeypatch.setattr(webpanel, '_model_roots', lambda: [models_dir])
    monkeypatch.setattr(webpanel, '_resolve_model', lambda rel: (
        vrm if rel in ('测试.vrm', './测试.vrm') else None))

    httpd = webpanel.ThreadingHTTPServer(('127.0.0.1', _free_port()),
                                         webpanel._Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f'http://127.0.0.1:{httpd.server_address[1]}'
    try:
        yield base, payload
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, dict(r.headers), r.read()


def test_full_get_byte_identical(srv):
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm')
    assert code == 200
    assert body == payload
    assert hdr.get('Accept-Ranges') == 'bytes'
    assert hdr.get('Content-Length') == str(len(payload))
    assert 'Content-Range' not in hdr


def test_range_prefix(srv):
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                           {'Range': 'bytes=0-99'})
    assert code == 206
    assert body == payload[:100]
    assert hdr['Content-Range'] == f'bytes 0-99/{len(payload)}'
    assert hdr['Content-Length'] == '100'


def test_range_middle(srv):
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                           {'Range': 'bytes=300-499'})
    assert code == 206
    assert body == payload[300:500]
    assert hdr['Content-Range'] == f'bytes 300-499/{len(payload)}'


def test_range_open_ended(srv):
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                           {'Range': f'bytes={len(payload) - 64}-'})
    assert code == 206
    assert body == payload[-64:]


def test_range_suffix(srv):
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                           {'Range': 'bytes=-128'})
    assert code == 206
    assert body == payload[-128:]


def test_range_assembled_equals_full(srv):
    """分段拼接必须与整文件一致 —— 这是下载器续传的正确性前提。"""
    base, payload = srv
    url = base + '/models/%E6%B5%8B%E8%AF%95.vrm'
    parts = []
    for a in range(0, len(payload), 200):
        _, _, body = _get(url, {'Range': f'bytes={a}-{min(a + 199, len(payload) - 1)}'})
        parts.append(body)
    assert b''.join(parts) == payload


def test_range_unsatisfiable_416(srv):
    base, payload = srv
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
             {'Range': f'bytes={len(payload) + 10}-'})
    assert e.value.code == 416
    assert e.value.headers['Content-Range'] == f'bytes */{len(payload)}'


def test_multi_range_degrades_to_full(srv):
    """多段范围不支持时按整文件回 200（RFC 7233 允许），绝不能伪装成 206。"""
    base, payload = srv
    code, hdr, body = _get(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                           {'Range': 'bytes=0-9,20-29'})
    assert code == 200
    assert 'Content-Range' not in hdr
    assert body == payload


def test_head_returns_headers_without_body(srv):
    """回归：以前没有 do_HEAD → 501，前端把服务判成不可用。"""
    base, payload = srv
    req = urllib.request.Request(base + '/models/%E6%B5%8B%E8%AF%95.vrm',
                                 method='HEAD')
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200
        assert r.headers['Content-Length'] == str(len(payload))
        assert r.headers['Accept-Ranges'] == 'bytes'
        assert r.read() == b''


def test_head_index_page(srv):
    req = urllib.request.Request('http://' + srv[0].split('//')[1] + '/',
                                 method='HEAD')
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200
        assert r.headers['Content-Type'].startswith('text/html')
        assert r.read() == b''


def test_head_missing_model_404(srv):
    base = srv[0]
    req = urllib.request.Request(base + '/models/nope.vrm', method='HEAD')
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 404


def test_viewer_html_served(srv):
    base, _ = srv
    code, _, body = _get(base + '/viewer.html')
    assert code == 200
    assert b'ok' in body


def test_viewer_head(srv):
    base, _ = srv
    req = urllib.request.Request(base + '/viewer.html', method='HEAD')
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200
        assert r.read() == b''


# --------------------------------------------------------------------------
# 真实资产：仓库里必须真的带着形象文件，且服务能原样吐出来
# --------------------------------------------------------------------------

REAL_VRM = ROOT / 'resources' / 'models' / '小凌.vrm'


@pytest.mark.skipif(not REAL_VRM.is_file(), reason='内置形象未入库')
def test_bundled_avatar_exists_and_is_valid_gltf():
    """3D 加载不出来的第一根因：资源压根没进版本库。这里做静态守门。"""
    size = REAL_VRM.stat().st_size
    assert size > 1_000_000, f'形象文件异常小：{size}'
    head = REAL_VRM.read_bytes()[:12]
    assert head[:4] == b'glTF', '不是 glTF 二进制'
    assert int.from_bytes(head[4:8], 'little') == 2, 'glTF 版本不是 2'
    declared = int.from_bytes(head[8:12], 'little')
    # 声明长度必须等于实际长度：不一致说明文件被截断（提交/打包丢字节）
    assert declared == size, f'glTF 声明 {declared} != 实际 {size}'


@pytest.mark.skipif(not REAL_VRM.is_file(), reason='内置形象未入库')
def test_bundled_avatar_survives_range_roundtrip(tmp_path, monkeypatch):
    base = _free_port()
    real = REAL_VRM
    web_dir = tmp_path / 'web'
    web_dir.mkdir()
    monkeypatch.setattr(webpanel, '_static_root',
                        lambda kind: (web_dir if kind == 'web' else None, kind))
    monkeypatch.setattr(webpanel, '_model_roots', lambda: [real.parent])
    httpd = webpanel.ThreadingHTTPServer(('127.0.0.1', base), webpanel._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{base}/models/{urllib.parse.quote(real.name)}'
    try:
        code, hdr, body = _get(url)
        assert code == 200
        assert body == real.read_bytes()
        assert hdr.get('Content-Type') == 'model/gltf-binary'
        # 取中段：证明 seek 逻辑对齐，不是"恰好前几字节对"
        _, _, mid = _get(url, {'Range': 'bytes=1000000-1000999'})
        assert mid == real.read_bytes()[1000000:1001000]
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q', '--override-ini=addopts=']))
