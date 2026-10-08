"""小凌 · 工具系统（工具 + 技能 + 目标）"""
import json
import math
import os
import re
import threading
import time
import uuid
from pathlib import Path

from .config import DATA_DIR

SAFE_MATH = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
SAFE_MATH.update({"abs": abs, "min": min, "max": max, "round": round,
                  "pow": pow, "int": int, "float": float, "sum": sum, "len": len})

DANGEROUS_TOKENS = re.compile(
    r"__|import|exec|eval|open|file|globals|locals|lambda|compile|"
    r"getattr|setattr|delattr|input|breakpoint|memoryview"
)

GOALS_PATH = DATA_DIR / "goals.json"


class ToolManager:
    CORE_TOOLS = ("get_time", "calculator", "read_file", "write_file",
                  "list_dir", "remember", "recall")
    WRITE_TOOLS = ("write_file", "run_cmd", "pip_install")
    CACHEABLE_TOOLS = ("get_time", "calculator", "list_dir", "read_file")

    def __init__(self, base_dir: str | None = None, memory=None,
                 cache_ttl: float = 60.0, max_read: int = 8000,
                 max_list: int = 200):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.memory = memory
        self.cache_ttl = cache_ttl
        self.max_read = max_read
        self.max_list = max_list
        self.tools: dict[str, dict] = {}
        self.before_hooks: list = []
        self.after_hooks: list = []
        self._cache: dict[str, tuple] = {}
        self._lock = threading.RLock()
        self._register_default()

    def register(self, name: str, func, desc: str, dangerous: bool = False):
        with self._lock:
            self.tools[name] = {"func": func, "desc": desc, "dangerous": dangerous}

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self.tools.pop(name, None) is not None

    def add_before_hook(self, fn):
        self.before_hooks.append(fn)

    def add_after_hook(self, fn):
        self.after_hooks.append(fn)

    def execute(self, name: str, args: dict | None = None):
        args = dict(args) if isinstance(args, dict) else {}
        if name not in self.tools:
            return f"未知工具：{name}"
        for h in self.before_hooks:
            try:
                h(name, args)
            except Exception:
                pass
        cache_key = None
        if name in self.CACHEABLE_TOOLS:
            try:
                cache_key = f"{name}|{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
            except Exception:
                cache_key = None
            if cache_key:
                with self._lock:
                    hit = self._cache.get(cache_key)
                if hit and time.time() - hit[1] < self.cache_ttl:
                    return hit[0]
        try:
            result = str(self.tools[name]["func"](**args))
        except TypeError as e:
            result = f"参数错误：{e}"
        except Exception as e:
            result = f"工具出错：{type(e).__name__}: {e}"
        if cache_key:
            with self._lock:
                self._cache[cache_key] = (result, time.time())
        for h in self.after_hooks:
            try:
                h(name, args, result)
            except Exception:
                pass
        return result

    def exists(self, name: str) -> bool:
        return name in self.tools

    def is_dangerous(self, name: str) -> bool:
        with self._lock:
            return bool(self.tools.get(name, {}).get("dangerous"))

    def list_tools(self) -> list:
        with self._lock:
            return [{"name": k, "desc": v["desc"], "dangerous": v.get("dangerous", False)}
                    for k, v in self.tools.items()]

    def tool_list_text(self) -> str:
        with self._lock:
            return "可用工具：" + ", ".join(sorted(self.tools.keys()))

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def _register_default(self):
        self.register("get_time", self._get_time, "获取当前时间")
        self.register("calculator", self._calculator, "计算器")
        self.register("read_file", self._read_file, "读取文件")
        self.register("write_file", self._write_file, "写入文件", dangerous=True)
        self.register("list_dir", self._list_dir, "列出目录")
        if self.memory is not None:
            self.register("remember", self._remember, "记住内容")
            self.register("recall", self._recall, "回忆内容")

    @staticmethod
    def _get_time(**_):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _calculator(expr: str = "", **_):
        if not expr or len(expr) > 200:
            return "表达式无效"
        if DANGEROUS_TOKENS.search(expr):
            return "表达式包含非法字符"
        try:
            return str(eval(expr, {"__builtins__": {}}, SAFE_MATH))
        except ZeroDivisionError:
            return "除数不能为零"
        except (SyntaxError, TypeError, NameError, ValueError) as e:
            return f"计算失败：{type(e).__name__}"
        except Exception as e:
            return f"计算失败：{e}"

    def _read_file(self, path: str = "", limit: int = 0, **_):
        p = self._safe_path(path)
        if p is None or not p.exists() or not p.is_file():
            return "文件不存在"
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            cap = limit if limit and limit > 0 else self.max_read
            if len(text) > cap:
                return text[:cap] + f"\n…（已截断，共 {len(text)} 字符）"
            return text
        except OSError as e:
            return f"读取失败：{e}"

    def _write_file(self, path: str = "", content: str = "", mode: str = "w", **_):
        p = self._safe_path(path)
        if p is None:
            return "路径不合法"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            m = "a" if mode == "a" else "w"
            with open(p, m, encoding="utf-8") as f:
                f.write(content or "")
            return f"已{'追加' if m == 'a' else '写入'} {len(content or '')} 字符到 {p.name}"
        except OSError as e:
            return f"写入失败：{e}"

    def _list_dir(self, path: str = ".", show_hidden: bool = False, **_):
        p = self._safe_path(path)
        if p is None or not p.exists() or not p.is_dir():
            return "目录不存在"
        try:
            items = []
            for it in sorted(p.iterdir()):
                if not show_hidden and it.name.startswith("."):
                    continue
                items.append(f"{'[D]' if it.is_dir() else '[F]'} {it.name}")
                if len(items) >= self.max_list:
                    break
            return "\n".join(items) if items else "（空目录）"
        except OSError as e:
            return f"列出失败：{e}"

    def _remember(self, key: str = "", value: str = "", **_):
        if not key:
            return "缺少 key"
        if self.memory is None:
            return "记忆模块未加载"
        try:
            self.memory.add("note", f"{key}: {value}",
                            importance=0.9, tags=["note", key])
            return f"已记住 {key}"
        except Exception as e:
            return f"记忆失败：{e}"

    def _recall(self, query: str = "", **_):
        if not query:
            return "缺少查询词"
        if self.memory is None:
            return "记忆模块未加载"
        try:
            items = self.memory.search(query, top_k=5)
            if not items:
                return "没有相关记忆"
            return "\n".join(f"- {i.content}" for i in items)
        except Exception as e:
            return f"回忆失败：{e}"

    def _safe_path(self, path: str):
        if not path:
            return None
        try:
            p = Path(path).expanduser()
            if not p.is_absolute():
                p = self.base_dir / p
            return p.resolve()
        except (OSError, RuntimeError):
            return None

    # ---- 增量：工具执行统计 / 安全计算 / 异常包装 ----
    def _record_call(self, name: str):
        """记录工具调用次数与最后调用时间。"""
        if not hasattr(self, "_tool_calls"):
            self._tool_calls = {}
        with self._lock:
            entry = self._tool_calls.setdefault(name, {"count": 0, "last_call": 0.0})
            entry["count"] += 1
            entry["last_call"] = time.time()

    def get_tool_stats(self) -> dict:
        """返回各工具调用统计。"""
        if not hasattr(self, "_tool_calls"):
            return {"tools": {}, "total_calls": 0}
        with self._lock:
            total = sum(v["count"] for v in self._tool_calls.values())
            return {"tools": dict(self._tool_calls), "total_calls": total}

    def calculate(self, expression: str = "", **_) -> str:
        """安全计算数学表达式，仅允许数字和基本运算符。"""
        if not expression or len(expression) > 200:
            return "表达式无效"
        import ast
        allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
                   ast.Pow, ast.USub, ast.UAdd)
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            for node in ast.walk(tree):
                if not isinstance(node, allowed):
                    return "表达式包含不允许的内容"
            result = eval(compile(tree, "<calc>", "eval"),
                          {"__builtins__": {}}, SAFE_MATH)
            return str(result)
        except Exception as e:
            return f"计算失败：{type(e).__name__}"

    def _safe_execute(self, tool_name: str, **kwargs) -> dict:
        """安全执行工具，捕获异常返回错误字典而非抛出。"""
        self._record_call(tool_name)
        try:
            if tool_name not in self.tools:
                return {"ok": False, "error": f"未知工具：{tool_name}", "result": None}
            result = self.execute(tool_name, kwargs)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "result": None}


