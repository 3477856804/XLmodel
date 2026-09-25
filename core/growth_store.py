#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.growth_store —— 训练数据仓库（SQLite + 哈希向量去重 + DPO 偏好对）
==========================================================================

对应设计文档《小凌个人模型成长管线设计文档》第二章「三层结构」与第三章
「通过 API 对话记录回答答案」，把"用户怎么聊 → 变成什么训练样本"这件事落成
可查询、可删除、可导出、可追溯的本地数据仓库。

记录结构（文档 3.1 节，字段名保持一致）：

    id / timestamp / user_input / base_model_output / deepseek_output
    user_feedback(like|dislike|correct) / corrected_output / memory_tags
    quality_score / used_in_training / training_round

存储分工（文档 3.2 节）：

    · SQLite         结构化字段、反馈、质量分、训练轮次   ← 本模块
    · 向量去重        user_input 的 embedding（本地哈希向量，零依赖）
    · 文件系统        原始对话日志，按月归档 `数据/records/YYYY-MM.jsonl`

数据使用规则（文档 3.3 节）：

    quality_score 高        → 训练正样本
    用户点踩                → 负样本 / DPO 偏好对
    DeepSeek 回答优于基底   → 蒸馏样本
    重复问题                → 去重，只留最优回答
    已用于训练              → 标记 training_round，避免重复训练

隐私与用户控制（文档 3.5 节）：纯本地存储、可一键清空、可加密导出/导入、
可查看每条样本是否被用于训练。

用法：
    python3 -m core.growth_store add --q "你好" --a "你好呀" --teacher "你好，很高兴见到你"
    python3 -m core.growth_store stats
    python3 -m core.growth_store list --limit 20
    python3 -m core.growth_store feedback <id> like
    python3 -m core.growth_store dedupe
    python3 -m core.growth_store export 数据/export.jsonl
    python3 -m core.growth_store purge --scope trained
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.paths import APP_DIR, STAR_DIR

