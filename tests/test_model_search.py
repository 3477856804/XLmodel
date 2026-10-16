"""远端搜索与下载函数的单元测试（不联网）。

覆盖：
- search_remote：正常解析、空 query 拒绝、HTTP 错误、非 JSON、success=false、脏数据过滤
- remote_model_files：正常解析、repo 校验
- download_remote：repo 校验（..、a/b/c、无斜杠、%2e%2e 全部拒绝）
- 续传判定：200+Content-Range 起始=have → ab 追加；200 无 Content-Range → wb 从头
- recommend_for_hardware：ram=0 → available=False 且无 recommended=True；
  正常 16GB+有 CUDA → available=True 且恰有一个 recommended=True
"""
import io
import json
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core import model


# ---------------------------------------------------------------------------
# 辅助：构造一个假的 urlopen 响应
# ---------------------------------------------------------------------------
class _FakeResp:
    """模拟 urllib.request.urlopen 返回的 response 对象。

    read(n) 必须**按顺序**吐字节、并在读完时返回 b''：被测的下载循环是
    `while True: chunk = r.read(512*1024); if not chunk: break`。
    要是这里每次都返回整块数据，循环永远不会结束，会把磁盘写满
    （这不是假想，第一版就是这么把 / 撑爆的）。
    """

    def __init__(self, data, status=200, headers=None):
        if isinstance(data, dict) or isinstance(data, list):
            self._body = json.dumps(data).encode("utf-8")
        elif isinstance(data, bytes):
            self._body = data
        else:
            self._body = str(data).encode("utf-8")
        self.status = status
        self._headers = headers or {}
        self._pos = 0

    def read(self, n=-1):
        if n is None or n < 0:
            out, self._pos = self._body[self._pos:], len(self._body)
        else:
            out = self._body[self._pos:self._pos + n]
            self._pos += len(out)
        return out

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    @property
    def headers(self):
        return self._headers