class SkillManager:
    def __init__(self, skills_dir: str | None = None, tool_manager: ToolManager | None = None,
                 memory=None, max_content: int = 4000):
        self.skills_dir = Path(skills_dir) if skills_dir else Path("skills")
        self.tool_manager = tool_manager
        self.memory = memory
        self.max_content = max_content
        self.skills: dict[str, dict] = {}
        self._lock = threading.RLock()
        self.load_all()

    def load_all(self) -> int:
        try:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return 0
        n = 0
        for md in sorted(self.skills_dir.glob("*.md")):
            if self.load_skill(md):
                n += 1
        for py in sorted(self.skills_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            if self.load_python_skill(py):
                n += 1
        return n

    def load_skill(self, md_path) -> bool:
        p = Path(md_path)
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            return False
        name = p.stem
        m = re.search(r"^#\s*(.+)$", content, re.MULTILINE)
        desc = m.group(1).strip() if m else name
        triggers = self._extract_triggers(content)
        with self._lock:
            self.skills[name] = {
                "name": name,
                "description": desc,
                "file": str(p),
                "content": content[:self.max_content],
                "triggers": triggers,
                "kind": "markdown",
            }
        return True

    def load_python_skill(self, py_path) -> bool:
        p = Path(py_path)
        name = p.stem
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            return False
        if "def run" not in content and "def invoke" not in content:
            return False
        m = re.search(r'"""(.*?)"""', content, re.DOTALL)
        desc = m.group(1).strip().split("\n")[0] if m else name
        with self._lock:
            self.skills[name] = {
                "name": name,
                "description": desc,
                "file": str(p),
                "content": content[:self.max_content],
                "triggers": [],
                "kind": "python",
            }
        return True

    @staticmethod
    def _extract_triggers(content: str) -> list:
        out = []
        for m in re.finditer(r"^trigger[s]?:\s*(.+)$", content,
                             re.MULTILINE | re.IGNORECASE):
            out.extend([t.strip() for t in re.split(r"[,，]", m.group(1)) if t.strip()])
        return out

    def list_skills(self) -> list:
        with self._lock:
            return [{"name": v["name"], "description": v["description"],
                     "kind": v.get("kind", "markdown"), "triggers": v.get("triggers", [])}
                    for v in self.skills.values()]

    def list_names(self) -> list:
        with self._lock:
            return list(self.skills.keys())

    def get(self, name: str) -> dict:
        with self._lock:
            return dict(self.skills.get(name, {}))

    def match(self, text: str, threshold: int = 1) -> list:
        if not text:
            return []
        hits = []
        with self._lock:
            for s in self.skills.values():
                score = 0
                for t in s.get("triggers", []):
                    if t and t in text:
                        score += 1
                if s["name"] in text:
                    score += 1
                if score >= threshold:
                    hits.append((score, s))
        hits.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in hits]

    def reload(self) -> int:
        with self._lock:
            self.skills.clear()
        return self.load_all()

    def stats(self) -> dict:
        with self._lock:
            kinds: dict[str, int] = {}
            for v in self.skills.values():
                k = v.get("kind", "markdown")
                kinds[k] = kinds.get(k, 0) + 1
            return {"total": len(self.skills), "kinds": kinds,
                    "dir": str(self.skills_dir)}