# 向量维度与 config.rag.dim 保持一致（512），便于和 RAG 共用一套检索思路
EMB_DIM = 512
DEDUP_THRESHOLD = 0.97          # 余弦相似度 ≥ 该值视为同一问题（文档 3.3「重复问题只留最优」）

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id               TEXT PRIMARY KEY,
    ts               INTEGER NOT NULL,
    created_at       TEXT    NOT NULL,
    user_input       TEXT    NOT NULL,
    base_model_output TEXT   DEFAULT '',
    deepseek_output  TEXT    DEFAULT '',
    user_feedback    TEXT    DEFAULT '',          -- like | dislike | correct | ''
    corrected_output TEXT    DEFAULT '',
    memory_tags      TEXT    DEFAULT '[]',        -- JSON 数组
    quality_score    REAL    DEFAULT 0,
    score_detail     TEXT    DEFAULT '{}',        -- 质量分可解释明细
    used_in_training INTEGER DEFAULT 0,
    training_round   INTEGER DEFAULT NULL,
    prompt_hash      TEXT    DEFAULT '',
    embedding        BLOB,                        -- float32 小端，EMB_DIM 维
    dup_of           TEXT    DEFAULT '',          -- 被判定为重复时，指向保留的那条 id
    source           TEXT    DEFAULT 'chat',      -- chat | import | distill | manual
    topic            TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_records_hash    ON records(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_records_quality ON records(quality_score);
CREATE INDEX IF NOT EXISTS idx_records_used    ON records(used_in_training);
CREATE INDEX IF NOT EXISTS idx_records_round   ON records(training_round);
CREATE INDEX IF NOT EXISTS idx_records_dup     ON records(dup_of);

CREATE TABLE IF NOT EXISTS dpo_pairs (
    id             TEXT PRIMARY KEY,
    ts             INTEGER NOT NULL,
    prompt         TEXT NOT NULL,
    chosen         TEXT NOT NULL,          -- 偏好回答
    rejected       TEXT NOT NULL,          -- 被拒回答
    source_record  TEXT DEFAULT '',
    used_in_training INTEGER DEFAULT 0,
    training_round INTEGER DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_dpo_used ON dpo_pairs(used_in_training);

CREATE TABLE IF NOT EXISTS train_rounds (
    round        INTEGER PRIMARY KEY,
    started_at   TEXT    NOT NULL,
    finished_at  TEXT    DEFAULT '',
    samples      INTEGER DEFAULT 0,        -- 本轮用户样本数
    base_mix     INTEGER DEFAULT 0,        -- 混入的防遗忘通用样本数
    avg_loss     REAL    DEFAULT NULL,
    adapter_before INTEGER DEFAULT 0,
    adapter_after  INTEGER DEFAULT 0,
    note         TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


# --------------------------------------------------------------------- 工具
def _now_ts() -> int:
    return int(time.time())


def _iso(ts: int | None = None) -> str:
    return datetime.fromtimestamp(ts if ts else _now_ts(), tz=timezone.utc).astimezone().isoformat(timespec='seconds')


def _norm(text: str) -> str:
    """提问归一化：去空白、去标点差异、统一小写，用于 hash 与向量。"""
    t = (text or '').strip().lower()
    out = []
    for ch in t:
        if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
            out.append(ch)
    return ''.join(out)


def prompt_hash(text: str) -> str:
    return hashlib.sha256(_norm(text).encode('utf-8')).hexdigest()[:32]


def embed(text: str, dim: int = EMB_DIM):
    """零依赖本地 embedding：字符 1/2/3-gram 哈希到固定维度 + L2 归一化。

    只用标准库（无 numpy 依赖也能跑），因此去重与召回在纯 CPU、无 torch
    的环境里同样可用；与 RAG 的向量库可共用同一思想（见 core/rag.py）。
    """
    vec = [0.0] * dim
    s = _norm(text)
    if not s:
        return vec
    for n in (1, 2, 3):
        for i in range(max(len(s) - n + 1, 0)):
            gram = s[i:i + n]
            h = hashlib.blake2b(gram.encode('utf-8'), digest_size=8).digest()
            idx = int.from_bytes(h[:4], 'little') % dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign * (1.0 / n)          # 长 gram 权重略降，避免短词主导
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a, b) -> float:
    if not a or not b:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _pack(vec) -> bytes:
    import struct
    return struct.pack(f'<{len(vec)}f', *vec)


def _unpack(blob) -> list:
    import struct
    if not blob:
        return []
    n = len(blob) // 4
    return list(struct.unpack(f'<{n}f', blob[:n * 4]))


# ---------------------------------------------------------------- 质量打分
def score_quality(user_input: str = '', answer: str = '', teacher: str = '',
                  feedback: str = '', tags=None, corrected: str = '') -> tuple:
    """启发式质量分（0~1）+ 可解释明细。

    说明：这是**纯规则、确定性、离线可复现**的打分，不是模型评判；四项权重固定，
    可在配置 `growth.quality_weights` 中调整。分数用途只有一个——决定样本进不进
    训练池、以及排序时的优先级。
    """
    tags = tags or []
    answer = answer or corrected or ''
    len_score = min(len(answer) / 200.0, 1.0)                       # 太短的回答信息量低
    base_part = 1.0 if (teacher and teacher.strip()) else 0.5       # 有老师回答 → 蒸馏价值更高
    fb = {'like': 1.0, 'correct': 0.95, 'dislike': 0.1, '': 0.6}.get(feedback, 0.6)
    tag_part = 1.0 if tags else 0.5                                 # 命中记忆标签（称呼/喜好/作息…）
    q_part = 1.0 if (user_input or '').strip() else 0.4
    detail = {'len': round(len_score, 3), 'teacher': base_part, 'feedback': fb,
              'tags': tag_part, 'question': q_part}
    score = (0.25 * len_score + 0.20 * base_part + 0.25 * fb
             + 0.15 * tag_part + 0.15 * q_part)
    return round(min(max(score, 0.0), 1.0), 4), detail


# ------------------------------------------------------------------- 主类
class GrowthStore:
    """训练数据仓库。线程内使用（桌宠/训练子进程各自一个实例）。"""

    def __init__(self, root: Path | str | None = None, db_path: Path | str | None = None,
                 archive: bool = True):
        self.app_dir = Path(root) if root else APP_DIR
        self.star = self.app_dir / '.star_core'
        self.growth_dir = self.star / 'growth'
        self.growth_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path else (self.growth_dir / 'records.db')
        self.archive_dir = self.app_dir / '数据' / 'records'
        self.archive = archive
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # ----------------------------------------------------------- 基础
    def close(self):
        try:
            self.conn.close()
        except Exception:                                            # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _kv_set(self, k, v):
        self.conn.execute('INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',
                          (k, json.dumps(v, ensure_ascii=False)))

    def _kv_get(self, k, default=None):
        row = self.conn.execute('SELECT v FROM kv WHERE k=?', (k,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row['v'])
        except Exception:                                            # noqa: BLE001
            return default

    def _archive_row(self, row: dict):
        if not self.archive:
            return
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            month = datetime.now().strftime('%Y-%m')
            with open(self.archive_dir / f'{month}.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        except OSError:
            pass

    # ----------------------------------------------------------- 写入
    def add(self, user_input: str, base_output: str = '', teacher_output: str = '',
            feedback: str = '', corrected: str = '', tags=None, topic: str = '',
            source: str = 'chat', dedupe: bool = True) -> dict:
        """写入一条对话记录。重复提问会被标记 `dup_of`（不删除，仍可查询与审计）。"""
        tags = list(tags or [])
        ts = _now_ts()
        rid = str(uuid.uuid4())
        ph = prompt_hash(user_input)
        vec = embed(user_input)
        dup_of = ''
        if dedupe:
            same = self.conn.execute(
                'SELECT id, quality_score, embedding FROM records WHERE prompt_hash=? AND dup_of="" '
                'ORDER BY quality_score DESC LIMIT 5', (ph,)).fetchall()
            for r in same:
                if cosine(vec, _unpack(r['embedding'])) >= DEDUP_THRESHOLD:
                    dup_of = r['id']
                    break
        score, detail = score_quality(user_input, base_output, teacher_output, feedback, tags, corrected)
        row = {
            'id': rid, 'ts': ts, 'created_at': _iso(ts), 'user_input': user_input,
            'base_model_output': base_output, 'deepseek_output': teacher_output,
            'user_feedback': feedback, 'corrected_output': corrected,
            'memory_tags': tags, 'quality_score': score, 'score_detail': detail,
            'used_in_training': 0, 'training_round': None, 'prompt_hash': ph,
            'dup_of': dup_of, 'source': source, 'topic': topic,
        }
        self.conn.execute(
            'INSERT INTO records(id, ts, created_at, user_input, base_model_output, deepseek_output,'
            ' user_feedback, corrected_output, memory_tags, quality_score, score_detail,'
            ' used_in_training, training_round, prompt_hash, embedding, dup_of, source, topic)'
            ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (rid, ts, row['created_at'], user_input, base_output, teacher_output, feedback, corrected,
             json.dumps(tags, ensure_ascii=False), score, json.dumps(detail, ensure_ascii=False),
             0, None, ph, _pack(vec), dup_of, source, topic))
        # 点踩 → 自动生成 DPO 偏好对（文档 3.3：负样本或 DPO 偏好对）
        if feedback == 'dislike':
            chosen = corrected or teacher_output
            rejected = base_output
            if chosen and rejected and chosen.strip() != rejected.strip():
                self.add_dpo(user_input, chosen, rejected, source_record=rid)
        self.conn.commit()
        row['dup'] = bool(dup_of)
        self._archive_row(row)
        return row

    def add_dpo(self, prompt: str, chosen: str, rejected: str, source_record: str = '') -> str:
        did = str(uuid.uuid4())
        self.conn.execute(
            'INSERT INTO dpo_pairs(id, ts, prompt, chosen, rejected, source_record, used_in_training,'
            ' training_round) VALUES(?,?,?,?,?,?,0,NULL)',
            (did, _now_ts(), prompt, chosen, rejected, source_record))
        self.conn.commit()
        return did

    def set_feedback(self, rid: str, feedback: str, corrected: str | None = None) -> dict:
        """用户点赞/点踩/纠正（文档 2.2 第 2 路数据来源）。"""
        row = self.get(rid)
        if not row:
            return {'ok': False, 'error': f'记录不存在：{rid}'}
        corrected = row['corrected_output'] if corrected is None else corrected
        score, detail = score_quality(row['user_input'], row['base_model_output'],
                                      row['deepseek_output'], feedback,
                                      row['memory_tags'], corrected)
        self.conn.execute('UPDATE records SET user_feedback=?, corrected_output=?, quality_score=?,'
                          ' score_detail=? WHERE id=?',
                          (feedback, corrected, score, json.dumps(detail, ensure_ascii=False), rid))
        if feedback == 'dislike':
            chosen = corrected or row['deepseek_output']
            if chosen and row['base_model_output'] and chosen.strip() != row['base_model_output'].strip():
                self.add_dpo(row['user_input'], chosen, row['base_model_output'], source_record=rid)
        self.conn.commit()
        return {'ok': True, 'id': rid, 'feedback': feedback, 'quality_score': score}

    def recompute_quality(self, rid: str | None = None) -> int:
        rows = self.conn.execute('SELECT * FROM records' + (' WHERE id=?' if rid else ''),
                                 ((rid,) if rid else ())).fetchall()
        n = 0
        for r in rows:
            score, detail = score_quality(r['user_input'], r['base_model_output'], r['deepseek_output'],
                                          r['user_feedback'], json.loads(r['memory_tags'] or '[]'),
                                          r['corrected_output'])
            self.conn.execute('UPDATE records SET quality_score=?, score_detail=? WHERE id=?',
                              (score, json.dumps(detail, ensure_ascii=False), r['id']))
            n += 1
        self.conn.commit()
        return n

    def mark_trained(self, ids, round_no: int) -> int:
        """把样本标记为已用于第 N 轮训练（文档 3.3：避免重复训练）。"""
        ids = list(ids or [])
        if not ids:
            return 0
        self.conn.executemany('UPDATE records SET used_in_training=1, training_round=? WHERE id=?',
                              [(round_no, i) for i in ids])
        self.conn.commit()
        return len(ids)

    def mark_dpo_trained(self, ids, round_no: int) -> int:
        ids = list(ids or [])
        if not ids:
            return 0
        self.conn.executemany('UPDATE dpo_pairs SET used_in_training=1, training_round=? WHERE id=?',
                              [(round_no, i) for i in ids])
        self.conn.commit()
        return len(ids)

    def delete(self, rid: str) -> bool:
        cur = self.conn.execute('DELETE FROM records WHERE id=?', (rid,))
        self.conn.commit()
        return cur.rowcount > 0

    # ----------------------------------------------------------- 查询
    _COLS = ('id', 'ts', 'created_at', 'user_input', 'base_model_output', 'deepseek_output',
             'user_feedback', 'corrected_output', 'memory_tags', 'quality_score', 'score_detail',
             'used_in_training', 'training_round', 'prompt_hash', 'dup_of', 'source', 'topic')

    @staticmethod
    def _row_to_dict(r) -> dict:
        d = {k: r[k] for k in GrowthStore._COLS if k in r.keys()}
        try:
            d['memory_tags'] = json.loads(d.get('memory_tags') or '[]')
        except Exception:                                            # noqa: BLE001
            d['memory_tags'] = []
        try:
            d['score_detail'] = json.loads(d.get('score_detail') or '{}')
        except Exception:                                            # noqa: BLE001
            d['score_detail'] = {}
        d['used_in_training'] = bool(d.get('used_in_training'))
        return d

    def get(self, rid: str) -> dict | None:
        r = self.conn.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()
        return self._row_to_dict(r) if r else None

    def list_records(self, limit: int = 50, offset: int = 0, feedback: str = '',
                     used: int | None = None, min_quality: float | None = None,
                     include_dup: bool = True) -> list:
        sql, args = 'SELECT * FROM records WHERE 1=1', []
        if feedback:
            sql += ' AND user_feedback=?'
            args.append(feedback)
        if used is not None:
            sql += ' AND used_in_training=?'
            args.append(1 if used else 0)
        if min_quality is not None:
            sql += ' AND quality_score>=?'
            args.append(float(min_quality))
        if not include_dup:
            sql += ' AND dup_of=""'
        sql += ' ORDER BY ts DESC LIMIT ? OFFSET ?'
        args += [int(limit), int(offset)]
        return [self._row_to_dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def pending(self, min_quality: float = 0.5, include_dislike: bool = False,
                include_dups: bool = False) -> list:
        """尚未用于训练、质量达标的样本（训练池候选）。"""
        sql = 'SELECT * FROM records WHERE used_in_training=0 AND quality_score>=?'
        args = [float(min_quality)]
        if not include_dislike:
            sql += ' AND user_feedback<>"dislike"'
        if not include_dups:
            sql += ' AND dup_of=""'
        sql += ' ORDER BY quality_score DESC, ts DESC'
        return [self._row_to_dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def distill_samples(self, include_trained: bool = False) -> list:
        """可作蒸馏样本的记录：老师回答存在且质量达标。"""
        sql = 'SELECT * FROM records WHERE deepseek_output<>"" AND quality_score>=? AND dup_of=""'
        if not include_trained:
            sql += ' AND used_in_training=0'
        sql += ' ORDER BY quality_score DESC, ts DESC'
        return [self._row_to_dict(r) for r in self.conn.execute(sql, [0.5]).fetchall()]

    def dpo_pairs(self, untrained_only: bool = True) -> list:
        sql = 'SELECT * FROM dpo_pairs'
        if untrained_only:
            sql += ' WHERE used_in_training=0'
        sql += ' ORDER BY ts DESC'
        return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def stats(self) -> dict:
        c = self.conn.execute
        total = c('SELECT COUNT(*) n FROM records').fetchone()['n']
        dup = c('SELECT COUNT(*) n FROM records WHERE dup_of<>""').fetchone()['n']
        trained = c('SELECT COUNT(*) n FROM records WHERE used_in_training=1').fetchone()['n']
        avg = c('SELECT AVG(quality_score) a FROM records WHERE dup_of=""').fetchone()['a'] or 0
        fbs = {r['user_feedback'] or 'none': r['n'] for r in
               c('SELECT user_feedback, COUNT(*) n FROM records GROUP BY user_feedback').fetchall()}
        dpo = c('SELECT COUNT(*) n FROM dpo_pairs').fetchone()['n']
        dpo_used = c('SELECT COUNT(*) n FROM dpo_pairs WHERE used_in_training=1').fetchone()['n']
        teacher = c('SELECT COUNT(*) n FROM records WHERE deepseek_output<>""').fetchone()['n']
        rounds = c('SELECT COUNT(*) n FROM train_rounds').fetchone()['n']
        pend = len(self.pending())
        return {
            'total': total, 'duplicates': dup, 'unique': total - dup,
            'used_in_training': trained, 'pending': pend,
            'avg_quality': round(float(avg), 4),
            'feedback': {'like': fbs.get('like', 0), 'dislike': fbs.get('dislike', 0),
                         'correct': fbs.get('correct', 0), 'none': fbs.get('none', 0)},
            'with_teacher': teacher, 'dpo_pairs': dpo, 'dpo_used': dpo_used,
            'train_rounds': rounds, 'db': str(self.db_path),
        }

    # ----------------------------------------------------------- 训练取样
    def sample_for_training(self, limit: int = 500, min_quality: float = 0.5,
                            base_mix_ratio: float = 0.15, base_corpus: Path | None = None) -> dict:
        """取一批训练样本，并按设计文档 2.4 节混入 10%~20% 通用数据防遗忘。

        返回 {'samples': [{'question','answer'}...], 'records': [id...], 'base_mix': n,
              'ratio': float}
        """
        rows = self.pending(min_quality=min_quality)
        picked = rows[:int(limit)]
        samples, ids = [], []
        for r in picked:
            q = r['user_input']
            a = (r['corrected_output'] or r['deepseek_output'] or r['base_model_output'] or '').strip()
            if not a:
                continue
            samples.append({'question': q, 'answer': a, 'topic': r.get('topic', ''),
                            'record_id': r['id']})
            ids.append(r['id'])
        base_mix = []
        corpus = Path(base_corpus) if base_corpus else (self.app_dir / '数据' / 'corpus.txt')
        ratio = max(0.0, min(float(base_mix_ratio or 0.0), 0.5))
        want = int(len(samples) * ratio / max(1e-6, 1 - ratio))
        if samples and ratio > 0:                      # 文档 2.4：有样本就至少混入 1 条通用语料
            want = max(want, 1)
        if want > 0 and corpus.exists():
            lines = [l.strip() for l in corpus.read_text(encoding='utf-8', errors='ignore').splitlines()
                     if l.strip()]
            if lines:
                step = max(len(lines) // max(want, 1), 1)
                for i in range(0, min(len(lines), want * step), step):
                    base_mix.append({'question': '', 'answer': lines[i], 'topic': 'base_mix'})
                    if len(base_mix) >= want:
                        break
        return {'samples': samples + base_mix, 'records': ids, 'base_mix': len(base_mix),
                'ratio': round(len(base_mix) / max(len(samples) + len(base_mix), 1), 3)}

    def write_corpus(self, path: Path | str, limit: int = 500, min_quality: float = 0.5,
                     base_mix_ratio: float = 0.15) -> dict:
        """把采样结果写成语料 jsonl（core.peft_train 直接可读）。"""
        pack = self.sample_for_training(limit=limit, min_quality=min_quality,
                                       base_mix_ratio=base_mix_ratio)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            for s in pack['samples']:
                row = {'question': s['question'], 'answer': s['answer']}
                if s.get('topic'):
                    row['topic'] = s['topic']
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        return {'path': str(p), 'written': len(pack['samples']), 'base_mix': pack['base_mix'],
                'ratio': pack['ratio'], 'records': pack['records']}

    # ----------------------------------------------------------- 轮次/去重/导出
    def begin_round(self, round_no: int, samples: int, base_mix: int,
                    adapter_before: int = 0, note: str = '') -> None:
        self.conn.execute('INSERT INTO train_rounds(round, started_at, samples, base_mix,'
                          ' adapter_before, note) VALUES(?,?,?,?,?,?)'
                          ' ON CONFLICT(round) DO UPDATE SET samples=excluded.samples,'
                          ' base_mix=excluded.base_mix, adapter_before=excluded.adapter_before',
                          (int(round_no), _iso(), int(samples), int(base_mix),
                           int(adapter_before), note))
        self.conn.commit()

    def finish_round(self, round_no: int, avg_loss=None, adapter_after: int = 0, note: str = '') -> None:
        self.conn.execute('UPDATE train_rounds SET finished_at=?, avg_loss=?, adapter_after=?, note=?'
                          ' WHERE round=?',
                          (_iso(), avg_loss, int(adapter_after), note, int(round_no)))
        self.conn.commit()

    def rounds(self, limit: int = 50) -> list:
        return [dict(r) for r in self.conn.execute(
            'SELECT * FROM train_rounds ORDER BY round DESC LIMIT ?', (int(limit),)).fetchall()]

    def loss_curve(self, limit: int = 100) -> list:
        """仪表盘用：每轮平均损失曲线。"""
        return [{'round': r['round'], 'avg_loss': r['avg_loss'], 'samples': r['samples']}
                for r in self.conn.execute(
                    'SELECT round, avg_loss, samples FROM train_rounds WHERE avg_loss IS NOT NULL'
                    ' ORDER BY round ASC LIMIT ?', (int(limit),)).fetchall()]

    def dedupe(self, threshold: float = DEDUP_THRESHOLD, dry_run: bool = False) -> dict:
        """历史数据的重复问题归并（保留质量分最高的一条，其余标 dup_of）。"""
        rows = self.conn.execute('SELECT * FROM records ORDER BY quality_score DESC, ts ASC').fetchall()
        kept, marked = [], 0
        for r in rows:
            if r['dup_of']:
                continue
            vec = _unpack(r['embedding'])
            hit = None
            for k in kept:
                if cosine(vec, k['vec']) >= threshold:
                    hit = k
                    break
            if hit:
                marked += 1
                if not dry_run:
                    self.conn.execute('UPDATE records SET dup_of=? WHERE id=?', (hit['id'], r['id']))
            else:
                kept.append({'id': r['id'], 'vec': vec})
        if not dry_run:
            self.conn.commit()
        return {'scanned': len(rows), 'kept': len(kept), 'marked_dup': marked,
                'threshold': threshold, 'dry_run': dry_run}

    def export_jsonl(self, path: Path | str, only_untrained: bool = False,
                     include_dpo: bool = True, encrypt_key: str = '') -> dict:
        """导出训练集（文档 3.5：导出/导入训练集可加密）。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        sql = 'SELECT * FROM records' + (' WHERE used_in_training=0' if only_untrained else '')
        rows = [self._row_to_dict(r) for r in self.conn.execute(sql).fetchall()]
        payload = {'kind': 'xiaoling-growth-export', 'version': 1, 'exported_at': _iso(),
                   'records': rows,
                   'dpo': self.dpo_pairs(untrained_only=False) if include_dpo else []}
        raw = json.dumps(payload, ensure_ascii=False, indent=1).encode('utf-8')
        if encrypt_key:
            raw = _xor_encrypt(raw, encrypt_key)
            p = p.with_suffix(p.suffix + '.enc')
        p.write_bytes(raw)
        return {'path': str(p), 'records': len(rows), 'dpo': len(payload['dpo']),
                'encrypted': bool(encrypt_key), 'bytes': len(raw)}

    def import_jsonl(self, path: Path | str, encrypt_key: str = '') -> dict:
        p = Path(path)
        raw = p.read_bytes()
        if raw[:1] not in (b'{', b'['):
            if not encrypt_key:
                return {'ok': False, 'error': '文件是加密的，请提供 --key'}
            raw = _xor_encrypt(raw, encrypt_key)
        try:
            data = json.loads(raw.decode('utf-8'))
        except Exception as e:                                       # noqa: BLE001
            return {'ok': False, 'error': f'解析失败：{e}'}
        rows = data.get('records', data if isinstance(data, list) else [])
        n = 0
        for r in rows:
            self.add(r.get('user_input', ''), r.get('base_model_output', ''),
                     r.get('deepseek_output', ''), r.get('user_feedback', ''),
                     r.get('corrected_output', ''), r.get('memory_tags') or [],
                     r.get('topic', ''), source='import', dedupe=True)
            n += 1
        for d in data.get('dpo', []) if isinstance(data, dict) else []:
            self.add_dpo(d.get('prompt', ''), d.get('chosen', ''), d.get('rejected', ''))
        return {'ok': True, 'imported': n, 'dpo': len(data.get('dpo', [])) if isinstance(data, dict) else 0}

    def purge(self, scope: str = 'all') -> dict:
        """一键清空训练数据（文档 3.5）。scope: all | trained | disliked | dpo"""
        before = self.stats()
        if scope == 'all':
            self.conn.execute('DELETE FROM records')
            self.conn.execute('DELETE FROM dpo_pairs')
        elif scope == 'trained':
            self.conn.execute('DELETE FROM records WHERE used_in_training=1')
        elif scope == 'disliked':
            self.conn.execute('DELETE FROM records WHERE user_feedback="dislike"')
        elif scope == 'dpo':
            self.conn.execute('DELETE FROM dpo_pairs')
        else:
            return {'ok': False, 'error': f'未知 scope：{scope}'}
        self.conn.commit()
        after = self.stats()
        self._kv_set('last_purge', {'at': _iso(), 'scope': scope})
        return {'ok': True, 'scope': scope, 'removed': before['total'] - after['total'],
                'remaining': after['total']}


def _xor_encrypt(data: bytes, key: str) -> bytes:
    """轻量本地混淆（非密码学强度，仅防明文直读；文档 3.5 的"加密导出"）。

    实现为 SHA-256 流密钥的重复异或，密钥不同则无法直接还原；
    正式密钥管理请配合系统钥匙串/用户口令，不要把它当强加密使用。
    """
    kb = hashlib.sha256(key.encode('utf-8')).digest() * (len(data) // 32 + 1)
    return bytes(a ^ b for a, b in zip(data, kb[:len(data)]))


# ------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌训练数据仓库')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add')
    p.add_argument('--q', required=True, help='用户输入')
    p.add_argument('--a', default='', help='基底模型回答')
    p.add_argument('--teacher', default='', help='DeepSeek 回答')
    p.add_argument('--feedback', default='', choices=['', 'like', 'dislike', 'correct'])
    p.add_argument('--corrected', default='')
    p.add_argument('--tags', default='', help='逗号分隔')
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('list')
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--feedback', default='')
    p.add_argument('--used', type=int, default=None)
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('stats')
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('feedback')
    p.add_argument('id')
    p.add_argument('value', choices=['like', 'dislike', 'correct'])
    p.add_argument('--corrected', default=None)
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('dedupe')
    p.add_argument('--threshold', type=float, default=DEDUP_THRESHOLD)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('export')
    p.add_argument('path')
    p.add_argument('--only-untrained', action='store_true')
    p.add_argument('--key', default='')
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('import')
    p.add_argument('path')
    p.add_argument('--key', default='')
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('purge')
    p.add_argument('--scope', default='all', choices=['all', 'trained', 'disliked', 'dpo'])
    p.add_argument('--root', default=str(APP_DIR))

    p = sub.add_parser('sample')
    p.add_argument('--limit', type=int, default=500)
    p.add_argument('--out', default='')
    p.add_argument('--base-mix', type=float, default=0.15)
    p.add_argument('--root', default=str(APP_DIR))

    a = ap.parse_args(argv)
    store = GrowthStore(a.root)
    if a.cmd == 'add':
        tags = [t for t in a.tags.split(',') if t.strip()]
        row = store.add(a.q, a.a, a.teacher, a.feedback, a.corrected, tags)
        print(json.dumps({'id': row['id'], 'quality_score': row['quality_score'],
                          'dup': row['dup'], 'detail': row['score_detail']},
                         ensure_ascii=False, indent=1))
    elif a.cmd == 'list':
        for r in store.list_records(limit=a.limit, feedback=a.feedback, used=a.used):
            flag = 'DUP' if r['dup_of'] else ('TRAINED' if r['used_in_training'] else 'PENDING')
            print(f"[{flag}] {r['quality_score']:.2f}  {r['created_at']}  {r['user_input'][:40]}")
    elif a.cmd == 'stats':
        print(json.dumps(store.stats(), ensure_ascii=False, indent=1))
    elif a.cmd == 'feedback':
        print(json.dumps(store.set_feedback(a.id, a.value, a.corrected), ensure_ascii=False, indent=1))
    elif a.cmd == 'dedupe':
        print(json.dumps(store.dedupe(a.threshold, a.dry_run), ensure_ascii=False, indent=1))
    elif a.cmd == 'export':
        print(json.dumps(store.export_jsonl(a.path, a.only_untrained, encrypt_key=a.key),
                         ensure_ascii=False, indent=1))
    elif a.cmd == 'import':
        print(json.dumps(store.import_jsonl(a.path, a.key), ensure_ascii=False, indent=1))
    elif a.cmd == 'purge':
        print(json.dumps(store.purge(a.scope), ensure_ascii=False, indent=1))
    elif a.cmd == 'sample':
        store.recompute_quality()
        if a.out:
            print(json.dumps(store.write_corpus(a.out, limit=a.limit, base_mix_ratio=a.base_mix),
                             ensure_ascii=False, indent=1))
        else:
            pack = store.sample_for_training(limit=a.limit, base_mix_ratio=a.base_mix)
            print(json.dumps({'samples': len(pack['samples']), 'base_mix': pack['base_mix'],
                              'ratio': pack['ratio']}, ensure_ascii=False, indent=1))
    store.close()


if __name__ == '__main__':
    main()
