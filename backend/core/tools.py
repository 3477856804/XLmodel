"""小凌 · 工具系统（工具 + 技能 + 目标）"""
import json
import math
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


class ToolKit:
    def __init__(self, base_dir: str | None = None, memory=None,
                 skills_dir: str | None = None):
        self.tools = ToolManager(base_dir=base_dir, memory=memory)
        self.skills = SkillManager(skills_dir=skills_dir, tool_manager=self.tools,
                                   memory=memory)
        self.goals = GoalManager(memory=memory)

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
                    reply = f"任务完成：{sub[:50]}"
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