class GoalManager:
    def __init__(self, memory=None, path: str | None = None,
                 max_goals: int = 200, max_rounds: int = 20):
        self.memory = memory
        self.path = Path(path) if path else GOALS_PATH
        self.max_goals = max_goals
        self.max_rounds = max_rounds
        self.goals: list[dict] = []
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.goals = [g for g in data if isinstance(g, dict)]
            elif isinstance(data, dict):
                self.goals = [g for g in (data.get("goals") or []) if isinstance(g, dict)]
        except Exception:
            self.goals = []

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = list(self.goals)
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError:
            pass

    def create(self, objective: str, max_rounds: int = 0, tags: list | None = None) -> dict:
        goal = {
            "id": f"goal_{uuid.uuid4().hex[:12]}",
            "objective": (objective or "").strip()[:500],
            "phase": "active",
            "rounds_started": 0,
            "max_rounds": max(1, int(max_rounds or self.max_rounds)),
            "created_at": time.time(),
            "updated_at": time.time(),
            "blocked_reason": "",
            "tags": list(tags or []),
            "history": [],
        }
        with self._lock:
            self.goals.append(goal)
            if len(self.goals) > self.max_goals:
                active = [g for g in self.goals if g.get("phase") == "active"]
                done = [g for g in self.goals if g.get("phase") != "active"]
                self.goals = (done[-(self.max_goals // 2):] + active)[-self.max_goals:]
        self._save()
        return goal

    def get(self, goal_id: str) -> dict | None:
        with self._lock:
            return self._find(goal_id)

    def get_active(self) -> dict | None:
        with self._lock:
            return self._find_active()

    def advance(self, goal_id: str = "", note: str = "") -> dict | None:
        with self._lock:
            goal = self._find(goal_id) or self._find_active()
            if not goal:
                return None
            goal["rounds_started"] = int(goal.get("rounds_started", 0)) + 1
            goal["updated_at"] = time.time()
            goal["history"].append({"at": time.time(),
                                    "round": goal["rounds_started"],
                                    "note": note[:200]})
            if len(goal["history"]) > 50:
                goal["history"] = goal["history"][-30:]
            if goal["rounds_started"] >= int(goal.get("max_rounds", self.max_rounds)):
                goal["phase"] = "blocked"
                goal["blocked_reason"] = "达到最大轮次限制"
            result = dict(goal)
        self._save()
        return result

    def complete(self, goal_id: str = "", summary: str = "") -> dict | None:
        with self._lock:
            goal = self._find(goal_id) or self._find_active()
            if not goal:
                return None
            goal["phase"] = "complete"
            goal["completed_at"] = time.time()
            goal["updated_at"] = time.time()
            if summary:
                goal["summary"] = summary[:500]
            result = dict(goal)
        self._save()
        if self.memory:
            try:
                self.memory.add("note", f"目标完成：{result.get('objective', '')[:100]}",
                                importance=0.7, tags=["goal"])
            except Exception:
                pass
        return result

    def block(self, reason: str = "", goal_id: str = "") -> dict | None:
        with self._lock:
            goal = self._find(goal_id) or self._find_active()
            if not goal:
                return None
            goal["phase"] = "blocked"
            goal["blocked_reason"] = (reason or "")[:200]
            goal["updated_at"] = time.time()
            result = dict(goal)
        self._save()
        return result

    def abandon(self, goal_id: str = "") -> dict | None:
        with self._lock:
            goal = self._find(goal_id) or self._find_active()
            if not goal:
                return None
            goal["phase"] = "abandoned"
            goal["updated_at"] = time.time()
            result = dict(goal)
        self._save()
        return result

    def resume(self, goal_id: str = "") -> dict | None:
        with self._lock:
            goal = self._find(goal_id)
            if not goal or goal.get("phase") not in ("blocked", "abandoned"):
                return None
            goal["phase"] = "active"
            goal["blocked_reason"] = ""
            goal["updated_at"] = time.time()
            result = dict(goal)
        self._save()
        return result

    def list_goals(self, limit: int = 20, phase: str = "", tag: str = "") -> list:
        with self._lock:
            goals = list(self.goals)
        if phase:
            goals = [g for g in goals if g.get("phase") == phase]
        if tag:
            goals = [g for g in goals if tag in (g.get("tags") or [])]
        return goals[-limit:]

    def list_text(self, limit: int = 10) -> str:
        goals = self.list_goals(limit=limit)
        if not goals:
            return "无目标"
        return "\n".join(
            f"[{g.get('phase', '?')}] {g.get('objective', '')[:60]}"
            f" (轮次 {g.get('rounds_started', 0)}/{g.get('max_rounds', 0)})"
            for g in goals
        )

    def remove(self, goal_id: str) -> bool:
        with self._lock:
            before = len(self.goals)
            self.goals = [g for g in self.goals if g.get("id") != goal_id]
            changed = len(self.goals) < before
        if changed:
            self._save()
        return changed

    def clear(self, phase: str = ""):
        with self._lock:
            if phase:
                self.goals = [g for g in self.goals if g.get("phase") != phase]
            else:
                self.goals.clear()
        self._save()

    def stats(self) -> dict:
        with self._lock:
            by_phase: dict[str, int] = {}
            for g in self.goals:
                p = g.get("phase", "unknown")
                by_phase[p] = by_phase.get(p, 0) + 1
            return {"total": len(self.goals), "by_phase": by_phase,
                    "path": str(self.path)}

    def _find(self, goal_id: str) -> dict | None:
        if not goal_id:
            return None
        for g in self.goals:
            if g.get("id") == goal_id:
                return g
        return None

    def _find_active(self) -> dict | None:
        for g in self.goals:
            if g.get("phase") == "active":
                return g
        return None


# ============================================================================
# 符号级代码索引（tree-sitter 可选，自动降级正则）
# 核心原则：有符号索引就用，没有就降级关键词搜索，绝不假装能理解代码结构。
# ============================================================================
class SymbolIndexer:
    """符号级代码索引器。

    优先尝试 tree-sitter 解析 AST；不可用时自动降级到正则表达式提取
    def/class/function/import 等关键字。索引缓存到 .symbol_index.json，
    按文件 mtime 增量更新。

    存储结构：
      symbols: {symbol_name: [{file, line, type, signature}, ...]}
      file_symbols: {rel_path: [symbol, ...]}
      file_mtimes: {rel_path: mtime_float}
    """

    CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".dart"}
    SKIP_DIRS = {".git", "build", "__pycache__", ".dart_tool", "node_modules",
                 ".idea", "venv", ".venv", "dist", ".next", "resources"}
    CACHE_NAME = ".symbol_index.json"
    MAX_FILE_BYTES = 1024 * 1024

    # ---- 正则降级模式 ----
    _PY_FUNC_RE = re.compile(
        r"^([ \t]*)(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\([^)]*\))"
    )
    _PY_CLASS_RE = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)")
    _PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+[\w.]+\s+)?import\s+")

    _JS_FUNC_RE = re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\s*(\([^)]*\))"
    )
    _JS_CLASS_RE = re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?class\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)"
    )
    _JS_VAR_RE = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\s*="
    )
    _JS_IMPORT_RE = re.compile(r"^\s*import\s+")

    _DART_CLASS_RE = re.compile(
        r"^\s*(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)"
    )
    _DART_FUNC_RE = re.compile(
        r"^\s*(?:[A-Za-z_<>,\[\]\s?.]+\s+)?"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{"
    )

    def __init__(self, root_dir: str):
        self.root = Path(root_dir).resolve()
        self.index_path = self.root / self.CACHE_NAME
        self.symbols: dict[str, list[dict]] = {}
        self.file_symbols: dict[str, list[dict]] = {}
        self.file_mtimes: dict[str, float] = {}
        self._lock = threading.RLock()
        self._ts_available = self._detect_tree_sitter()

    @staticmethod
    def _detect_tree_sitter() -> bool:
        """探测 tree-sitter 是否可用。永不抛异常。"""
        try:
            import tree_sitter  # noqa: F401
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------
    def build(self, force: bool = False) -> dict:
        """构建或增量更新符号索引。返回统计信息。永不抛异常。"""
        with self._lock:
            try:
                if not force:
                    self._load_cache()

                stats = {"indexed": 0, "skipped": 0, "removed": 0,
                         "tree_sitter": self._ts_available}

                # 收集当前所有代码文件
                current: dict[str, float] = {}
                try:
                    for dirpath, dirnames, filenames in os.walk(str(self.root)):
                        dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
                        for fn in filenames:
                            ext = os.path.splitext(fn)[1].lower()
                            if ext not in self.CODE_EXTS:
                                continue
                            full = os.path.join(dirpath, fn)
                            rel = os.path.relpath(full, str(self.root))
                            try:
                                current[rel] = os.path.getmtime(full)
                            except OSError:
                                continue
                except Exception:
                    pass

                # 清理已删除文件
                stale = set(self.file_mtimes.keys()) - set(current.keys())
                for sf in stale:
                    self._remove_file_symbols(sf)
                    stats["removed"] += 1

                # 增量解析变更文件
                for rel, mtime in current.items():
                    old = self.file_mtimes.get(rel)
                    if old is not None and abs(mtime - old) < 1.0:
                        stats["skipped"] += 1
                        continue
                    self._remove_file_symbols(rel)
                    syms = self._parse_file(rel)
                    self.file_symbols[rel] = syms
                    self.file_mtimes[rel] = mtime
                    for s in syms:
                        self.symbols.setdefault(s["name"], []).append(s)
                    stats["indexed"] += 1

                self._save_cache()
                stats["total_symbols"] = sum(len(v) for v in self.symbols.values())
                stats["total_files"] = len(self.file_mtimes)
                return stats
            except Exception as e:
                return {"error": f"{type(e).__name__}: {e}",
                        "indexed": 0, "skipped": 0, "removed": 0,
                        "total_symbols": 0, "total_files": 0,
                        "tree_sitter": self._ts_available}

    def _remove_file_symbols(self, rel: str):
        """移除某个文件的所有符号记录。"""
        old = self.file_symbols.pop(rel, [])
        for s in old:
            name = s.get("name", "")
            if name in self.symbols:
                self.symbols[name] = [x for x in self.symbols[name]
                                      if x.get("file") != rel]
                if not self.symbols[name]:
                    del self.symbols[name]
        self.file_mtimes.pop(rel, None)

    def _parse_file(self, rel: str) -> list:
        """解析单个文件提取符号。永不抛异常。"""
        syms: list[dict] = []
        try:
            full = self.root / rel
            if full.stat().st_size > self.MAX_FILE_BYTES:
                return syms
            text = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return syms

        ext = os.path.splitext(rel)[1].lower()

        # 优先 tree-sitter
        if self._ts_available:
            try:
                ts = self._parse_with_ts(rel, text, ext)
                if ts:
                    return ts
            except Exception:
                pass  # 降级到正则

        # 正则降级
        try:
            if ext == ".py":
                syms = self._parse_python(text, rel)
            elif ext in (".js", ".jsx", ".ts", ".tsx"):
                syms = self._parse_js(text, rel)
            elif ext == ".dart":
                syms = self._parse_dart(text, rel)
        except Exception:
            syms = []
        return syms

    # ------------------------------------------------------------------
    # tree-sitter 解析（可选）
    # ------------------------------------------------------------------
    def _parse_with_ts(self, rel: str, text: str, ext: str) -> list:
        """用 tree-sitter 解析 AST。语言包缺失时返回空列表触发降级。"""
        lang_map = {
            ".py": ("tree_sitter_python", "python"),
            ".js": ("tree_sitter_javascript", "javascript"),
            ".jsx": ("tree_sitter_javascript", "javascript"),
            ".ts": ("tree_sitter_typescript", "typescript"),
            ".tsx": ("tree_sitter_typescript", "typescript"),
        }
        entry = lang_map.get(ext)
        if not entry:
            return []
        mod_name, _ = entry
        try:
            lang_mod = __import__(mod_name)
        except ImportError:
            return []

        # 兼容不同 tree-sitter 语言包 API
        language = None
        for attr in ("language", "LANGUAGE"):
            try:
                language = getattr(lang_mod, attr)
                if callable(language):
                    language = language()
                break
            except Exception:
                language = None
        if language is None:
            return []

        from tree_sitter import Parser as _TsParser
        parser = _TsParser()
        try:
            parser.set_language(language)
        except Exception:
            return []
        tree = parser.parse(bytes(text, "utf-8"))
        root_node = tree.root_node

        syms: list[dict] = []
        def _walk(node):
            try:
                nt = node.type
                if nt in ("function_definition", "function_declaration",
                          "method_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        line = node.start_point[0] + 1
                        sig = text[node.start_byte:node.end_byte].split("\n")[0][:120]
                        syms.append({
                            "name": name_node.text.decode("utf-8", "ignore"),
                            "file": rel, "line": line,
                            "type": "function", "signature": sig,
                        })
                elif nt == "class_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node is not None:
                        line = node.start_point[0] + 1
                        sig = text[node.start_byte:node.end_byte].split("\n")[0][:120]
                        syms.append({
                            "name": name_node.text.decode("utf-8", "ignore"),
                            "file": rel, "line": line,
                            "type": "class", "signature": sig,
                        })
            except Exception:
                pass
            for child in node.children:
                _walk(child)
        try:
            _walk(root_node)
        except Exception:
            pass
        return syms

    # ------------------------------------------------------------------
    # 正则降级解析
    # ------------------------------------------------------------------
    def _parse_python(self, text: str, rel: str) -> list:
        syms: list[dict] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            m = self._PY_CLASS_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "class", "signature": stripped[:120],
                })
                continue

            m = self._PY_FUNC_RE.match(line)
            if m:
                indent = m.group(1)
                func_name = m.group(2)
                sym_type = "method" if len(indent.expandtabs()) >= 4 else "function"
                syms.append({
                    "name": func_name, "file": rel, "line": lineno,
                    "type": sym_type, "signature": stripped[:120],
                })
                continue

            if self._PY_IMPORT_RE.match(line):
                syms.append({
                    "name": "_import", "file": rel, "line": lineno,
                    "type": "import", "signature": stripped[:120],
                })
        return syms

    def _parse_js(self, text: str, rel: str) -> list:
        syms: list[dict] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue

            m = self._JS_CLASS_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "class", "signature": stripped[:120],
                })
                continue

            m = self._JS_FUNC_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "function", "signature": stripped[:120],
                })
                continue

            m = self._JS_VAR_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "variable", "signature": stripped[:120],
                })
                continue

            if self._JS_IMPORT_RE.match(line):
                syms.append({
                    "name": "_import", "file": rel, "line": lineno,
                    "type": "import", "signature": stripped[:120],
                })
        return syms

    def _parse_dart(self, text: str, rel: str) -> list:
        syms: list[dict] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            m = self._DART_CLASS_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "class", "signature": stripped[:120],
                })
                continue
            m = self._DART_FUNC_RE.match(line)
            if m:
                syms.append({
                    "name": m.group(1), "file": rel, "line": lineno,
                    "type": "function", "signature": stripped[:120],
                })
        return syms

    # ------------------------------------------------------------------
    # 符号查询
    # ------------------------------------------------------------------
    def find_symbol(self, name: str, fuzzy: bool = True) -> list:
        """按名称精确/模糊查找符号定义。"""
        if not name:
            return []
        results: list[dict] = []
        with self._lock:
            exact = self.symbols.get(name, [])
            for s in exact:
                results.append({**s, "match": "exact"})
            if fuzzy and not exact:
                q = name.lower()
                for sym_name, entries in self.symbols.items():
                    if sym_name == "_import":
                        continue
                    if q in sym_name.lower() and sym_name != name:
                        for s in entries:
                            results.append({**s, "match": "fuzzy"})
        return results

    def find_references(self, name: str) -> list:
        """查找符号的所有引用位置（简单版：grep 单词匹配，排除定义行）。"""
        if not name:
            return []
        refs: list[dict] = []
        try:
            defs = self.find_symbol(name, fuzzy=False)
            def_loc = {(d["file"], d["line"]) for d in defs}
            word = re.compile(r"\b" + re.escape(name) + r"\b")
            for rel in list(self.file_symbols.keys()):
                try:
                    text = (self.root / rel).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    if not word.search(line):
                        continue
                    if (rel, lineno) in def_loc:
                        continue
                    refs.append({"file": rel, "line": lineno,
                                 "text": line.strip()[:120]})
                    if len(refs) >= 100:
                        return refs
        except Exception:
            pass
        return refs

    def list_symbols(self, file: str = "", type_filter: str = "") -> list:
        """列出文件中所有符号（可按类型过滤）。"""
        with self._lock:
            if file:
                syms = list(self.file_symbols.get(file, []))
            else:
                syms = []
                for entries in self.file_symbols.values():
                    syms.extend(entries)
        if type_filter:
            syms = [s for s in syms if s.get("type") == type_filter]
        return syms

    def get_call_graph(self, function_name: str) -> dict:
        """简单调用图：谁调用了该函数 / 该函数调用了谁。"""
        result: dict = {"caller": [], "callee": []}
        if not function_name:
            return result
        try:
            result["caller"] = self.find_references(function_name)[:20]
        except Exception:
            pass
        try:
            defs = self.find_symbol(function_name, fuzzy=False)
            if defs:
                d = defs[0]
                text = (self.root / d["file"]).read_text(
                    encoding="utf-8", errors="ignore")
                lines = text.splitlines()
                start = d["line"] - 1
                body = "\n".join(lines[start:start + 50])
                called = set()
                for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", body):
                    called.add(m.group(1))
                skip = {"if", "for", "while", "return", "print", "len", "str",
                        "int", "range", "self", "super", "open", "isinstance",
                        "except", "with", "yield", "await", "async"}
                result["callee"] = sorted(called - skip)[:20]
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # 缓存读写
    # ------------------------------------------------------------------
    def _load_cache(self):
        try:
            if not self.index_path.exists():
                return
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                return
            self.symbols = data.get("symbols", {})
            self.file_mtimes = data.get("file_mtimes", {})
            self.file_symbols = {}
            for entries in self.symbols.values():
                for s in entries:
                    f = s.get("file", "")
                    if f:
                        self.file_symbols.setdefault(f, []).append(s)
        except Exception:
            self.symbols = {}
            self.file_mtimes = {}
            self.file_symbols = {}

    def _save_cache(self):
        try:
            data = {
                "version": 1,
                "root": str(self.root),
                "symbols": self.symbols,
                "file_mtimes": self.file_mtimes,
            }
            self.index_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8")
        except Exception:
            pass


