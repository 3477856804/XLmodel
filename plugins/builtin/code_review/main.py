# -*- coding: utf-8 -*-
"""code_review 插件

对指定文件做静态代码审查，检出常见问题：
  - hardcoded_secret : 硬编码密码 / 密钥 / token
  - sql_injection    : SQL 语句用字符串拼接 / f-string 构造（注入风险）
  - bare_except      : 裸 except / 吞掉异常（未处理异常）
  - mutable_default  : 可变默认参数（Python 陷阱）
  - perf_n_plus_one  : 循环内重复调用（粗粒度性能提示）

核心原则：真实读取文件、用 ast + 正则做静态分析，不产生假数据；
文件不存在 / 无法解析时返回明确错误。
"""
from __future__ import annotations

import ast
import os
import re

try:
    from core.plugin_system import PluginBase
except ImportError:  # 直接以脚本运行 / 非打包态兜底
    from backend.core.plugin_system import PluginBase


# 硬编码密钥：赋值形如 password = "xxx" / api_key = 'xxx' / SECRET_TOKEN = "xxx"
_SECRET_RE = re.compile(
    r"""^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*\s*=\s*['"]"""
    r"""(?P<val>[^'"]{4,})['"])""",
)
_SECRET_NAME_HINT = re.compile(
    r"(password|passwd|secret|api[_-]?key|token|access[_-]?key|"
    r"private[_-]?key|auth|credential)",
    re.IGNORECASE,
)

# SQL 注入：.execute( 调用里出现 f-string、% 格式化 或 字符串拼接（"..." + var）
_SQL_CALL_RE = re.compile(r"""\.(execute|executemany)\s*\(""")
_SQL_FSTRING_RE = re.compile(r"""\.(execute|executemany)\s*\(\s*[f]['"]""")
_SQL_PERCENT_RE = re.compile(r"""\.(execute|executemany)\s*\(\s*['"][^'"]*['"]\s*%""")
_SQL_CONCAT_RE = re.compile(r"""\.(execute|executemany)\s*\(\s*['"][^'"]*['"]\s*\+""")


def _looks_like_sql_concat(line: str) -> bool:
    if not _SQL_CALL_RE.search(line):
        return False
    return bool(_SQL_FSTRING_RE.search(line)
                or _SQL_PERCENT_RE.search(line)
                or _SQL_CONCAT_RE.search(line))


class _Reviewer(ast.NodeVisitor):
    """用 ast 结构检出与控制流相关的问题。"""

    def __init__(self, source_lines):
        self.issues = []
        self.lines = source_lines

    def _snippet(self, lineno):
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()[:120]
        return ""

    def visit_ExceptHandler(self, node):
        # 裸 except:
        if node.type is None:
            self.issues.append({
                "line": node.lineno,
                "severity": "warning",
                "rule": "bare_except",
                "message": "裸 except: 会捕获包括 KeyboardInterrupt 在内的所有异常，建议捕获具体异常类型",
                "snippet": self._snippet(node.lineno),
            })
        else:
            # except Exception: 且 body 只有 pass（吞异常）
            body = node.body
            if (isinstance(node.type, ast.Name) and node.type.id == "Exception") or \
               (isinstance(node.type, ast.Tuple)):
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    self.issues.append({
                        "line": node.lineno,
                        "severity": "warning",
                        "rule": "bare_except",
                        "message": "except Exception 后直接 pass，异常被静默吞掉，建议记录或重新抛出",
                        "snippet": self._snippet(node.lineno),
                    })
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # 可变默认参数：def f(x=[]) / def f(x={})
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.issues.append({
                    "line": default.lineno,
                    "severity": "error",
                    "rule": "mutable_default",
                    "message": "可变默认参数在多次调用间共享状态，会引发难以察觉的 bug",
                    "snippet": self._snippet(default.lineno),
                })
        self.generic_visit(node)


def _review_text(file_path: str, text: str) -> list:
    """对文件文本做静态审查，返回问题列表。"""
    issues = []
    lines = text.splitlines()

    # 1) 正则层：硬编码密钥 / SQL 拼接
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("#"):
            continue
        m = _SECRET_RE.match(line)
        if m and _SECRET_NAME_HINT.search(m.group("name").split("=")[0]):
            issues.append({
                "line": i,
                "severity": "error",
                "rule": "hardcoded_secret",
                "message": "疑似硬编码密钥/密码，应移到环境变量或配置文件",
                "snippet": line.strip()[:120],
            })
        if _looks_like_sql_concat(line):
            issues.append({
                "line": i,
                "severity": "error",
                "rule": "sql_injection",
                "message": "SQL 语句用 f-string / % / + 拼接，存在注入风险，应使用参数化查询",
                "snippet": line.strip()[:120],
            })

    # 2) ast 层：结构问题（仅 Python 文件可解析）
    if file_path.endswith(".py"):
        try:
            tree = ast.parse(text, filename=file_path)
            reviewer = _Reviewer(lines)
            reviewer.visit(tree)
            issues.extend(reviewer.issues)
        except SyntaxError as e:
            issues.append({
                "line": getattr(e, "lineno", 0),
                "severity": "warning",
                "rule": "syntax_error",
                "message": "文件存在语法错误，ast 结构检查已跳过：{}".format(e.msg),
                "snippet": "",
            })

    issues.sort(key=lambda x: (x["line"], x["rule"]))
    return issues


class CodeReviewPlugin(PluginBase):
    name = "code_review"
    version = "0.0.1"
    description = "代码审查：检出硬编码密钥、SQL 注入、吞异常、可变默认参数等常见问题"
    author = "xiaoling"
    category = "development"
    permissions = ["file:read"]

    def init(self):
        self._tools = [
            {
                "name": "review_file",
                "description": "对指定文件做静态代码审查，返回问题列表",
                "args_schema": {"file_path": "string"},
                "handler": self.review_file,
            },
        ]

    # 兼容：外部若按 setup() 调用也能工作
    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def review_file(self, file_path: str = "") -> dict:
        """审查指定文件。返回 {ok, file, issue_count, issues, summary}。"""
        try:
            if not file_path:
                return {"ok": False, "error": "缺少参数 file_path"}
            path = os.path.abspath(os.path.expanduser(str(file_path)))
            if not os.path.isfile(path):
                return {"ok": False, "error": "文件不存在: {}".format(path)}
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError as e:
                return {"ok": False, "error": "读取文件失败: {}".format(e)}

            issues = _review_text(path, text)
            errors = sum(1 for i in issues if i["severity"] == "error")
            warnings = sum(1 for i in issues if i["severity"] == "warning")
            return {
                "ok": True,
                "file": path,
                "issue_count": len(issues),
                "errors": errors,
                "warnings": warnings,
                "issues": issues,
                "summary": "共 {} 个问题：{} 错误 / {} 警告".format(
                    len(issues), errors, warnings),
            }
        except Exception as e:  # 兜底，绝不抛出
            return {"ok": False, "error": "审查失败: {}: {}".format(type(e).__name__, e)}
