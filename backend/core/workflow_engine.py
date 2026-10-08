import json, os, time, logging, threading
import ast, operator, re
from typing import List, Dict, Any, Callable

class WorkflowNode:
    """工作流节点"""
    def __init__(self, node_id, node_type, config=None):
        self.id = node_id
        self.type = node_type  # trigger/action/condition/llm/tool
        self.config = config or {}
        self.next_nodes = []

    def to_dict(self):
        return {"id": self.id, "type": self.type, "config": self.config, "next": self.next_nodes}


class Workflow:
    """工作流定义"""
    def __init__(self, name, description=""):
        self.name = name
        self.description = description
        self.nodes = {}  # id -> WorkflowNode
        self.trigger_node = None
        self.created_at = time.time()

    def add_node(self, node: WorkflowNode):
        self.nodes[node.id] = node
        if node.type == "trigger":
            self.trigger_node = node

    def connect(self, from_id, to_id):
        if from_id in self.nodes:
            self.nodes[from_id].next_nodes.append(to_id)

    def to_dict(self):
        return {
            "name": self.name, "description": self.description,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "trigger": self.trigger_node.id if self.trigger_node else None,
            "created_at": self.created_at,
        }


class WorkflowEngine:
    """工作流引擎：管理和执行工作流"""
    def __init__(self, storage_path="data/workflows.json", engine=None):
        self.storage_path = storage_path
        self.engine = engine  # 可选的引擎引用，用于 LLM 节点真实调用
        self.workflows = {}  # name -> Workflow
        self._actions = {}  # action_name -> handler
        self._load()
        self._register_builtin_actions()

    def set_engine(self, engine):
        """运行时注入引擎引用（供 LLM 节点调用）。"""
        self.engine = engine

    def _register_builtin_actions(self):
        self._actions["log"] = lambda ctx, cfg: f"LOG: {cfg.get('message', '')}"
        self._actions["delay"] = lambda ctx, cfg: (time.sleep(cfg.get("seconds", 1)), "delayed")[1]
        self._actions["set_var"] = lambda ctx, cfg: (ctx.update({cfg["key"]: cfg["value"]}), f"set {cfg['key']}")[1]

    def register_action(self, name, handler):
        self._actions[name] = handler

    def create_workflow(self, name, description="") -> Workflow:
        wf = Workflow(name, description)
        self.workflows[name] = wf
        self._save()
        return wf

    def delete_workflow(self, name):
        if name in self.workflows:
            del self.workflows[name]
            self._save()

    def list_workflows(self) -> list:
        return [{"name": w.name, "description": w.description, "nodes": len(w.nodes), "created_at": w.created_at}
                for w in self.workflows.values()]

    def execute(self, workflow_name, context=None) -> dict:
        """执行工作流，从 trigger 节点开始遍历"""
        if workflow_name not in self.workflows:
            return {"ok": False, "error": f"Workflow {workflow_name} not found"}
        wf = self.workflows[workflow_name]
        ctx = context or {}
        results = []
        visited = set()

        def execute_node(node_id):
            if node_id in visited or node_id not in wf.nodes:
                return
            visited.add(node_id)
            node = wf.nodes[node_id]
            try:
                res = self._execute_node(node, ctx)
                results.append({"node": node_id, **res})
            except Exception as e:
                results.append({"node": node_id,
                                "success": False, "output": "", "error": str(e)})
            for next_id in node.next_nodes:
                execute_node(next_id)

        if wf.trigger_node:
            execute_node(wf.trigger_node.id)
        return {"ok": True, "results": results, "context": ctx}

    def _execute_node(self, node, ctx: dict) -> dict:
        """执行单个节点，统一返回 {"success": bool, "output": str, "error": str}。"""
        try:
            if node.type == "action":
                action_name = node.config.get("action", "")
                handler = self._actions.get(action_name)
                if handler is None:
                    return {"success": False, "output": "",
                            "error": f"未知动作: {action_name}"}
                output = handler(ctx, node.config)
                return {"success": True, "output": str(output), "error": ""}

            if node.type == "llm":
                if self.engine is None or not hasattr(self.engine, "chat"):
                    return {"success": False, "output": "",
                            "error": "LLM节点执行失败：未配置引擎"}
                prompt = node.config.get("prompt", "")
                try:
                    result = self.engine.chat(prompt)
                except Exception as e:
                    return {"success": False, "output": "",
                            "error": f"LLM节点调用异常: {e}"}
                return {"success": True, "output": str(result), "error": ""}

            if node.type == "condition":
                expr = node.config.get("expression", "")
                try:
                    ok = safe_eval_condition(expr, ctx)
                except Exception as e:
                    logging.error("条件表达式解析失败: %s (%s)", expr, e)
                    return {"success": False, "output": "",
                            "error": f"条件表达式无法解析: {expr}"}
                return {"success": True, "output": str(ok), "error": ""}

            if node.type == "trigger":
                return {"success": True, "output": "trigger fired", "error": ""}

            return {"success": False, "output": "",
                    "error": f"未知节点类型: {node.type}"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.workflows.items()}, f, indent=2, ensure_ascii=False)

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                for name, wf_data in data.items():
                    wf = Workflow(name, wf_data.get("description", ""))
                    for nid, ndata in wf_data.get("nodes", {}).items():
                        node = WorkflowNode(nid, ndata["type"], ndata.get("config", {}))
                        node.next_nodes = ndata.get("next", [])
                        wf.add_node(node)
                    self.workflows[name] = wf
            except: pass


# ===== 安全的条件表达式求值（禁止 eval() 任意代码执行）=====
_ALLOWED_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_ALLOWED_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
_ALLOWED_UNARY_OPS = {
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval_node(node, ctx: dict):
    """递归求值 AST 节点，仅允许字面量、变量、比较、算术、and/or/not。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)
    if isinstance(node, ast.Constant):  # 数字 / 字符串 / 布尔
        return node.value
    if isinstance(node, ast.Name):  # 变量：从 ctx 取值
        return ctx.get(node.id, 0)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
        return _ALLOWED_BIN_OPS[type(node.op)](
            _eval_node(node.left, ctx), _eval_node(node.right, ctx))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_eval_node(node.operand, ctx))
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            if not _ALLOWED_CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for v in node.values:
                result = _eval_node(v, ctx)
                if not result:
                    return False
            return bool(result)
        if isinstance(node.op, ast.Or):
            for v in node.values:
                result = _eval_node(v, ctx)
                if result:
                    return True
            return False
    if isinstance(node, ast.List):
        return [_eval_node(e, ctx) for e in node.elts]
    if isinstance(node, ast.Str):  # 兼容旧 AST
        return node.s
    raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def safe_eval_condition(expression: str, ctx: dict) -> bool:
    """安全求值条件表达式，如 `x > 5`、`status == "done"`、`a and b`。

    使用 ast 解析并白名单求值，绝不调用 eval() 执行任意代码。
    表达式无法解析或包含不允许的操作时抛出异常。
    """
    if not expression or not str(expression).strip():
        return False
    try:
        tree = ast.parse(str(expression).strip(), mode="eval")
        result = _eval_node(tree, ctx or {})
        return bool(result)
    except SyntaxError:
        raise
    except Exception as e:
        raise ValueError(f"条件表达式求值失败: {e}")
