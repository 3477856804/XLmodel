"""知识系统 - 知识图谱 + RAG检索"""
import json
import re
import time
from pathlib import Path


# ===== 知识图谱 =====
class KnowledgeGraph:
    """知识图谱：实体-关系网络"""

    def __init__(self):
        self.entities = {}
        self.relations = []

    def learn(self, text: str) -> int:
        """从文本抽取三元组"""
        if not text or len(text) < 4:
            return 0
        n = 0
        rel_verbs = ["是", "叫", "属于", "包含", "用于", "来自"]
        for v in rel_verbs:
            pat = re.compile(r'([\u4e00-\u9fff]{2,6})' + v + r'([\u4e00-\u9fff\w\s]{2,10})')
            for m in pat.finditer(text):
                subj, obj = m.group(1).strip(), m.group(2).strip()[:10]
                if subj and obj and subj != obj:
                    n += 1
        return n

    def query(self, entity: str, depth: int = 1) -> str:
        """查询实体相关知识"""
        if entity in self.entities:
            return f"实体「{entity}」：出现{self.entities[entity].get('count', 0)}次"
        return f"图谱中暂无「{entity}」的知识"

    def stats(self) -> str:
        return f"实体 {len(self.entities)} 个，关系 {len(self.relations)} 条"


# ===== RAG 检索 =====
class RAG:
    """RAG 检索系统"""

    def __init__(self, vector_store=None):
        self.vector_store = vector_store
        self.documents = []

    def add_document(self, content: str, metadata: dict = None):
        """添加文档"""
        self.documents.append({
            "content": content,
            "metadata": metadata or {},
            "time": time.time(),
        })

    def search(self, query: str, top_k: int = 5) -> list:
        """检索相关文档"""
        results = []
        query_words = set(query.lower().split())
        for doc in self.documents:
            doc_words = set(doc["content"].lower().split())
            score = len(query_words & doc_words)
            if score > 0:
                results.append((score, doc))
        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:top_k]]

    def format_for_prompt(self, query: str) -> str:
        """格式化检索结果用于 prompt"""
        docs = self.search(query, top_k=3)
        if not docs:
            return ""
        lines = ["【相关知识】"]
        for doc in docs:
            lines.append(f"- {doc['content'][:100]}")
        return "\n".join(lines)