# ---------------------------------------------------------------------------
# search_remote
# ---------------------------------------------------------------------------
def test_search_remote_normal(monkeypatch):
    """正常解析：total/page 回填、字段归一化、description 截断。"""
    long_desc = "x" * 300
    payload = {
        "success": True,
        "data": {
            "models": [
                {
                    "id": "Qwen/Qwen2.5-7B-Instruct",
                    "display_name": "Qwen2.5 7B",
                    "description": long_desc,
                    "downloads": 12345,
                    "likes": 99,
                    "license": "apache-2.0",
                    "tasks": ["text-generation"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_modified": "2024-06-15T12:34:56Z",
                    "file_size": 4466000000,
                    "params": "7B",
                    "tags": ["chat", "qwen"],
                    "private": False,
                    "gated": False,
                },
                {
                    "id": "meta-llama/Llama-3.2-1B",
                    "display_name": "Llama 3.2 1B",
                    "description": "short",
                    "downloads": 100,
                    "likes": 5,
                    "license": "llama3.2",
                    "tasks": [],
                    "last_modified": "2024-09-01",
                    "file_size": 770000000,
                    "params": "1B",
                    "tags": [],
                    "private": True,
                    "gated": True,
                },
            ],
            "total_count": 5200,
            "page_number": 1,
            "page_size": 2,
        },
    }

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url if hasattr(req, "full_url") else str(req)
        return _FakeResp(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    res = model.search_remote("qwen", page=1, page_size=2)
    assert res["ok"] is True
    assert res["total"] == 5200
    assert res["page"] == 1
    assert res["page_size"] == 2
    assert res["source"] == "modelscope"
    assert len(res["models"]) == 2

    m0 = res["models"][0]
    assert m0["repo"] == "Qwen/Qwen2.5-7B-Instruct"
    assert m0["name"] == "Qwen2.5-7B-Instruct"
    assert m0["display_name"] == "Qwen2.5 7B"
    assert len(m0["description"]) == 201  # 200 + "…"
    assert m0["description"].endswith("…")
    assert m0["downloads"] == 12345
    assert m0["likes"] == 99
    assert m0["license"] == "apache-2.0"
    assert m0["tasks"] == ["text-generation"]
    assert m0["size_mb"] == 4466
    assert m0["params"] == "7B"
    assert m0["tags"] == ["chat", "qwen"]
    assert m0["private"] is False
    assert m0["gated"] is False
    assert m0["updated"] == "2024-06-15"

    m1 = res["models"][1]
    assert m1["private"] is True
    assert m1["gated"] is True
    assert m1["updated"] == "2024-09-01"

    # 确认请求 URL 包含搜索词
    assert "search=qwen" in captured["url"]


def test_search_remote_empty_query(monkeypatch):
    """空 query 拒绝且不发请求（断言 urlopen 未被调用）。"""
    called = []

    def fake_urlopen(*a, **kw):
        called.append(1)
        return _FakeResp({"success": True, "data": {"models": []}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    for q in ("", None, "   "):
        res = model.search_remote(q)
        assert res["ok"] is False
        assert res["models"] == []
        assert "不能为空" in res["error"]
    assert called == []  # urlopen 从未被调用


def test_search_remote_http_error(monkeypatch):
    """HTTP 错误 → ok=False + error + models 为空。"""
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url if hasattr(req, "full_url") else "url",
            500, "Internal Server Error", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = model.search_remote("test")
    assert res["ok"] is False
    assert res["models"] == []
    assert res["error"]
    assert "HTTPError" in res["error"] or "500" in res["error"]


def test_search_remote_non_json(monkeypatch):
    """非 JSON 响应 → ok=False + error + models 为空。"""
    def fake_urlopen(req, timeout=None):
        return _FakeResp(b"<html>not json</html>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = model.search_remote("test")
    assert res["ok"] is False
    assert res["models"] == []
    assert res["error"]


def test_search_remote_success_false(monkeypatch):
    """success=false → ok=False + error + models 为空。"""
    def fake_urlopen(req, timeout=None):
        return _FakeResp({"success": False, "message": "rate limited"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = model.search_remote("test")
    assert res["ok"] is False
    assert res["models"] == []
    assert "success=false" in res["error"].lower() or "success" in res["error"].lower()


def test_search_remote_dirty_entries_filtered(monkeypatch):
    """无 id 的脏条目被过滤。"""
    payload = {
        "success": True,
        "data": {
            "models": [
                {"display_name": "no id"},  # 无 id
                {"id": "", "display_name": "empty id"},  # 空 id
                {"id": "valid/model", "display_name": "ok",
                 "last_modified": "2024-01-01", "file_size": 0},
            ],
            "total_count": 3,
            "page_number": 1,
            "page_size": 20,
        },
    }

    def fake_urlopen(req, timeout=None):
        return _FakeResp(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = model.search_remote("test")
    assert res["ok"] is True
    assert len(res["models"]) == 1
    assert res["models"][0]["repo"] == "valid/model"


# ---------------------------------------------------------------------------
# remote_model_files
# ---------------------------------------------------------------------------
def test_remote_model_files_normal(monkeypatch):
    """正常解析文件列表和 gguf 筛选。"""
    payload = {
        "Code": 200,
        "Data": {
            "Files": [
                {"Path": "README.md", "Size": 1024, "IsLFS": False},
                {"Path": "model-q4_k_m.gguf", "Size": 4466000000, "IsLFS": True},
                {"Path": "model-q8_0.gguf", "Size": 8000000000, "IsLFS": True},
            ]
        },
    }

    def fake_urlopen(req, timeout=None):
        return _FakeResp(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = model.remote_model_files("Qwen/Qwen2.5-7B-Instruct-GGUF")
    assert res["ok"] is True
    assert len(res["files"]) == 3
    assert len(res["gguf"]) == 2
    assert "model-q4_k_m.gguf" in res["gguf"]
    assert res["files"][1]["size_mb"] == 4466.0
    assert res["files"][1]["is_lfs"] is True


def test_remote_model_files_invalid_repo(monkeypatch):
    """repo 校验失败 → ok=False。"""
    called = []

    def fake_urlopen(*a, **kw):
        called.append(1)
        return _FakeResp({"Code": 200, "Data": {"Files": []}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    for bad in ("noslash", "a/b/c", "../etc", "a%2Fb"):
        res = model.remote_model_files(bad)
        assert res["ok"] is False
        assert "不合法" in res["error"]
    assert called == []


# ---------------------------------------------------------------------------
# download_remote repo 校验
# ---------------------------------------------------------------------------
def test_download_remote_repo_validation(monkeypatch):
    """..、a/b/c、无斜杠、含 %2e%2e 全部拒绝且不发请求。"""
    called = []

    def fake_urlopen(*a, **kw):
        called.append(1)
        return _FakeResp({"Code": 200, "Data": {"Files": []}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    for bad in ("..", "a/b/c", "noslash", "a%2e%2eb/c", "a/..", "a\\b"):
        res = model.download_remote(bad)
        assert res["ok"] is False
        assert "不合法" in res["error"]
    assert called == []


# ---------------------------------------------------------------------------
# 续传判定
# ---------------------------------------------------------------------------
def test_resume_200_with_content_range_appends(monkeypatch, tmp_path):
    """伪造 200+Content-Range 起始=已有字节数 → 断言以 ab 追加打开。"""
    # 准备一个已有部分数据的 .part 文件
    part_path = tmp_path / "model-q4_k_m.gguf.part"
    existing = b"EXISTING_DATA_" * 100  # 1400 bytes
    part_path.write_bytes(existing)
    have = len(existing)

    # 伪造 HEAD 响应（探大小）
    # 伪造 GET 响应：200 + Content-Range 起始=have
    new_data = b"NEW_CHUNK_DATA"

    call_count = {"head": 0, "get": 0}
    open_modes = []

    original_open = open

    def tracking_open(path, mode="r", *a, **kw):
        if str(path).endswith(".part") and "b" in mode:
            open_modes.append(mode)
        return original_open(path, mode, *a, **kw)

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        method = req.get_method() if hasattr(req, "get_method") else "GET"
        if method == "HEAD":
            call_count["head"] += 1
            return _FakeResp(b"", status=200,
                             headers={"Content-Length": str(have + len(new_data))})
        else:
            call_count["get"] += 1
            cr = f"bytes {have}-{have + len(new_data) - 1}/{have + len(new_data)}"
            return _FakeResp(new_data, status=200,
                             headers={"Content-Range": cr,
                                      "Content-Length": str(len(new_data))})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("builtins.open", tracking_open)

    # 直接调 _download_gguf_repo
    res = model._download_gguf_repo(
        "test/repo", ["model-q4_k_m.gguf"], tmp_path,
        quant="Q4_K_M", timeout=5.0)

    assert res["ok"] is True
    assert "ab" in open_modes, f"Expected 'ab' in open modes, got {open_modes}"
    # 最终文件应该是 existing + new_data
    final = tmp_path / "model-q4_k_m.gguf"
    assert final.read_bytes() == existing + new_data


def test_resume_200_no_content_range_restarts(monkeypatch, tmp_path):
    """伪造 200 无 Content-Range → 断言从头 wb。"""
    part_path = tmp_path / "model-q4_k_m.gguf.part"
    existing = b"OLD_GARBAGE_" * 50
    part_path.write_bytes(existing)

    full_data = b"FULL_FILE_DATA_" * 100
    open_modes = []

    original_open = open

    def tracking_open(path, mode="r", *a, **kw):
        if str(path).endswith(".part") and "b" in mode:
            open_modes.append(mode)
        return original_open(path, mode, *a, **kw)

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        method = req.get_method() if hasattr(req, "get_method") else "GET"
        if method == "HEAD":
            return _FakeResp(b"", status=200,
                             headers={"Content-Length": str(len(full_data))})
        else:
            # 200 无 Content-Range → 服务端不支持续传
            return _FakeResp(full_data, status=200,
                             headers={"Content-Length": str(len(full_data))})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("builtins.open", tracking_open)

    res = model._download_gguf_repo(
        "test/repo", ["model-q4_k_m.gguf"], tmp_path,
        quant="Q4_K_M", timeout=5.0)

    assert res["ok"] is True
    assert "wb" in open_modes, f"Expected 'wb' in open modes, got {open_modes}"
    final = tmp_path / "model-q4_k_m.gguf"
    assert final.read_bytes() == full_data


# ---------------------------------------------------------------------------
# recommend_for_hardware
# ---------------------------------------------------------------------------
def test_recommend_hardware_ram_zero(monkeypatch):
    """ram=0 → available=False 且无任何 recommended=True。"""
    fake_hw = model.HardwareInfo(
        platform="Linux", machine="x86_64", cpu="Test CPU",
        cpu_cores=4, ram_total_gb=0.0, ram_available_gb=0.0,
        gpu_name="", gpu_memory_gb=0.0,
        has_cuda=False, has_metal=False, has_rocm=False,
        disk_free_gb=50.0, disk_total_gb=100.0,
    )
    monkeypatch.setattr(model, "detect_hardware", lambda: fake_hw)

    res = model.recommend_for_hardware()
    assert res["ok"] is True
    assert res["available"] is False
    assert "未能识别" in res["why"] or "未能" in res["why"]
    # 没有任何模型被标为 recommended=True
    assert all(not m.get("recommended") for m in res["models"])
    # detected 字段如实反映
    assert res["detected"]["ram_total_gb"] == 0.0


def test_recommend_hardware_normal_16gb_cuda(monkeypatch):
    """正常 16GB + 有 CUDA → available=True 且恰有一个 recommended=True。"""
    fake_hw = model.HardwareInfo(
        platform="Linux", machine="x86_64", cpu="Test CPU",
        cpu_cores=8, ram_total_gb=16.0, ram_available_gb=12.0,
        gpu_name="NVIDIA RTX 3060", gpu_memory_gb=8.0,
        has_cuda=True, has_metal=False, has_rocm=False,
        disk_free_gb=100.0, disk_total_gb=500.0,
    )
    monkeypatch.setattr(model, "detect_hardware", lambda: fake_hw)

    res = model.recommend_for_hardware()
    assert res["ok"] is True
    assert res["available"] is True
    assert res["detected"]["ram_total_gb"] == 16.0
    assert res["detected"]["has_cuda"] is True
    assert res["detected"]["vram_gb"] == 8.0
    # 恰有一个 recommended=True
    rec_count = sum(1 for m in res["models"] if m.get("recommended"))
    assert rec_count == 1, f"Expected exactly 1 recommended, got {rec_count}"
    # tier 应该是 HardwareInfo.tier() 的真实返回值
    assert res["tier"] == fake_hw.tier()
    # why 应引用 RAM/VRAM 数字
    assert "16.0" in res["why"] or "16" in res["why"]