class ToolKit:
    def __init__(self, base_dir: str | None = None, memory=None,
                 skills_dir: str | None = None):
        self.tools = ToolManager(base_dir=base_dir, memory=memory)
        self.skills = SkillManager(skills_dir=skills_dir, tool_manager=self.tools,
                                   memory=memory)
        self.goals = GoalManager(memory=memory)
        self._mcp_manager = None
        self._sym_indexer = None

    @property
    def mcp_manager(self):
        """懒加载 MCPManager 单例。"""
        if self._mcp_manager is None:
            try:
                from .mcp_client import MCPManager
                self._mcp_manager = MCPManager()
            except Exception:
                self._mcp_manager = False
        return self._mcp_manager if self._mcp_manager else None

    def execute(self, name: str, args: dict | None = None) -> str:
        return self.tools.execute(name, args)

    def match_skills(self, text: str) -> list:
        return self.skills.match(text)

    def snapshot(self) -> dict:
        return {
            "tools": self.tools.list_tools(),
            "skills": self.skills.list_skills(),
            "goals": self.goals.stats(),
        }

    def stats(self) -> dict:
        return {
            "tools": len(self.tools.tools),
            "skills": self.skills.stats(),
            "goals": self.goals.stats(),
        }

    def close(self):
        try:
            self.goals._save()
        except Exception:
            pass

    # ================================================================
    # Agent 工具集（供 AgentEngine 调用）
    # ================================================================
    def agent_tools(self) -> list:
        """返回 Agent 可用工具的定义列表（含参数 schema）。"""
        base = [
            {
                "name": "read_file",
                "description": "读取指定文件内容，返回 {path, content, language, lines, size}",
                "args": {
                    "path": {"type": "string", "description": "文件相对或绝对路径",
                             "required": True},
                },
            },
            {
                "name": "write_file",
                "description": "写入（或追加）文件，自动创建父目录",
                "args": {
                    "path": {"type": "string", "description": "文件路径",
                             "required": True},
                    "content": {"type": "string", "description": "要写入的内容",
                                 "required": True},
                    "append": {"type": "boolean", "description": "是否追加模式",
                               "required": False},
                },
            },
            {
                "name": "list_dir",
                "description": "列出目录内容（目录在前、文件在后）",
                "args": {
                    "path": {"type": "string", "description": "目录路径，默认当前目录",
                             "required": False},
                },
            },
            {
                "name": "search_code",
                "description": "在项目代码中搜索。mode=keyword（默认）逐行 grep 关键词；mode=symbol 符号级查询（函数/类定义、引用位置、调用关系）",
                "args": {
                    "query": {"type": "string", "description": "搜索关键词或符号名",
                               "required": True},
                    "mode": {"type": "string", "description": "搜索模式：keyword（默认）| symbol",
                              "required": False},
                    "max_results": {"type": "integer", "description": "最大返回条数",
                                    "required": False},
                },
            },
            {
                "name": "run_command",
                "description": "执行一条 shell 命令（超时 30 秒），返回 stdout+stderr",
                "args": {
                    "cmd": {"type": "string", "description": "要执行的 shell 命令",
                             "required": True},
                },
            },
            {
                "name": "web_search",
                "description": "联网搜索，返回 [{title, url, snippet}]",
                "args": {
                    "query": {"type": "string", "description": "搜索查询词",
                               "required": True},
                },
            },
            {
                "name": "get_project_context",
                "description": "获取当前项目上下文（文件统计、语言分布、README）",
                "args": {},
            },
        ]
        mcp = self.mcp_manager
        if mcp is not None:
            for t in mcp.get_all_tools():
                base.append({
                    "name": t["full_name"],
                    "description": t.get("description", "") or f"MCP 工具 ({t['server']})",
                    "args": self._mcp_schema_to_args(t.get("inputSchema", {})),
                })
        return base

    @staticmethod
    def _mcp_schema_to_args(schema: dict) -> dict:
        """将 MCP inputSchema 转换为内部 args 格式。"""
        props = (schema or {}).get("properties", {})
        required = set((schema or {}).get("required", []))
        out = {}
        for k, v in props.items():
            out[k] = {
                "type": v.get("type", "string"),
                "description": v.get("description", ""),
                "required": k in required,
            }
        return out

    def _file_manager(self):
        """惰性构建 FileManager，避免循环导入与初始化开销。"""
        try:
            from .fileops import FileManager
            return FileManager(str(self.tools.base_dir))
        except Exception as e:  # noqa: BLE001
            print(f"  [Tools] FileManager 初始化失败：{type(e).__name__}: {e}")
            return None

    def _symbol_indexer(self):
        """惰性构建 SymbolIndexer 单例。失败返回 None，由调用方降级。"""
        if self._sym_indexer is None:
            try:
                self._sym_indexer = SymbolIndexer(str(self.tools.base_dir))
            except Exception:
                self._sym_indexer = False  # 标记为不可用，避免反复尝试
        return self._sym_indexer if self._sym_indexer else None

    def execute_tool(self, name: str, args: dict | None = None) -> str:
        """按 name 分发执行 Agent 工具，统一返回字符串结果。异常被捕获。"""
        args = dict(args) if isinstance(args, dict) else {}
        try:
            if name == "read_file":
                fm = self._file_manager()
                if fm is None:
                    return "文件管理器不可用"
                res = fm.read_file(args.get("path", "."))
                if res.get("error"):
                    return f"读取失败：{res['error']}"
                header = f"[{res.get('language','text')}] {res.get('lines',0)} 行, {res.get('size',0)} 字节\n"
                return header + res.get("content", "")

            if name == "write_file":
                fm = self._file_manager()
                if fm is None:
                    return "文件管理器不可用"
                ok = fm.write_file(args.get("path", ""),
                                   args.get("content", ""),
                                   append=bool(args.get("append", False)))
                return f"写入成功：{args.get('path')}" if ok else "写入失败"

            if name == "list_dir":
                fm = self._file_manager()
                if fm is None:
                    return "文件管理器不可用"
                res = fm.list_dir(args.get("path", "."))
                if res.get("error"):
                    return f"列出失败：{res['error']}"
                lines = []
                for it in res.get("items", []):
                    tag = "[D]" if it["is_dir"] else "[F]"
                    lines.append(f"{tag} {it['name']}")
                return "\n".join(lines) if lines else "（空目录）"

            if name == "search_code":
                query = args.get("query", "")
                if not query:
                    return "缺少 query"
                mode = (args.get("mode") or "keyword").lower()

                # ---- 符号级查询模式 ----
                if mode == "symbol":
                    try:
                        idx = self._symbol_indexer()
                        if idx is None:
                            return ("符号索引不可用（tree-sitter 与正则均失败），"
                                    "请用 mode=keyword 关键词搜索")
                        stats = idx.build()
                        if stats.get("error"):
                            return f"符号索引构建失败：{stats['error']}，请用 mode=keyword"

                        # 1) 先找符号定义
                        defs = idx.find_symbol(query)
                        if defs:
                            engine = "tree-sitter" if stats.get("tree_sitter") else "regex"
                            out = [f"符号「{query}」定义（{len(defs)} 处，引擎={engine}）："]
                            for d in defs[:30]:
                                out.append(
                                    f"  [{d.get('type','?')}] {d.get('file','?')}:"
                                    f"{d.get('line','?')} {d.get('signature','')[:80]}"
                                )
                            return "\n".join(out)

                        # 2) 没找到定义，尝试找引用
                        refs = idx.find_references(query)
                        if refs:
                            out = [f"符号「{query}」无定义，但找到 {len(refs)} 处引用："]
                            for r in refs[:20]:
                                out.append(f"  {r['file']}:{r['line']} {r['text'][:80]}")
                            return "\n".join(out)

                        return (f"符号「{query}」未找到定义或引用"
                                f"（已索引 {stats.get('total_files',0)} 文件，"
                                f"{stats.get('total_symbols',0)} 符号）")
                    except Exception as e:  # noqa: BLE001
                        return f"符号搜索异常，降级关键词：{type(e).__name__}: {e}"

                # ---- 默认关键词 grep 模式（向后兼容）----
                from .search import search_code
                matches = search_code(query,
                                      path=str(self.tools.base_dir),
                                      max_results=int(args.get("max_results", 50)))
                if not matches:
                    return f"未找到与「{query}」相关的代码"
                out = [f"共 {len(matches)} 条："]
                for m in matches[:20]:
                    out.append(f"{m['file']}:{m['line']} ({m['kind']}) {m['text'][:80]}")
                return "\n".join(out)

            if name == "run_command":
                import subprocess as _sp
                cmd = args.get("cmd", "")
                if not cmd:
                    return "缺少 cmd"
                proc = _sp.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=30)
                out = (proc.stdout or "") + (proc.stderr or "")
                return out.strip() or f"命令执行完成（退出码 {proc.returncode}，无输出）"

            if name == "web_search":
                from .search import search_web
                query = args.get("query", "")
                if not query:
                    return "缺少 query"
                results = search_web(query, n=5)
                if not results:
                    return f"未找到与「{query}」相关的结果"
                lines = []
                for i, r in enumerate(results, 1):
                    lines.append(f"[{i}] {r.get('title','')}\n    {r.get('url','')}\n    {r.get('snippet','')[:120]}")
                return "\n".join(lines)

            if name == "get_project_context":
                from .context import ProjectContext
                pc = ProjectContext(str(self.tools.base_dir))
                res = pc.collect()
                return (f"项目：{res.get('project_name','')}\n"
                        f"文件数：{res.get('total_files',0)}，"
                        f"总行数：{res.get('total_lines',0)}\n"
                        f"语言：{', '.join(res.get('languages', []))}\n"
                        f"README：{(res.get('readme','') or '（无）')[:500]}")

            if name.startswith("mcp__"):
                mcp = self.mcp_manager
                if mcp is None:
                    return "MCP 模块不可用"
                return mcp.call_tool(name, args)

            return f"未知工具：{name}"
        except Exception as e:  # noqa: BLE001
            return f"工具 {name} 执行异常：{type(e).__name__}: {e}"


