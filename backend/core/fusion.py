# -*- coding: utf-8 -*-
"""指令解析（fusion）—— 把自然语言/结构化指令路由到具体能力。

本模块原先缺失，导致 ExecuteCommand 只能返回"指令解析模块已下线"。
此处按项目原有契约重建：`try_command(engine, cmd) -> str | None`。

设计要点：
    1. 返回 None 表示"不认识这条指令"，由调用方自行兜底（保持原有语义）
    2. 其余情况返回字符串；结构化数据用 JSON 编码，便于 Flutter 端解析
    3. 所有涉及"删除"的动作一律走 quarantine（移入 D:\\待处理），绝不真删

支持的指令：
    help / 帮助
    status / 状态
    model:scan <目录>              扫描目录内可用的本地模型
    model:addlocal <目录> [备注]    登记一个本地模型（不复制、不移动）
    model:listlocal                列出已登记的本地模型
    model:addapi <JSON>            登记 OpenAI 兼容接口
    model:listapi                  列出已登记接口
    model:delapi <名称>            摘除接口登记（不动远端）
    model:probeapi <名称>          探测接口是否可达
    model:listall                  汇总所有可用模型来源
"""
from __future__ import annotations

import json


def _ok(**kw) -> str:
    d = {"ok": True}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def _err(msg) -> str:
    return json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)


def _store():
    from core.model import ModelStore
    return ModelStore()


def _local_reg():
    from core.model import LocalModelRegistry
    return LocalModelRegistry()


def _api_reg():
    from core.model import ApiEndpointRegistry
    return ApiEndpointRegistry()


# ---------------------------------------------------------------- 指令入口
def try_command(engine, cmd: str):
    """解析并执行一条指令。返回 str（结构化用 JSON）或 None（不认识）。"""
    if not cmd or not isinstance(cmd, str):
        return None
    raw = cmd.strip()
    if not raw:
        return None
    low = raw.lower()

    # ---- 基础指令 ----
    if low in ("help", "帮助", "?", "h"):
        return _ok(message=_help_text(), commands=[
            "help", "status", "model:scan <目录>", "model:addlocal <目录>",
            "model:listlocal", "model:addapi <JSON>", "model:listapi",
            "model:delapi <名称>", "model:probeapi <名称>", "model:listall",
            "model:use <名称>", "model:current",
        ])

    if low in ("status", "状态"):
        return _ok(message=_status_text(engine))

    # ---- 模型相关 ----
    if low.startswith("model:"):
        return _model_command(raw[len("model:"):].strip(), engine)

    if low.startswith("模型:"):
        return _model_command(raw[len("模型:"):].strip(), engine)

    return None


def _help_text() -> str:
    return ("可用指令：\n"
            "  help                  显示本帮助\n"
            "  status                查看运行状态\n"
            "  model:scan <目录>      扫描目录里已有的本地模型\n"
            "  model:addlocal <目录>  把已有模型目录登记给小凌（不复制不移动）\n"
            "  model:listlocal        列出已登记的本地模型\n"
            "  model:addapi <JSON>    登记本地/远端 OpenAI 兼容接口\n"
            "  model:listapi          列出已登记接口\n"
            "  model:probeapi <名称>   探测接口是否可用\n"
            "  model:delapi <名称>     摘除接口登记\n"
            "  model:use <名称>        切换小凌当前使用的模型（含本地/GGUF）\n"
            "  model:current          查看当前正在用哪个模型")


def _status_text(engine) -> str:
    parts = []
    try:
        if engine is not None and hasattr(engine, "show_status"):
            return str(engine.show_status())
    except Exception:
        pass
    try:
        st = _store()
        info = st.list_all()
        parts.append(f"已下载 {len(info.get('installed', []))} 个")
        parts.append(f"本地登记 {len(info.get('local', []))} 个")
        parts.append(f"API 接口 {len(info.get('api', []))} 个")
    except Exception as e:  # noqa: BLE001
        parts.append(f"模型中心读取失败：{e}")
    return " · ".join(parts) or "引擎未就绪"


# ---------------------------------------------------------------- 模型指令
def _model_command(rest: str, engine=None) -> str:
    if not rest:
        return _err("缺少模型子指令，试试 model:listall")

    op, _, arg = rest.partition(" ")
    op = op.strip().lower()
    arg = arg.strip()

    if op in ("scan", "扫描"):
        return _op_scan(arg)

    if op in ("use", "select", "switch", "切换", "使用", "选用"):
        return _op_use(engine, arg)

    if op in ("current", "now", "当前", "当前模型"):
        return _op_current(engine)

    if op in ("remove", "unregister", "摘除", "移除", "删除登记"):
        if not arg:
            return _err("请给出要摘除的名称，例如：model:remove granite-3")
        r = _store().unregister(arg)
        return (_ok(message=f"已摘除登记：{arg}（磁盘文件未动）")
                if r.get("ok") else _err(r.get("error")))

    if op in ("addlocal", "add", "登记"):
        return _op_add_local(arg)

    if op in ("listlocal", "local", "本地"):
        items = _local_reg().list()
        return _ok(models=items, count=len(items))

    if op in ("addapi", "api", "接口"):
        return _op_add_api(arg)

    if op in ("listapi", "apis"):
        items = _api_reg().list()
        return _ok(endpoints=items, count=len(items))

    if op in ("delapi", "rmapi", "删除接口"):
        if not arg:
            return _err("接口名不能为空")
        r = _api_reg().remove(arg)
        return _ok(message=f"已摘除接口 {arg}") if r.get("ok") else _err(
            r.get("error"))

    if op in ("probeapi", "testapi", "探测"):
        if not arg:
            return _err("接口名不能为空")
        return json.dumps(_api_reg().probe(arg), ensure_ascii=False)

    if op in ("listall", "all", "汇总"):
        try:
            return _ok(**_store().list_all())
        except Exception as e:  # noqa: BLE001
            return _err(f"{type(e).__name__}: {e}")

    return _err(f"未知模型指令：{op}（可用：scan / addlocal / listlocal / "
                f"addapi / listapi / delapi / probeapi / listall / remove）")


