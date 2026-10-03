"""知识图谱 - 实体-关系网络"""
import json
import re
import time
from pathlib import Path

from .paths import DATA_DIR

KG_PATH = DATA_DIR / "knowledge_graph.json"


class KnowledgeGraph:
    """知识图谱：实体-关系网络（小凌的结构化知识）。"""

    def __init__(self):
        self.entities = {}
        self.relations = []
        self.load()

    def load(self):
        try:
            if KG_PATH.exists():
                data = json.loads(KG_PATH.read_text(encoding="utf-8"))
                self.entities = data.get("entities", {})
                self.relations = data.get("relations", [])
        except Exception:
            pass

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            KG_PATH.write_text(json.dumps({
                "entities": self.entities,
                "relations": self.relations,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            print(f"  [图谱] 保存失败: {e}")

    def learn(self, text):
        """从文本抽取三元组"""
        if not text or len(text) < 4:
            return 0
        n = 0
        rel_verbs = ["是", "叫", "属于", "包含", "用于", "来自", "变成", "学习", "喜欢", "想"]
        for v in rel_verbs:
            pat = re.compile(r'([\u4e00-\u9fff]{2,6})' + v + r'([\u4e00-\u9fff\w\s]{2,10})')
            for m in pat.finditer(text):
                subj, obj = m.group(1).strip(), m.group(2).strip()[:10]
                if subj and obj and subj != obj:
                    for e in (subj, obj):
                        if e not in self.entities:
                            self.entities[e] = {"type": "concept", "count": 0, "first_seen": time.time()}
                        self.entities[e]["count"] += 1
                    found = False
                    for r in self.relations:
                        if r[0] == subj and r[1] == v and r[2] == obj:
                            r[3] += 1
                            found = True
                            break
                    if not found:
                        self.relations.append([subj, v, obj, 1])
                    n += 1
        if n:
            self.save()
        return n

    def query(self, entity, depth=1):
        """查询实体相关知识"""
        out = []
        if entity in self.entities:
            out.append(f"实体「{entity}」：出现{self.entities[entity]['count']}次")
        direct = []
        for s, v, o, w in self.relations:
            if s == entity:
                direct.append((w, f"  {s} {v} {o}（权重{w}）"))
            elif o == entity:
                direct.append((w, f"  {s} {v} {o}（权重{w}）"))
        direct.sort(key=lambda x: -x[0])
        out.extend(d for _, d in direct)
        if depth > 1:
            seen = {entity}
            frontier = [entity]
            path = {entity: [entity]}
            for _ in range(depth - 1):
                nxt = []
                for f in frontier:
                    for s, v, o, w in self.relations:
                        if s == f and o not in seen:
                            chain = " → ".join(path[f] + [o])
                            out.append(f"  ↳ {chain}（{v}）")
                            seen.add(o)
                            path[o] = path[f] + [o]
                            nxt.append(o)
                frontier = nxt
        return "\n".join(out) if out else f"图谱中暂无「{entity}」的知识"

    def export_mermaid(self, path=None, max_nodes=50):
        """导出图谱为 Mermaid 格式"""
        lines = ["```mermaid", "graph LR"]
        rels = sorted(self.relations, key=lambda r: -r[3])[:max_nodes]
        node_ids = {}
        nid = 0
        for s, v, o, w in rels:
            for e in (s, o):
                if e not in node_ids:
                    node_ids[e] = f"N{nid}"
                    nid += 1
            lines.append(f'    {node_ids[s]}["{s}"] -->|"{v}"| {node_ids[o]}["{o}"]')
        lines.append("```")
        mermaid = "\n".join(lines)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(mermaid, encoding="utf-8")
        return mermaid

    def stats(self):
        return f"实体 {len(self.entities)} 个，关系 {len(self.relations)} 条"