def quick_calc(expr: str) -> str:
    return ToolManager._calculator(expr)


def quick_time() -> str:
    return ToolManager._get_time()


def extract_tool_calls(text: str) -> tuple:
    pattern = re.compile(r"\[\[tool:(\w+)([^\]]*)\]\]")
    calls = []
    for m in pattern.finditer(text):
        args = {}
        rest = m.group(2).strip()
        if rest:
            for part in rest.split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    args[k.strip()] = v.strip()
        calls.append({"name": m.group(1), "args": args})
    clean = pattern.sub("", text).strip()
    return clean, calls

"""小凌 · 守卫（离线检测 + 循环检测）"""
import json
import socket
import threading
import time


class OfflineGuard:
    def __init__(self, host: str = "gitee.com", port: int = 443,
                 interval: float = 30.0, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.interval = interval
        self.timeout = timeout
        self.online: bool | None = None
        self.last_check = 0.0
        self._lock = threading.RLock()

    def is_online(self, force: bool = False) -> bool:
        now = time.time()
        with self._lock:
            if not force and self.online is not None and (now - self.last_check) < self.interval:
                return self.online
            self.last_check = now
        ok = False
        try:
            prev = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self.timeout)
            try:
                socket.getaddrinfo(self.host, self.port,
                                   socket.AF_INET, socket.SOCK_STREAM)
                ok = True
            finally:
                socket.setdefaulttimeout(prev)
        except (socket.gaierror, socket.timeout, OSError):
            ok = False
        with self._lock:
            self.online = ok
        return ok

    def status_text(self) -> str:
        return "在线" if self.is_online() else "离线模式——本地模型完整可用"

    def reset(self):
        with self._lock:
            self.online = None
            self.last_check = 0.0

    def snapshot(self) -> dict:
        return {"online": self.online, "last_check": self.last_check,
                "host": self.host}


