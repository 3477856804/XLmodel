# -*- coding: utf-8 -*-
"""pdf_reader 插件

PDF 文本提取：真实读取磁盘上的 PDF 文件，不硬编码任何 PDF 内容。

工具：
  - extract_text(pdf_path)            提取全文（附总页数）
  - read_page(pdf_path, page_num)     按 1-based 页码读取单页
  - search_in_pdf(pdf_path, keyword)  在全文中搜索关键词，返回命中页码

后端优先级：pypdf > PyPDF2 > pdfplumber。三者都没装时，所有工具返回
明确的"缺少依赖"错误；文件不存在 / 不是 PDF / 加密等也都明确报错。
"""
from __future__ import annotations

import os
import threading

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


def _detect_backend():
    """返回 (backend_name, module) 或 (None, None)。"""
    try:
        import pypdf  # type: ignore
        return "pypdf", pypdf
    except Exception:
        pass
    try:
        import PyPDF2  # type: ignore
        return "PyPDF2", PyPDF2
    except Exception:
        pass
    try:
        import pdfplumber  # type: ignore
        return "pdfplumber", pdfplumber
    except Exception:
        pass
    return None, None


def _open_pages(pdf_path: str):
    """返回 (backend_name, [page_text, ...], total_pages)。"""
    name, mod = _detect_backend()
    if mod is None:
        raise RuntimeError(
            "未安装任何 PDF 解析库（pypdf / PyPDF2 / pdfplumber 均不可用）")
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError("PDF 文件不存在: {}".format(pdf_path))

    pages = []
    if name == "pdfplumber":
        with mod.open(pdf_path) as pdf:
            for p in pdf.pages:
                pages.append(p.extract_text() or "")
    else:
        reader = mod.PdfReader(pdf_path)
        if getattr(reader, "is_encrypted", False):
            try:
                if reader.decrypt("") == 0:
                    raise RuntimeError("PDF 已加密，无法读取")
            except RuntimeError:
                raise
            except Exception:
                pass
        for p in reader.pages:
            pages.append(p.extract_text() or "")
    return name, pages, len(pages)


class PdfReaderPlugin(PluginBase):
    name = "pdf_reader"
    version = "0.0.1"
    description = "PDF 文本阅读：提取全文 / 按页读取 / 搜索关键词"
    author = "xiaoling"
    category = "tool"
    permissions = ["file:read"]

    def __init__(self, context=None):
        super().__init__(context)
        self._lock = threading.RLock()

    # ---------------- 工具注册 ----------------
    def init(self):
        self._tools = [
            {
                "name": "extract_text",
                "description": "提取 PDF 全文（附总页数）",
                "args_schema": {"pdf_path": "string"},
                "handler": self.extract_text,
            },
            {
                "name": "read_page",
                "description": "按 1-based 页码读取单页文本",
                "args_schema": {"pdf_path": "string", "page_num": "int"},
                "handler": self.read_page,
            },
            {
                "name": "search_in_pdf",
                "description": "在 PDF 全文中搜索关键词，返回命中页码",
                "args_schema": {"pdf_path": "string", "keyword": "string"},
                "handler": self.search_in_pdf,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    # ---------------- 工具实现 ----------------
    def extract_text(self, pdf_path: str = "") -> dict:
        try:
            if not pdf_path or not str(pdf_path).strip():
                return {"ok": False, "error": "缺少参数 pdf_path"}
            with self._lock:
                backend, pages, total = _open_pages(str(pdf_path).strip())
            return {"ok": True, "pdf_path": pdf_path, "backend": backend,
                    "total_pages": total, "text": "\n".join(pages)}
        except Exception as e:
            return {"ok": False, "pdf_path": pdf_path,
                    "error": "extract_text 失败: {}: {}".format(
                        type(e).__name__, e)}

    def read_page(self, pdf_path: str = "", page_num: int = 1) -> dict:
        try:
            if not pdf_path or not str(pdf_path).strip():
                return {"ok": False, "error": "缺少参数 pdf_path"}
            try:
                pno = int(page_num)
            except (TypeError, ValueError):
                return {"ok": False, "error": "page_num 必须是整数"}
            with self._lock:
                backend, pages, total = _open_pages(str(pdf_path).strip())
            if pno < 1 or pno > total:
                return {"ok": False, "pdf_path": pdf_path,
                        "error": "页码越界：共 {} 页，请求第 {} 页".format(
                            total, pno)}
            return {"ok": True, "pdf_path": pdf_path, "backend": backend,
                    "page_num": pno, "total_pages": total,
                    "text": pages[pno - 1]}
        except Exception as e:
            return {"ok": False, "pdf_path": pdf_path,
                    "error": "read_page 失败: {}: {}".format(
                        type(e).__name__, e)}

    def search_in_pdf(self, pdf_path: str = "", keyword: str = "") -> dict:
        try:
            if not pdf_path or not str(pdf_path).strip():
                return {"ok": False, "error": "缺少参数 pdf_path"}
            kw = str(keyword or "").strip().lower()
            if not kw:
                return {"ok": False, "error": "缺少参数 keyword"}
            with self._lock:
                backend, pages, total = _open_pages(str(pdf_path).strip())
            hits = []
            for idx, text in enumerate(pages, start=1):
                if kw in (text or "").lower():
                    hits.append(idx)
            return {"ok": True, "pdf_path": pdf_path, "backend": backend,
                    "keyword": keyword, "total_pages": total,
                    "hit_pages": hits, "hit_count": len(hits)}
        except Exception as e:
            return {"ok": False, "pdf_path": pdf_path,
                    "error": "search_in_pdf 失败: {}: {}".format(
                        type(e).__name__, e)}
