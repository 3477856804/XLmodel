import json, os, time, logging, threading
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
    def __init__(self, storage_path="data/workflows.json"):
        self.storage_path = storage_path
        self.workflows = {}  # name -> Workflow
        self._actions = {}  # action_name -> handler
        self._load()
        self._register_builtin_actions()

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
                if node.type == "action" and node.config.get("action") in self._actions:
                    result = self._actions[node.config["action"]](ctx, node.config)
                    results.append({"node": node_id, "result": str(result)})
                elif node.type == "llm":
                    results.append({"node": node_id, "result": f"LLM call: {node.config.get('prompt', '')[:50]}"})
                elif node.type == "condition":
                    results.append({"node": node_id, "result": f"Condition: {node.config.get('expression', '')}"})
                else:
                    results.append({"node": node_id, "result": f"Executed {node.type}"})
            except Exception as e:
                results.append({"node": node_id, "error": str(e)})
            for next_id in node.next_nodes:
                execute_node(next_id)

        if wf.trigger_node:
            execute_node(wf.trigger_node.id)
        return {"ok": True, "results": results, "context": ctx}

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
