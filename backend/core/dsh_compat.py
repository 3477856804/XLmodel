import json, os, subprocess, logging, shutil
from pathlib import Path

class DSHCompat:
    """DSH 插件兼容层：解析、安装、管理 DSH 插件"""

    def __init__(self, plugins_dir="data/plugins/dsh"):
        self.plugins_dir = plugins_dir
        self.installed = {}  # name -> manifest
        os.makedirs(plugins_dir, exist_ok=True)
        self._load_installed()

    def _load_installed(self):
        """加载已安装的 DSH 插件列表"""
        manifest_file = os.path.join(self.plugins_dir, "installed.json")
        if os.path.exists(manifest_file):
            with open(manifest_file) as f:
                self.installed = json.load(f)

    def _save_installed(self):
        with open(os.path.join(self.plugins_dir, "installed.json"), "w") as f:
            json.dump(self.installed, f, indent=2, ensure_ascii=False)

    def parse_dsh_plugin(self, package_path: str) -> dict:
        """解析 DSH 插件的 package.json，提取元数据和工具定义
        DSH 插件是 npm 包，package.json 中有 dsh 字段定义插件信息
        """
        pkg_file = os.path.join(package_path, "package.json")
        if not os.path.exists(pkg_file):
            return {"ok": False, "error": "package.json not found"}
        with open(pkg_file) as f:
            pkg = json.load(f)
        dsh_config = pkg.get("dsh", {})
        return {
            "ok": True,
            "name": pkg.get("name", ""),
            "version": pkg.get("version", "0.0.0"),
            "description": pkg.get("description", ""),
            "author": pkg.get("author", ""),
            "tools": dsh_config.get("tools", []),
            "skills": dsh_config.get("skills", []),
            "entry": pkg.get("main", "index.js"),
            "dsh_compatible": True,
        }

    def install_dsh_plugin(self, source: str) -> dict:
        """安装 DSH 插件（从 npm 或本地路径）
        source: npm 包名 或 本地路径 或 git URL
        """
        try:
            plugin_name = os.path.basename(source.rstrip("/"))
            target_dir = os.path.join(self.plugins_dir, plugin_name)
            if source.startswith(("http", "git@")):
                # git clone
                result = subprocess.run(["git", "clone", "--depth", "1", source, target_dir],
                                      capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    return {"ok": False, "error": result.stderr}
            elif os.path.isdir(source):
                # 本地复制
                shutil.copytree(source, target_dir, dirs_exist_ok=True)
            else:
                # npm install
                result = subprocess.run(["npm", "install", "--prefix", target_dir, source],
                                      capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    return {"ok": False, "error": result.stderr}
            manifest = self.parse_dsh_plugin(target_dir)
            if manifest["ok"]:
                self.installed[plugin_name] = manifest
                self._save_installed()
            return manifest
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def uninstall_dsh_plugin(self, name: str) -> bool:
        """卸载 DSH 插件"""
        target_dir = os.path.join(self.plugins_dir, name)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        if name in self.installed:
            del self.installed[name]
            self._save_installed()
        return True

    def list_dsh_plugins(self) -> list:
        """列出已安装的 DSH 插件"""
        return list(self.installed.values())

    # 精选推荐列表（人工筛选，非实时数据；标注 source="curated"）
    CURATED_PLUGINS = [
        {"name": "dsh-github", "title": "GitHub 工具", "description": "GitHub 仓库管理、Issue/PR 操作", "stars": 2340, "category": "开发", "source": "curated"},
        {"name": "dsh-filesystem", "title": "文件系统增强", "description": "高级文件操作、批量重命名、目录同步", "stars": 1890, "category": "工具", "source": "curated"},
        {"name": "dsh-browser", "title": "浏览器自动化", "description": "网页浏览、表单填写、数据抓取", "stars": 3100, "category": "效率", "source": "curated"},
        {"name": "dsh-database", "title": "数据库工具", "description": "SQL 查询、数据库管理、数据导出", "stars": 1560, "category": "开发", "source": "curated"},
        {"name": "dsh-slack", "title": "Slack 集成", "description": "发送消息、读取频道、管理工作区", "stars": 980, "category": "社交", "source": "curated"},
        {"name": "dsh-notion", "title": "Notion 集成", "description": "页面管理、数据库查询、内容创建", "stars": 1200, "category": "效率", "source": "curated"},
        {"name": "dsh-terminal", "title": "终端增强", "description": "命令执行、进程管理、系统监控", "stars": 2100, "category": "开发", "source": "curated"},
        {"name": "dsh-memory", "title": "记忆增强", "description": "长期记忆、向量存储、知识检索", "stars": 1750, "category": "工具", "source": "curated"},
    ]

    REMOTE_MARKET_API = "https://api.github.com/search/repositories?q=dsh+plugin&sort=stars&order=desc&per_page=20"

    def fetch_remote_market(self) -> list:
        """从 GitHub API 实时搜索 dsh 插件市场。
        成功返回条目列表（source="remote"）；任何失败均返回空列表，由调用方降级。
        """
        try:
            import urllib.request
            req = urllib.request.Request(self.REMOTE_MARKET_API, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "XiaoLing-DSHMarket/0.0.1",
            })
            with urllib.request.urlopen(req, timeout=6) as r:
                if getattr(r, "status", 200) != 200:
                    return []
                raw = r.read().decode("utf-8")
            data = json.loads(raw)
            items = data.get("items") or []
            out = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                full_name = str(it.get("full_name") or it.get("name") or "")
                if not full_name:
                    continue
                out.append({
                    "name": full_name,
                    "title": str(it.get("name") or full_name),
                    "description": str(it.get("description") or ""),
                    "stars": int(it.get("stargazers_count") or 0),
                    "category": "remote",
                    "source": "remote",
                    "html_url": str(it.get("html_url") or ""),
                })
            return out
        except Exception:
            return []

    def get_available_plugins(self) -> list:
        """获取可安装的 DSH 插件列表。
        优先尝试 GitHub API 实时数据；失败或为空时降级到精选推荐列表。
        每条目带 source 字段："remote"（实时获取）或 "curated"（精选推荐）。
        """
        try:
            remote = self.fetch_remote_market()
            if remote:
                return remote
        except Exception:
            pass
        return [dict(item) for item in self.CURATED_PLUGINS]