def _op_scan(arg: str) -> str:
    from core.model import scan_directory_for_models
    if not arg:
        return _err("请给出要扫描的目录，例如：model:scan D:\\models")
    try:
        res = scan_directory_for_models(arg)
    except Exception as e:  # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    if not res.get("ok"):
        return _err(res.get("error", "扫描失败"))
    return _ok(candidates=res.get("candidates", []),
               count=res.get("count", 0), root=res.get("root", ""))


def _op_add_local(arg: str) -> str:
    """登记本地模型。支持两种写法：
        model:addlocal <目录>
        model:addlocal <名称>|<目录>
    """
    if not arg:
        return _err("请给出模型路径，例如：model:addlocal D:\\models\\Qwen2.5-0.5B "
                    "或 model:addlocal D:\\models\\Qwen3.5-9B.gguf")
    name, directory = "", arg
    if "|" in arg:
        name, _, directory = arg.partition("|")
        name, directory = name.strip(), directory.strip()
    d = directory
    if not name:
        # 用目录名 / 文件名（仅文件去掉扩展名）作为登记名。
        # 注意不能用 `_p.suffix` 判断：目录名里带小数点很常见
        # （granite-3.2-8b-instruct-GGUF），suffix 会误判成 ".2-8b-instruct-GGUF"，
        # 结果名字被截成 "granite-3"。
        from pathlib import Path
        _p = Path(d)
        name = (_p.stem if _p.is_file() else _p.name) or "local_model"
    try:
        r = _local_reg().add(name, d)
    except Exception as e:  # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    if not r.get("ok"):
        return _err(r.get("error"))
    return _ok(message=f"已登记本地模型「{name}」", model=r.get("model"))


def _op_use(engine, arg: str) -> str:
    """切换小凌当前使用的模型。

    这是"本地/GGUF 模型真正能用起来"的最后一环：光能被识别还不够，
    必须有一个把某模型设为当前对话模型的入口。
    """
    if not arg:
        return _err("请给出模型名，例如：model:use "
                    "Qwen3.5-9B-DeepSeek-V4-Flash-Q4_K_M")
    mr = getattr(engine, "model_replace", None) if engine is not None else None
    if mr is None:
        return _err("引擎未就绪，无法切换模型")
    try:
        r = mr.select(arg)
    except Exception as e:  # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    if not r.get("ok"):
        return _err(r.get("error"))
    loaded, err = False, ""
    try:
        loaded = bool(mr.ensure_loaded())
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    return _ok(message=(f"已切换到「{arg}」" +
                        ("，模型已就绪" if loaded else
                         f"，但加载失败：{err or '未知原因'}")),
               name=arg, path=r.get("path", ""), loaded=loaded, error=err)


def _op_current(engine) -> str:
    mr = getattr(engine, "model_replace", None) if engine is not None else None
    name = ""
    loaded = False
    if mr is not None:
        try:
            name = mr.current_name() or ""
        except Exception:
            name = ""
        try:
            m = mr.get_model()
            loaded = bool(m is not None and m.is_loaded())
        except Exception:
            loaded = False
    return _ok(name=name, loaded=loaded,
               message=(f"当前模型：{name or '（未选择）'}"
                        f"{'（已加载）' if loaded else '（未加载）'}"))


def _op_add_api(arg: str) -> str:
    """登记 OpenAI 兼容接口。参数可为 JSON，也可用简写：
        model:addapi {"name":"本地LM","base_url":"http://127.0.0.1:1234","model":"qwen"}
        model:addapi 本地LM http://127.0.0.1:1234 qwen2.5-7b
    """
    if not arg:
        return _err('请给出接口信息，例如：model:addapi {"name":"本地LM",'
                    '"base_url":"http://127.0.0.1:1234"}')
    if arg.startswith("{"):
        try:
            spec = json.loads(arg)
        except Exception as e:  # noqa: BLE001
            return _err(f"JSON 解析失败：{e}")
        if not isinstance(spec, dict):
            return _err("JSON 必须是对象")
        try:
            r = _api_reg().add(
                name=spec.get("name", ""),
                base_url=spec.get("base_url", ""),
                model=spec.get("model", ""),
                api_key=spec.get("api_key", ""),
                kind=spec.get("kind", "openai"),
                note=spec.get("note", ""),
            )
        except Exception as e:  # noqa: BLE001
            return _err(f"{type(e).__name__}: {e}")
        return _ok(message="接口已登记", **r) if r.get("ok") else _err(
            r.get("error"))

    # 简写：名称 地址 模型名
    parts = arg.split()
    if len(parts) < 2:
        return _err("简写格式：名称 地址 [模型名]，或用 JSON")
    name, base = parts[0], parts[1]
    model = parts[2] if len(parts) > 2 else ""
    try:
        r = _api_reg().add(name=name, base_url=base, model=model)
    except Exception as e:  # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    return _ok(message=f"接口「{name}」已登记", **r) if r.get("ok") else _err(
        r.get("error"))