class Guard:
    SOFT_THRESHOLD = 3
    HARD_THRESHOLD = 5
    MAX_HISTORY = 100
    WINDOW = 20

    def __init__(self):
        self.tool_history: list[dict] = []
        self._consecutive: list[str] = []
        self._lock = threading.RLock()

    @staticmethod
    def _normalize(obj):
        if isinstance(obj, dict):
            return {k: Guard._normalize(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, (list, tuple)):
            return [Guard._normalize(x) for x in obj]
        return obj

    def _signature(self, name: str, args) -> str:
        try:
            return f"{name}|{json.dumps(self._normalize(args), sort_keys=True, ensure_ascii=False)}"
        except Exception:
            return f"{name}|{args}"

    def record_tool(self, name: str, args):
        sig = self._signature(name, args)
        with self._lock:
            self.tool_history.append({"name": name, "args": str(args)[:100],
                                      "time": time.time()})
            if len(self.tool_history) > self.MAX_HISTORY:
                self.tool_history = self.tool_history[-self.MAX_HISTORY:]
            self._consecutive.append(sig)
            if len(self._consecutive) > self.WINDOW:
                self._consecutive = self._consecutive[-self.WINDOW:]

    def check(self, name: str, args) -> tuple:
        sig = self._signature(name, args)
        with self._lock:
            run = 0
            for s in reversed(self._consecutive):
                if s == sig:
                    run += 1
                else:
                    break
        if run >= self.HARD_THRESHOLD:
            return "hard", f"硬停止：{name} 连续调用 {run} 次"
        if run >= self.SOFT_THRESHOLD:
            return "soft", f"软警告：{name} 连续调用 {run} 次"
        return None, None

    def reset(self):
        with self._lock:
            self.tool_history.clear()
            self._consecutive.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"history": len(self.tool_history),
                    "window": len(self._consecutive)}
"""小凌 · 定时系统（CronScheduler）"""
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

JOBS_PATH = DATA_DIR / "cron_jobs.json"

INTERVAL_UNITS = (
    ("秒", 1.0), ("s", 1.0), ("sec", 1.0),
    ("分钟", 60.0), ("min", 60.0), ("m", 60.0),
    ("小时", 3600.0), ("hour", 3600.0), ("h", 3600.0),
    ("天", 86400.0), ("day", 86400.0), ("d", 86400.0),
)

DAILY_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class CronScheduler:
    def __init__(self, app=None, jobs_path: str | None = None, tick: float = 15.0,
                 on_fire=None):
        self.app = app
        self.path = Path(jobs_path) if jobs_path else JOBS_PATH
        self.tick = float(tick)
        self.on_fire = on_fire
        self.jobs: list[dict] = []
        self._lock = threading.RLock()
        self._stop = False
        self._thread: threading.Thread | None = None
        self._load()
        self._start()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                with self._lock:
                    self.jobs = [j for j in data if isinstance(j, dict)]
        except Exception:
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = list(self.jobs)
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError:
            pass

    def _parse(self, spec: str) -> tuple:
        s = (spec or "").strip().lower()
        if s.startswith("every "):
            rest = s[6:].strip()
            for unit, mult in INTERVAL_UNITS:
                if unit in rest:
                    try:
                        n = float(rest.replace(unit, "").strip() or 1)
                        return "interval", max(n * mult, 1.0)
                    except ValueError:
                        break
        if s == "hourly":
            return "interval", 3600.0
        if s == "daily":
            return "daily", "09:00"
        if s.startswith("daily "):
            v = s[6:].strip()
            if DAILY_RE.match(v):
                return "daily", v
        if s.startswith("weekly "):
            return "weekly", s[7:].strip()
        return "interval", 300.0

    def add(self, desc: str, spec: str, action: str = "", payload: dict = None) -> dict:
        kind, value = self._parse(spec)
        job = {
            "id": f"job_{int(time.time() * 1000)}_{len(self.jobs)}",
            "desc": (desc or "")[:200],
            "spec": spec,
            "kind": kind,
            "value": value,
            "action": action,
            "payload": payload or {},
            "last_run": 0.0,
            "runs": 0,
            "created_at": time.time(),
            "enabled": True,
        }
        with self._lock:
            self.jobs.append(job)
        self.save()
        return job

    def remove(self, job_id: str) -> bool:
        with self._lock:
            before = len(self.jobs)
            self.jobs = [j for j in self.jobs if j.get("id") != job_id]
            changed = len(self.jobs) < before
        if changed:
            self.save()
        return changed

    def pause(self, job_id: str) -> bool:
        with self._lock:
            for j in self.jobs:
                if j.get("id") == job_id:
                    j["enabled"] = False
                    self.save()
                    return True
        return False

    def resume(self, job_id: str) -> bool:
        with self._lock:
            for j in self.jobs:
                if j.get("id") == job_id:
                    j["enabled"] = True
                    self.save()
                    return True
        return False

    def list_jobs(self) -> list:
        with self._lock:
            return [dict(j) for j in self.jobs]

    def list_text(self) -> str:
        with self._lock:
            jobs = list(self.jobs)
        if not jobs:
            return "当前无定时任务"
        lines = []
        for i, j in enumerate(jobs, 1):
            state = "▶" if j.get("enabled", True) else "⏸"
            lines.append(f"{state} {i}. {j['desc']}（{j['spec']}，已执行 {j['runs']} 次）")
        return "\n".join(lines)

    def _start(self):
        def _loop():
            while not self._stop:
                time.sleep(self.tick)
                try:
                    self._tick_once()
                except Exception:
                    pass
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def _tick_once(self):
        now = time.time()
        fires = []
        with self._lock:
            for j in self.jobs:
                if not j.get("enabled", True):
                    continue
                kind = j.get("kind")
                value = j.get("value")
                last = float(j.get("last_run", 0))
                due = False
                if kind == "interval":
                    due = (now - last) >= float(value)
                elif kind == "daily":
                    cur = time.strftime("%H:%M")
                    due = (cur == value and now - last > 60)
                if due:
                    j["last_run"] = now
                    j["runs"] = int(j.get("runs", 0)) + 1
                    fires.append(dict(j))
        for job in fires:
            self._fire(job)
        if fires:
            self.save()

    def _fire(self, job: dict):
        if self.on_fire:
            try:
                self.on_fire(job)
            except Exception:
                pass
        if self.app and hasattr(self.app, "chat") and job.get("action"):
            try:
                self.app.chat(job["action"])
            except Exception:
                pass

    def stop(self):
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def clear(self):
        with self._lock:
            self.jobs.clear()
        self.save()

    def stats(self) -> dict:
        with self._lock:
            total = len(self.jobs)
            enabled = sum(1 for j in self.jobs if j.get("enabled", True))
            total_runs = sum(int(j.get("runs", 0)) for j in self.jobs)
            return {"total": total, "enabled": enabled, "runs": total_runs,
                    "path": str(self.path)}
"""小凌 · 多子 Agent 并行系统"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

DECOMPOSE_HINTS = ("所有", "全部", "批量", "多个", "每个", "分别", "列表", "分类", "逐条")
ANGLES = ("从整体梳理", "从细节执行", "从风险排查", "从优化提升", "从成果验证",
          "从时间维度", "从空间维度")


class MultiAgentSystem:
    def __init__(self, app=None, max_agents: int = 100, max_workers: int = 16):
        self.app = app
        self.max_agents = max_agents
        self.max_workers = max_workers
        self.agents: dict[str, dict] = {}
        self._lock = threading.RLock()

    def spawn(self, task: str, count: int = 3, max_workers: int | None = None) -> str:
        count = max(1, min(int(count), self.max_agents))
        workers = max_workers or min(count, self.max_workers)
        subtasks = self._decompose(task, count)
        with self._lock:
            self.agents.clear()
            for i in range(count):
                aid = f"agent_{i + 1}"
                self.agents[aid] = {"status": "排队中",
                                    "task": subtasks[i % len(subtasks)][:60],
                                    "result": "", "started_at": 0.0,
                                    "finished_at": 0.0}
        results = {}

        def _run(aid: str, sub: str):
            with self._lock:
                if aid in self.agents:
                    self.agents[aid]["status"] = "执行中"
                    self.agents[aid]["started_at"] = __import__("time").time()
            try:
                if self.app and hasattr(self.app, "chat"):
                    out = self.app.chat(sub)
                    reply = out[0] if isinstance(out, (tuple, list)) else out
                else:
                    # 未接入引擎：明确标注降级，绝不假装已“完成”子任务
                    reply = f"（未接入对话引擎，降级回执）已接收：{sub[:50]}"
                with self._lock:
                    if aid in self.agents:
                        self.agents[aid]["status"] = "完成"
                        self.agents[aid]["result"] = str(reply)[:500]
                        self.agents[aid]["finished_at"] = __import__("time").time()
                return str(reply)
            except Exception as e:
                with self._lock:
                    if aid in self.agents:
                        self.agents[aid]["status"] = "失败"
                        self.agents[aid]["result"] = str(e)[:300]
                return f"子任务失败：{e}"

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for i in range(count):
                aid = f"agent_{i + 1}"
                sub = subtasks[i % len(subtasks)]
                futures[pool.submit(_run, aid, sub)] = aid
            for fut in as_completed(futures):
                aid = futures[fut]
                try:
                    results[aid] = fut.result()
                except Exception as e:
                    results[aid] = f"异常：{e}"

        lines = []
        for i in range(1, count + 1):
            aid = f"agent_{i}"
            lines.append(f"[{aid}] {str(results.get(aid, '无结果'))[:80]}")
        return "\n".join(lines)

    def _decompose(self, task: str, count: int) -> list:
        if not any(k in task for k in DECOMPOSE_HINTS):
            return [task]
        return [f"{task}（{ANGLES[i % len(ANGLES)]}）" for i in range(min(count, 5))]

    def status(self) -> str:
        with self._lock:
            if not self.agents:
                return "当前无子 agent 在运行"
            done = sum(1 for a in self.agents.values() if a["status"] == "完成")
            running = sum(1 for a in self.agents.values() if a["status"] == "执行中")
            failed = sum(1 for a in self.agents.values() if a["status"] == "失败")
            return (f"共 {len(self.agents)} 个子 agent："
                    f"完成 {done}｜执行中 {running}｜失败 {failed}")

    def report(self) -> list:
        with self._lock:
            return [{"id": k, **v} for k, v in self.agents.items()]

    def clear(self):
        with self._lock:
            self.agents.clear()

    def stats(self) -> dict:
        with self._lock:
            by_status: dict[str, int] = {}
            for a in self.agents.values():
                s = a.get("status", "unknown")
                by_status[s] = by_status.get(s, 0) + 1
            return {"total": len(self.agents), "by_status": by_status,
                    "max_agents": self.max_agents}