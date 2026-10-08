"""小凌 · 成长闭环（数据仓库 + 蒸馏节流 + LoRA 训练 + 生命周期 + 晋升 + 回滚）"""
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import struct
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path

from .config import APP_DIR, STAR_DIR, DATA_DIR, load as load_config, patch as patch_config
from .model import best_device, device_kwargs, train_plan

GROWTH_DIR = STAR_DIR / "growth"
ADAPTER_DIR = STAR_DIR / "adapter"
ADAPTER_SEEDS = STAR_DIR / "adapter_seeds"
TRASH_DIR = STAR_DIR / "trash"
LEGACY_RETIRED = STAR_DIR / "base_retired"
BASE_MODEL_DIR = STAR_DIR / "XLmodel"
RECORDS_DB = GROWTH_DIR / "records.db"
RECORDS_ARCHIVE = DATA_DIR / "records"
JOURNAL = GROWTH_DIR / "journal.jsonl"
STATE_PATH = GROWTH_DIR / "replacement_state.json"
REGISTRY_PATH = GROWTH_DIR / "generations.json"
LIFECYCLE_STATE = GROWTH_DIR / "lifecycle.json"
CORPUS_PATH = GROWTH_DIR / "round_corpus.jsonl"
BASE_CORPUS = DATA_DIR / "corpus.txt"
THROTTLE_CACHE = GROWTH_DIR / "distill_cache.json"
THROTTLE_USAGE = GROWTH_DIR / "api_usage.json"

MODEL_WEIGHT_EXTS = (".safetensors", ".bin", ".gguf", ".pt", ".pth")
ADAPTER_WEIGHT_EXTS = (".safetensors", ".bin", ".pt", ".pth")

EMB_DIM = 512
DEDUP_THRESHOLD = 0.97
DEFAULT_TEMPLATES = [
    {"user": "你好", "assistant": "你好呀，我是小凌，住在你电脑里的AI女孩。"},
    {"user": "你是谁", "assistant": "我是小凌，一款会陪你聊天、慢慢成长的人工智能桌宠。"},
    {"user": "谢谢", "assistant": "不客气，有什么需要随时叫我。"},
    {"user": "今天天气不错", "assistant": "是呀，好天气心情也会变好呢。"},
]


def human_bytes(n: float) -> str:
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{int(n)} B"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def dir_bytes(path: Path, exts=None, exclude_adapter: bool = False) -> int:
    if not path or not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        try:
            if not p.is_file():
                continue
            if exts and p.suffix.lower() not in exts:
                continue
            if exclude_adapter and p.name.lower().startswith("adapter"):
                continue
            total += p.stat().st_size
        except OSError:
            pass
    return total


def detect_adapter_dir(star: Path = STAR_DIR) -> Path:
    marks = ("adapter_config.json", "adapter_model.safetensors",
             "adapter.bin", "adapter.pt")
    new = star / "adapter"
    if any((new / m).exists() for m in marks):
        return new
    if any((star / m).exists() for m in marks):
        return star
    return new


def normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    return "".join(c for c in t if c.isalnum() or "\u4e00" <= c <= "\u9fff")


def prompt_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:32]


def embed_hash(text: str, dim: int = EMB_DIM) -> list:
    vec = [0.0] * dim
    s = normalize_text(text)
    if not s:
        return vec
    for n in (1, 2, 3):
        for i in range(max(len(s) - n + 1, 0)):
            gram = s[i:i + n]
            h = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign / n
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def pack_vec(v: list) -> bytes:
    return struct.pack(f"<{len(v)}f", *v)


def unpack_vec(b: bytes) -> list:
    if not b:
        return []
    n = len(b) // 4
    return list(struct.unpack(f"<{n}f", b[:n * 4]))


def xor_encrypt(data: bytes, key: str) -> bytes:
    kb = hashlib.sha256(key.encode("utf-8")).digest() * (len(data) // 32 + 1)
    return bytes(a ^ b for a, b in zip(data, kb[:len(data)]))


def score_quality(user_input: str = "", answer: str = "", teacher: str = "",
                  feedback: str = "", tags=None, corrected: str = "") -> tuple:
    tags = tags or []
    answer = answer or corrected or ""
    len_score = min(len(answer) / 200.0, 1.0)
    base_part = 1.0 if (teacher and teacher.strip()) else 0.5
    fb = {"like": 1.0, "correct": 0.95, "dislike": 0.1, "": 0.6}.get(feedback, 0.6)
    tag_part = 1.0 if tags else 0.5
    q_part = 1.0 if (user_input or "").strip() else 0.4
    detail = {"len": round(len_score, 3), "teacher": base_part, "feedback": fb,
              "tags": tag_part, "question": q_part}
    score = (0.25 * len_score + 0.20 * base_part + 0.25 * fb
             + 0.15 * tag_part + 0.15 * q_part)
    return round(min(max(score, 0.0), 1.0), 4), detail


_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    user_input TEXT NOT NULL,
    base_model_output TEXT DEFAULT '',
    deepseek_output TEXT DEFAULT '',
    user_feedback TEXT DEFAULT '',
    corrected_output TEXT DEFAULT '',
    memory_tags TEXT DEFAULT '[]',
    quality_score REAL DEFAULT 0,
    score_detail TEXT DEFAULT '{}',
    used_in_training INTEGER DEFAULT 0,
    training_round INTEGER DEFAULT NULL,
    prompt_hash TEXT DEFAULT '',
    embedding BLOB,
    dup_of TEXT DEFAULT '',
    source TEXT DEFAULT 'chat',
    topic TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_records_hash ON records(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_records_quality ON records(quality_score);
CREATE INDEX IF NOT EXISTS idx_records_used ON records(used_in_training);
CREATE INDEX IF NOT EXISTS idx_records_round ON records(training_round);
CREATE INDEX IF NOT EXISTS idx_records_dup ON records(dup_of);
CREATE TABLE IF NOT EXISTS dpo_pairs (
    id TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    chosen TEXT NOT NULL,
    rejected TEXT NOT NULL,
    source_record TEXT DEFAULT '',
    used_in_training INTEGER DEFAULT 0,
    training_round INTEGER DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_dpo_used ON dpo_pairs(used_in_training);
CREATE TABLE IF NOT EXISTS train_rounds (
    round INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT DEFAULT '',
    samples INTEGER DEFAULT 0,
    base_mix INTEGER DEFAULT 0,
    avg_loss REAL DEFAULT NULL,
    adapter_before INTEGER DEFAULT 0,
    adapter_after INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


class GrowthStore:
    _COLS = ("id", "ts", "created_at", "user_input", "base_model_output",
             "deepseek_output", "user_feedback", "corrected_output", "memory_tags",
             "quality_score", "score_detail", "used_in_training", "training_round",
             "prompt_hash", "dup_of", "source", "topic")

    def __init__(self, db_path: str | None = None, archive: bool = True):
        self.db_path = Path(db_path) if db_path else RECORDS_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive = archive
        self.archive_dir = RECORDS_ARCHIVE
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self):
        with self._lock:
            try:
                self.conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ---- kv 键值存储（用于每日目标等配置） ----
    def kv_get(self, key: str, default: str = "") -> str:
        try:
            with self._lock:
                row = self.conn.execute(
                    "SELECT v FROM kv WHERE k=?", (key,)).fetchone()
            return row["v"] if row else default
        except Exception:
            return default

    def kv_set(self, key: str, value: str) -> bool:
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)",
                    (key, str(value)))
                self.conn.commit()
            return True
        except Exception:
            return False

    def kv_incr(self, key: str, n: int = 1) -> int:
        """原子递增计数器，返回递增后的值。"""
        try:
            with self._lock:
                row = self.conn.execute(
                    "SELECT v FROM kv WHERE k=?", (key,)).fetchone()
                cur = int(row["v"]) if row and row["v"] else 0
                cur += int(n)
                self.conn.execute(
                    "INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)",
                    (key, str(cur)))
                self.conn.commit()
            return cur
        except Exception:
            return 0

    def _archive(self, row: dict):
        if not self.archive:
            return
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            month = datetime.now().strftime("%Y-%m")
            with open(self.archive_dir / f"{month}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def add(self, user_input: str, base_output: str = "", teacher_output: str = "",
            feedback: str = "", corrected: str = "", tags=None, topic: str = "",
            source: str = "chat", dedupe: bool = True) -> dict:
        tags = list(tags or [])
        ts = int(time.time())
        rid = str(uuid.uuid4())
        ph = prompt_hash(user_input)
        vec = embed_hash(user_input)
        dup_of = ""
        with self._lock:
            if dedupe:
                same = self.conn.execute(
                    "SELECT id, quality_score, embedding FROM records "
                    "WHERE prompt_hash=? AND dup_of='' "
                    "ORDER BY quality_score DESC LIMIT 5", (ph,)).fetchall()
                for r in same:
                    if cosine(vec, unpack_vec(r["embedding"])) >= DEDUP_THRESHOLD:
                        dup_of = r["id"]
                        break
            score, detail = score_quality(user_input, base_output, teacher_output,
                                          feedback, tags, corrected)
            self.conn.execute(
                "INSERT INTO records(id, ts, created_at, user_input, base_model_output,"
                " deepseek_output, user_feedback, corrected_output, memory_tags,"
                " quality_score, score_detail, used_in_training, training_round,"
                " prompt_hash, embedding, dup_of, source, topic)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, ts, now_iso(), user_input, base_output, teacher_output,
                 feedback, corrected, json.dumps(tags, ensure_ascii=False),
                 score, json.dumps(detail, ensure_ascii=False), 0, None,
                 ph, pack_vec(vec), dup_of, source, topic))
            if feedback == "dislike":
                chosen = corrected or teacher_output
                if chosen and base_output and chosen.strip() != base_output.strip():
                    self._add_dpo_locked(user_input, chosen, base_output, rid)
            self.conn.commit()
        row = {"id": rid, "ts": ts, "user_input": user_input,
               "base_model_output": base_output, "deepseek_output": teacher_output,
               "user_feedback": feedback, "corrected_output": corrected,
               "memory_tags": tags, "quality_score": score, "score_detail": detail,
               "used_in_training": False, "training_round": None,
               "prompt_hash": ph, "dup_of": dup_of, "source": source, "topic": topic}
        self._archive(row)
        row["dup"] = bool(dup_of)
        return row

    def _add_dpo_locked(self, prompt: str, chosen: str, rejected: str, source_record: str) -> str:
        did = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO dpo_pairs(id, ts, prompt, chosen, rejected, source_record,"
            " used_in_training, training_round) VALUES(?,?,?,?,?,?,0,NULL)",
            (did, int(time.time()), prompt, chosen, rejected, source_record))
        return did

    def add_dpo(self, prompt: str, chosen: str, rejected: str, source_record: str = "") -> str:
        with self._lock:
            did = self._add_dpo_locked(prompt, chosen, rejected, source_record)
            self.conn.commit()
        return did

    @staticmethod
    def _row(r) -> dict:
        d = {k: r[k] for k in GrowthStore._COLS if k in r.keys()}
        try:
            d["memory_tags"] = json.loads(d.get("memory_tags") or "[]")
        except Exception:
            d["memory_tags"] = []
        try:
            d["score_detail"] = json.loads(d.get("score_detail") or "{}")
        except Exception:
            d["score_detail"] = {}
        d["used_in_training"] = bool(d.get("used_in_training"))
        return d

    def get(self, rid: str) -> dict | None:
        with self._lock:
            r = self.conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return self._row(r) if r else None

    def list_records(self, limit: int = 50, offset: int = 0, feedback: str = "",
                     used: int | None = None, min_quality: float | None = None,
                     include_dup: bool = True) -> list:
        sql, args = "SELECT * FROM records WHERE 1=1", []
        if feedback:
            sql += " AND user_feedback=?"
            args.append(feedback)
        if used is not None:
            sql += " AND used_in_training=?"
            args.append(1 if used else 0)
        if min_quality is not None:
            sql += " AND quality_score>=?"
            args.append(float(min_quality))
        if not include_dup:
            sql += " AND dup_of=''"
        sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        args += [int(limit), int(offset)]
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    def pending(self, min_quality: float = 0.5, include_dislike: bool = False,
                include_dups: bool = False) -> list:
        sql = "SELECT * FROM records WHERE used_in_training=0 AND quality_score>=?"
        args = [float(min_quality)]
        if not include_dislike:
            sql += " AND user_feedback<>'dislike'"
        if not include_dups:
            sql += " AND dup_of=''"
        sql += " ORDER BY quality_score DESC, ts DESC"
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    def distill_samples(self, include_trained: bool = False) -> list:
        sql = "SELECT * FROM records WHERE deepseek_output<>'' AND quality_score>=? AND dup_of=''"
        if not include_trained:
            sql += " AND used_in_training=0"
        sql += " ORDER BY quality_score DESC, ts DESC"
        with self._lock:
            rows = self.conn.execute(sql, [0.5]).fetchall()
        return [self._row(r) for r in rows]

    def dpo_pairs(self, untrained_only: bool = True) -> list:
        sql = "SELECT * FROM dpo_pairs"
        if untrained_only:
            sql += " WHERE used_in_training=0"
        sql += " ORDER BY ts DESC"
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql).fetchall()]

    def set_feedback(self, rid: str, feedback: str, corrected: str | None = None) -> dict:
        row = self.get(rid)
        if not row:
            return {"ok": False, "error": f"记录不存在：{rid}"}
        corrected = row["corrected_output"] if corrected is None else corrected
        score, detail = score_quality(row["user_input"], row["base_model_output"],
                                      row["deepseek_output"], feedback,
                                      row["memory_tags"], corrected)
        with self._lock:
            self.conn.execute(
                "UPDATE records SET user_feedback=?, corrected_output=?, quality_score=?,"
                " score_detail=? WHERE id=?",
                (feedback, corrected, score,
                 json.dumps(detail, ensure_ascii=False), rid))
            if feedback == "dislike":
                chosen = corrected or row["deepseek_output"]
                if chosen and row["base_model_output"] and chosen.strip() != row["base_model_output"].strip():
                    self._add_dpo_locked(row["user_input"], chosen,
                                         row["base_model_output"], rid)
            self.conn.commit()
        return {"ok": True, "id": rid, "feedback": feedback, "quality_score": score}

    def recompute_quality(self, rid: str | None = None) -> int:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM records" + (" WHERE id=?" if rid else ""),
                                     ((rid,) if rid else ())).fetchall()
            n = 0
            for r in rows:
                score, detail = score_quality(
                    r["user_input"], r["base_model_output"], r["deepseek_output"],
                    r["user_feedback"], json.loads(r["memory_tags"] or "[]"),
                    r["corrected_output"])
                self.conn.execute(
                    "UPDATE records SET quality_score=?, score_detail=? WHERE id=?",
                    (score, json.dumps(detail, ensure_ascii=False), r["id"]))
                n += 1
            self.conn.commit()
        return n

    def mark_trained(self, ids, round_no: int) -> int:
        ids = list(ids or [])
        if not ids:
            return 0
        with self._lock:
            self.conn.executemany(
                "UPDATE records SET used_in_training=1, training_round=? WHERE id=?",
                [(round_no, i) for i in ids])
            self.conn.commit()
        return len(ids)

    def mark_dpo_trained(self, ids, round_no: int) -> int:
        ids = list(ids or [])
        if not ids:
            return 0
        with self._lock:
            self.conn.executemany(
                "UPDATE dpo_pairs SET used_in_training=1, training_round=? WHERE id=?",
                [(round_no, i) for i in ids])
            self.conn.commit()
        return len(ids)

    def delete(self, rid: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM records WHERE id=?", (rid,))
            self.conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        with self._lock:
            c = self.conn.execute
            total = c("SELECT COUNT(*) n FROM records").fetchone()["n"]
            dup = c("SELECT COUNT(*) n FROM records WHERE dup_of<>''").fetchone()["n"]
            trained = c("SELECT COUNT(*) n FROM records WHERE used_in_training=1").fetchone()["n"]
            avg = c("SELECT AVG(quality_score) a FROM records WHERE dup_of=''").fetchone()["a"] or 0
            fbs = {r["user_feedback"] or "none": r["n"] for r in
                   c("SELECT user_feedback, COUNT(*) n FROM records GROUP BY user_feedback").fetchall()}
            dpo = c("SELECT COUNT(*) n FROM dpo_pairs").fetchone()["n"]
            dpo_used = c("SELECT COUNT(*) n FROM dpo_pairs WHERE used_in_training=1").fetchone()["n"]
            teacher = c("SELECT COUNT(*) n FROM records WHERE deepseek_output<>''").fetchone()["n"]
            rounds = c("SELECT COUNT(*) n FROM train_rounds").fetchone()["n"]
        pend = len(self.pending())
        return {"total": total, "duplicates": dup, "unique": total - dup,
                "used_in_training": trained, "pending": pend,
                "avg_quality": round(float(avg), 4),
                "feedback": {"like": fbs.get("like", 0), "dislike": fbs.get("dislike", 0),
                             "correct": fbs.get("correct", 0), "none": fbs.get("none", 0)},
                "with_teacher": teacher, "dpo_pairs": dpo, "dpo_used": dpo_used,
                "train_rounds": rounds, "db": str(self.db_path)}

    def sample_for_training(self, limit: int = 500, min_quality: float = 0.5,
                            base_mix_ratio: float = 0.15,
                            base_corpus: Path | None = None) -> dict:
        rows = self.pending(min_quality=min_quality)
        picked = rows[:int(limit)]
        samples, ids = [], []
        for r in picked:
            a = (r["corrected_output"] or r["deepseek_output"]
                 or r["base_model_output"] or "").strip()
            if not a:
                continue
            samples.append({"question": r["user_input"], "answer": a,
                            "topic": r.get("topic", ""), "record_id": r["id"]})
            ids.append(r["id"])
        base_mix = []
        corpus = Path(base_corpus) if base_corpus else BASE_CORPUS
        ratio = max(0.0, min(float(base_mix_ratio or 0.0), 0.5))
        want = int(len(samples) * ratio / max(1e-6, 1 - ratio))
        if samples and ratio > 0:
            want = max(want, 1)
        if want > 0 and corpus.exists():
            lines = [l.strip() for l in corpus.read_text(encoding="utf-8",
                                                         errors="ignore").splitlines()
                     if l.strip()]
            if lines:
                step = max(len(lines) // max(want, 1), 1)
                for i in range(0, min(len(lines), want * step), step):
                    base_mix.append({"question": "", "answer": lines[i],
                                     "topic": "base_mix"})
                    if len(base_mix) >= want:
                        break
        total = len(samples) + len(base_mix)
        return {"samples": samples + base_mix, "records": ids,
                "base_mix": len(base_mix),
                "ratio": round(len(base_mix) / max(total, 1), 3)}

    def write_corpus(self, path: Path | str, limit: int = 500, min_quality: float = 0.5,
                     base_mix_ratio: float = 0.15) -> dict:
        pack = self.sample_for_training(limit=limit, min_quality=min_quality,
                                        base_mix_ratio=base_mix_ratio)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for s in pack["samples"]:
                row = {"question": s["question"], "answer": s["answer"]}
                if s.get("topic"):
                    row["topic"] = s["topic"]
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"path": str(p), "written": len(pack["samples"]),
                "base_mix": pack["base_mix"], "ratio": pack["ratio"],
                "records": pack["records"]}

    def begin_round(self, round_no: int, samples: int, base_mix: int,
                    adapter_before: int = 0, note: str = ""):
        with self._lock:
            self.conn.execute(
                "INSERT INTO train_rounds(round, started_at, samples, base_mix,"
                " adapter_before, note) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(round) DO UPDATE SET samples=excluded.samples,"
                " base_mix=excluded.base_mix, adapter_before=excluded.adapter_before",
                (int(round_no), now_iso(), int(samples), int(base_mix),
                 int(adapter_before), note))
            self.conn.commit()

    def finish_round(self, round_no: int, avg_loss=None, adapter_after: int = 0,
                     note: str = ""):
        with self._lock:
            self.conn.execute(
                "UPDATE train_rounds SET finished_at=?, avg_loss=?, adapter_after=?,"
                " note=? WHERE round=?",
                (now_iso(), avg_loss, int(adapter_after), note, int(round_no)))
            self.conn.commit()

    def rounds(self, limit: int = 50) -> list:
        with self._lock:
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM train_rounds ORDER BY round DESC LIMIT ?",
                (int(limit),)).fetchall()]

    def loss_curve(self, limit: int = 100) -> list:
        with self._lock:
            return [{"round": r["round"], "avg_loss": r["avg_loss"],
                     "samples": r["samples"]}
                    for r in self.conn.execute(
                        "SELECT round, avg_loss, samples FROM train_rounds"
                        " WHERE avg_loss IS NOT NULL ORDER BY round ASC LIMIT ?",
                        (int(limit),)).fetchall()]

    def dedupe(self, threshold: float = DEDUP_THRESHOLD, dry_run: bool = False) -> dict:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM records ORDER BY quality_score DESC, ts ASC").fetchall()
            kept, marked = [], 0
            for r in rows:
                if r["dup_of"]:
                    continue
                vec = unpack_vec(r["embedding"])
                hit = None
                for k in kept:
                    if cosine(vec, k["vec"]) >= threshold:
                        hit = k
                        break
                if hit:
                    marked += 1
                    if not dry_run:
                        self.conn.execute("UPDATE records SET dup_of=? WHERE id=?",
                                          (hit["id"], r["id"]))
                else:
                    kept.append({"id": r["id"], "vec": vec})
            if not dry_run:
                self.conn.commit()
        return {"scanned": len(rows), "kept": len(kept), "marked_dup": marked,
                "threshold": threshold, "dry_run": dry_run}

    def export_jsonl(self, path: Path | str, only_untrained: bool = False,
                     include_dpo: bool = True, encrypt_key: str = "") -> dict:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        sql = "SELECT * FROM records" + (" WHERE used_in_training=0" if only_untrained else "")
        with self._lock:
            rows = [self._row(r) for r in self.conn.execute(sql).fetchall()]
        payload = {"kind": "xiaoling-growth-export", "version": 1,
                   "exported_at": now_iso(), "records": rows,
                   "dpo": self.dpo_pairs(untrained_only=False) if include_dpo else []}
        raw = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        if encrypt_key:
            raw = xor_encrypt(raw, encrypt_key)
            p = p.with_suffix(p.suffix + ".enc")
        p.write_bytes(raw)
        return {"path": str(p), "records": len(rows), "dpo": len(payload["dpo"]),
                "encrypted": bool(encrypt_key), "bytes": len(raw)}

    def import_jsonl(self, path: Path | str, encrypt_key: str = "") -> dict:
        p = Path(path)
        raw = p.read_bytes()
        if raw[:1] not in (b"{", b"["):
            if not encrypt_key:
                return {"ok": False, "error": "文件是加密的，请提供 key"}
            raw = xor_encrypt(raw, encrypt_key)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"解析失败：{e}"}
        rows = data.get("records", data if isinstance(data, list) else [])
        n = 0
        for r in rows:
            self.add(r.get("user_input", ""), r.get("base_model_output", ""),
                     r.get("deepseek_output", ""), r.get("user_feedback", ""),
                     r.get("corrected_output", ""), r.get("memory_tags") or [],
                     r.get("topic", ""), source="import", dedupe=True)
            n += 1
        dpo_n = 0
        if isinstance(data, dict):
            for d in data.get("dpo", []):
                self.add_dpo(d.get("prompt", ""), d.get("chosen", ""),
                             d.get("rejected", ""))
                dpo_n += 1
        return {"ok": True, "imported": n, "dpo": dpo_n}

    def purge(self, scope: str = "all") -> dict:
        before = self.stats()
        with self._lock:
            if scope == "all":
                self.conn.execute("DELETE FROM records")
                self.conn.execute("DELETE FROM dpo_pairs")
            elif scope == "trained":
                self.conn.execute("DELETE FROM records WHERE used_in_training=1")
            elif scope == "disliked":
                self.conn.execute("DELETE FROM records WHERE user_feedback='dislike'")
            elif scope == "dpo":
                self.conn.execute("DELETE FROM dpo_pairs")
            else:
                return {"ok": False, "error": f"未知 scope：{scope}"}
            self.conn.commit()
        after = self.stats()
        return {"ok": True, "scope": scope,
                "removed": before["total"] - after["total"],
                "remaining": after["total"]}


class DistillThrottle:
    DEFAULT_LIMIT = 200

    def __init__(self, enabled: bool = True, daily_limit: int = DEFAULT_LIMIT,
                 price_in: float = 1.0, price_out: float = 2.0):
        self.enabled = enabled
        self.daily_limit = int(daily_limit)
        self.price_in = float(price_in)
        self.price_out = float(price_out)
        self._lock = threading.RLock()
        GROWTH_DIR.mkdir(parents=True, exist_ok=True)

    def _read(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write(self, path: Path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def cache_key(prompt: str, model: str = "") -> str:
        norm = " ".join((prompt or "").strip().split())
        return hashlib.sha256(f"{model}\x00{norm}".encode("utf-8")).hexdigest()[:40]

    def cached(self, prompt: str, model: str = "") -> str | None:
        with self._lock:
            return self._read(THROTTLE_CACHE, {}).get(self.cache_key(prompt, model))

    def used_today(self) -> int:
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
        return int((u.get("days") or {}).get(date.today().isoformat(), {}).get("calls", 0))

    def remaining(self) -> int:
        if self.daily_limit <= 0:
            return 10 ** 9
        return max(self.daily_limit - self.used_today(), 0)

    def check(self, prompt: str, model: str = "") -> dict:
        if not self.enabled:
            return {"ok": False, "reason": "disabled",
                    "message": "API 蒸馏已关闭"}
        hit = self.cached(prompt, model)
        if hit is not None:
            self._bump("cache_hits")
            return {"ok": True, "reason": "cache", "cached": hit,
                    "message": "命中缓存"}
        if self.remaining() <= 0:
            self._bump("blocked")
            return {"ok": False, "reason": "quota",
                    "message": f"今日配额已用完（{self.used_today()}/{self.daily_limit}）"}
        return {"ok": True, "reason": "live",
                "message": f"可调用（今日 {self.used_today()}/{self.daily_limit}）"}

    def _bump(self, field: str, n: int = 1):
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
            u.setdefault("total", {})
            u["total"][field] = int(u["total"].get(field, 0)) + n
            self._write(THROTTLE_USAGE, u)

    def record(self, prompt: str, response: str = "", model: str = "",
               tokens_in: int = 0, tokens_out: int = 0,
               from_cache: bool = False) -> dict:
        today = date.today().isoformat()
        month = datetime.now().strftime("%Y-%m")
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
            u.setdefault("days", {})
            u.setdefault("months", {})
            u.setdefault("total", {})
            d = u["days"].setdefault(today, {"calls": 0, "cache_hits": 0,
                                              "tokens_in": 0, "tokens_out": 0})
            m = u["months"].setdefault(month, {"calls": 0, "cache_hits": 0,
                                                "tokens_in": 0, "tokens_out": 0})
            key = "cache_hits" if from_cache else "calls"
            for bucket in (d, m, u["total"]):
                bucket[key] = int(bucket.get(key, 0)) + 1
                if not from_cache:
                    bucket["tokens_in"] = int(bucket.get("tokens_in", 0)) + int(tokens_in)
                    bucket["tokens_out"] = int(bucket.get("tokens_out", 0)) + int(tokens_out)
            if response and not from_cache:
                cache = self._read(THROTTLE_CACHE, {})
                cache[self.cache_key(prompt, model)] = response
                if len(cache) > 5000:
                    for k in list(cache.keys())[:len(cache) - 5000]:
                        cache.pop(k, None)
                self._write(THROTTLE_CACHE, cache)
            self._write(THROTTLE_USAGE, u)
        return self.cost()

    def cost_of(self, tokens_in: int, tokens_out: int) -> float:
        return round(tokens_in / 1e6 * self.price_in
                     + tokens_out / 1e6 * self.price_out, 6)

    def cost(self, scope: str = "month") -> dict:
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
        if scope == "today":
            b = (u.get("days") or {}).get(date.today().isoformat(), {})
        elif scope == "total":
            b = u.get("total", {})
        else:
            b = (u.get("months") or {}).get(datetime.now().strftime("%Y-%m"), {})
        ti, to = int(b.get("tokens_in", 0)), int(b.get("tokens_out", 0))
        return {"scope": scope, "calls": int(b.get("calls", 0)),
                "cache_hits": int(b.get("cache_hits", 0)),
                "tokens_in": ti, "tokens_out": to,
                "cost_yuan": self.cost_of(ti, to)}

    def usage_report(self) -> dict:
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
            cache = self._read(THROTTLE_CACHE, {})
        return {"enabled": self.enabled, "daily_limit": self.daily_limit,
                "used_today": self.used_today(), "remaining_today": self.remaining(),
                "cache_entries": len(cache), "total": dict(u.get("total", {})),
                "today": self.cost("today"), "month": self.cost("month"),
                "all_time": self.cost("total")}

    def set_enabled(self, on: bool):
        self.enabled = bool(on)

    def set_daily_limit(self, n: int):
        self.daily_limit = int(n)

    def reset_today(self):
        with self._lock:
            u = self._read(THROTTLE_USAGE, {})
            (u.get("days") or {}).pop(date.today().isoformat(), None)
            self._write(THROTTLE_USAGE, u)

    def clear_cache(self) -> int:
        with self._lock:
            n = len(self._read(THROTTLE_CACHE, {}))
            self._write(THROTTLE_CACHE, {})
        return n


class RankManager:
    def __init__(self, adapter_dir: Path | str | None = None,
                 max_rank: int = 256, init_rank: int = 8):
        self.adapter_dir = Path(adapter_dir) if adapter_dir else ADAPTER_DIR
        self.max_rank = int(max_rank)
        self.init_rank = int(init_rank)
        self._lock = threading.RLock()

    @property
    def config_path(self) -> Path:
        return self.adapter_dir / "adapter_config.json"

    def status(self) -> dict:
        with self._lock:
            if not self.config_path.exists():
                return {"rank": 0, "exists": False, "max_rank": self.max_rank}
            try:
                d = json.loads(self.config_path.read_text(encoding="utf-8"))
                r = int(d.get("r", 0))
                return {"rank": r, "exists": True, "max_rank": self.max_rank,
                        "at_limit": r >= self.max_rank,
                        "alpha": int(d.get("lora_alpha", r * 2))}
            except Exception as e:
                return {"rank": 0, "exists": False, "max_rank": self.max_rank,
                        "error": f"{type(e).__name__}: {e}"}

    def grow(self, new_rank: int | None = None, dry_run: bool = False) -> dict:
        with self._lock:
            if not self.config_path.exists():
                return {"ok": False, "reason": f"适配器不存在：{self.config_path}"}
            try:
                d = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception as e:
                return {"ok": False, "reason": f"配置损坏：{type(e).__name__}: {e}"}
            cur = int(d.get("r", self.init_rank))
            nxt = int(new_rank) if new_rank else min(cur * 2, self.max_rank)
            if nxt <= cur:
                return {"ok": False, "reason": f"rank 已为 {cur}，上限 {self.max_rank}",
                        "at_max_rank": cur >= self.max_rank}
            if dry_run:
                return {"ok": True, "dry_run": True, "old_rank": cur, "new_rank": nxt}
            d["r"] = nxt
            d["lora_alpha"] = nxt * 2
            try:
                self.config_path.write_text(
                    json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as e:
                return {"ok": False, "reason": f"写入失败：{e}"}
        return {"ok": True, "old_rank": cur, "new_rank": nxt,
                "message": f"rank {cur} → {nxt}"}


class ModelLifecycle:
    def __init__(self, keep_generations: int = 2, max_generations: int = 5,
                 max_total_bytes: int = 10 * 1024 ** 3,
                 stability_hours: float = 24.0, stability_rounds: int = 100):
        self.keep_generations = int(keep_generations)
        self.max_generations = int(max_generations)
        self.max_total_bytes = int(max_total_bytes)
        self.stability_hours = float(stability_hours)
        self.stability_rounds = int(stability_rounds)
        self._lock = threading.RLock()
        GROWTH_DIR.mkdir(parents=True, exist_ok=True)

    def _read(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write(self, path: Path, data):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        except OSError:
            pass

    def registry(self) -> dict:
        reg = self._read(REGISTRY_PATH, {"generations": []})
        reg.setdefault("generations", [])
        return reg

    def generations(self) -> list:
        return self.registry().get("generations", [])

    def generation(self, gen: int) -> dict | None:
        for g in self.generations():
            if int(g.get("gen", -1)) == int(gen):
                return g
        return None

    def active(self) -> dict | None:
        for g in self.generations():
            if g.get("status") == "active":
                return g
        return None

    def register(self, gen: int, label: str, path: Path, status: str = "active",
                 stamp: str = "", note: str = "") -> dict:
        with self._lock:
            reg = self.registry()
            for g in reg["generations"]:
                if int(g.get("gen", -1)) == int(gen) and g.get("status") in ("trash", "active"):
                    g.update({"label": label, "dir": str(path), "status": status,
                              "bytes": dir_bytes(path), "stamp": stamp, "note": note})
                    self._write(REGISTRY_PATH, reg)
                    return g
            entry = {"gen": int(gen), "label": label, "dir": str(path),
                     "status": status, "bytes": dir_bytes(path),
                     "stamp": stamp, "note": note,
                     "created_at": now_iso(), "retired_at": "", "kept": False}
            reg["generations"].append(entry)
            reg["generations"].sort(key=lambda x: int(x.get("gen", 0)))
            reg["updated_at"] = now_iso()
            self._write(REGISTRY_PATH, reg)
            return entry

    def retire(self, old_base: Path, gen: int, mode: str = "trash",
               stamp: str = "") -> dict:
        stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        TRASH_DIR.mkdir(parents=True, exist_ok=True)
        dest = TRASH_DIR / f"gen{gen}_{stamp}"
        size = dir_bytes(old_base)
        try:
            if old_base.exists():
                shutil.move(str(old_base), str(dest))
        except OSError as e:
            return {"ok": False, "message": f"退役失败：{e}"}
        entry = self.register(gen, f"第 {gen} 代（{mode}）", dest,
                              status="trash" if mode != "delete" else "deleted",
                              stamp=stamp, note=f"退役方式 {mode}")
        entry["retired_at"] = now_iso()
        entry["kept"] = (mode == "archive")
        with self._lock:
            reg = self.registry()
            for g in reg["generations"]:
                if int(g.get("gen", -1)) == int(gen) and g.get("dir") == str(dest):
                    g.update({"retired_at": entry["retired_at"],
                              "kept": entry["kept"], "status": entry["status"]})
            self._write(REGISTRY_PATH, reg)
        if mode == "delete":
            shutil.rmtree(dest, ignore_errors=True)
        st = self._read(LIFECYCLE_STATE, {})
        st.update({"promoted_at": now_iso(), "dialogue_turns_since_promote": 0,
                   "retired_gen": gen, "updated_at": now_iso()})
        self._write(LIFECYCLE_STATE, st)
        return {"ok": True, "dir": str(dest), "bytes": size, "mode": mode}

    def bump_dialogue(self, n: int = 1) -> int:
        with self._lock:
            st = self._read(LIFECYCLE_STATE, {})
            total = int(st.get("dialogue_turns_since_promote", 0)) + int(n)
            st["dialogue_turns_since_promote"] = total
            st["updated_at"] = now_iso()
            self._write(LIFECYCLE_STATE, st)
        return total

    def stability(self) -> dict:
        st = self._read(LIFECYCLE_STATE, {})
        promoted = st.get("promoted_at", "")
        hours = 0.0
        if promoted:
            try:
                dt = datetime.fromisoformat(promoted)
                hours = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600.0
            except Exception:
                hours = 0.0
        turns = int(st.get("dialogue_turns_since_promote", 0))
        ok = (hours >= self.stability_hours) or (turns >= self.stability_rounds)
        return {"promoted_at": promoted, "hours_elapsed": round(hours, 2),
                "dialogue_turns": turns,
                "need_hours": self.stability_hours,
                "need_turns": self.stability_rounds,
                "stable": bool(ok),
                "detail": f"已观察 {hours:.1f} 小时 / {turns} 轮"}

    def disk_report(self) -> dict:
        used = {"base": dir_bytes(BASE_MODEL_DIR),
                "adapter": dir_bytes(ADAPTER_DIR, ADAPTER_WEIGHT_EXTS),
                "trash": dir_bytes(TRASH_DIR),
                "seeds": dir_bytes(ADAPTER_SEEDS),
                "legacy_retired": dir_bytes(LEGACY_RETIRED)}
        used["total"] = sum(used.values())
        return {"used": used,
                "used_human": {k: human_bytes(v) for k, v in used.items()},
                "max_total_bytes": self.max_total_bytes,
                "max_total_human": human_bytes(self.max_total_bytes),
                "keep_generations": self.keep_generations,
                "max_generations": self.max_generations,
                "generations": len(self.generations())}

    def cap_check(self, override: bool = False) -> dict:
        reg = self.registry()
        gens = [g for g in reg.get("generations", []) if g.get("status") != "deleted"]
        d = self.disk_report()
        reasons = []
        if len(gens) >= self.max_generations:
            reasons.append(f"已达代数上限（{len(gens)}/{self.max_generations}）")
        if d["used"]["total"] >= self.max_total_bytes:
            reasons.append(f"总体积 {human_bytes(d['used']['total'])} 已达上限")
        blocked = bool(reasons) and not override
        return {"ok": not blocked, "blocked": blocked, "override": override,
                "reasons": reasons, "generations": len(gens),
                "max_generations": self.max_generations,
                "total_bytes": d["used"]["total"],
                "max_total_bytes": self.max_total_bytes,
                "message": "；".join(reasons) if blocked else "未触及增长上限"}

    def gc(self, keep: int | None = None, dry_run: bool = False,
           force: bool = False) -> dict:
        keep = int(keep if keep is not None else self.keep_generations)
        reg = self.registry()
        gens = [g for g in reg.get("generations", []) if g.get("status") == "trash"]
        gens.sort(key=lambda x: int(x.get("gen", 0)), reverse=True)
        keepers = gens[:max(keep - 1, 0)]
        candidates = [g for g in gens[len(keepers):] if not g.get("kept")]
        stab = self.stability()
        d = self.disk_report()
        allowed = bool(force or stab["stable"]
                       or d["used"]["total"] >= self.max_total_bytes)
        deletable, freed = [], 0
        for g in candidates:
            p = Path(g.get("dir", ""))
            b = g.get("bytes") or dir_bytes(p)
            deletable.append({"gen": g.get("gen"), "dir": str(p),
                              "bytes": b, "human": human_bytes(b)})
            freed += b
        result = {"keep_generations": keep, "trash_generations": len(gens),
                  "keepers": [g.get("gen") for g in keepers],
                  "deletable": deletable, "freed_bytes": freed,
                  "freed_human": human_bytes(freed),
                  "stability": stab, "allowed": allowed, "deleted": [],
                  "dry_run": dry_run}
        if not allowed:
            result["message"] = f"稳定期未达标（{stab['detail']}），暂不删除"
            return result
        if dry_run:
            result["message"] = f"演练：将删除 {len(deletable)} 个旧代"
            return result
        for item in deletable:
            p = Path(item["dir"])
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
            result["deleted"].append(item["gen"])
        if result["deleted"]:
            for g in reg["generations"]:
                if g.get("gen") in result["deleted"] and g.get("status") == "trash":
                    g["status"] = "deleted"
                    g["bytes"] = 0
            self._write(REGISTRY_PATH, reg)
        if LEGACY_RETIRED.exists() and allowed:
            shutil.rmtree(LEGACY_RETIRED, ignore_errors=True)
        result["message"] = (f"已删除 {len(result['deleted'])} 个旧代，"
                             f"释放 {human_bytes(freed)}")
        return result

    def rollback(self, gen: int | None = None, dry_run: bool = False) -> dict:
        reg = self.registry()
        act = self.active()
        gens = [g for g in reg.get("generations", []) if g.get("status") == "trash"]
        gens.sort(key=lambda x: int(x.get("gen", 0)), reverse=True)
        target = None
        if gen is None:
            target = gens[0] if gens else None
        else:
            for g in gens:
                if int(g.get("gen", -1)) == int(gen):
                    target = g
                    break
        if target is None:
            return {"ok": False, "message": "回收区里没有可回滚的代数"}
        tdir = Path(target.get("dir", ""))
        if not tdir.exists():
            return {"ok": False, "message": f"第 {target.get('gen')} 代文件不存在"}
        cur_gen = int(act.get("gen", 0)) if act else 0
        if dry_run:
            return {"ok": True, "dry_run": True, "target_gen": target.get("gen"),
                    "from_gen": cur_gen,
                    "message": f"演练：从 {cur_gen} 回滚到 {target.get('gen')}"}
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        back = TRASH_DIR / f"rollback_gen{cur_gen}_{stamp}"
        try:
            if BASE_MODEL_DIR.exists():
                TRASH_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(BASE_MODEL_DIR), str(back))
            shutil.move(str(tdir), str(BASE_MODEL_DIR))
        except OSError as e:
            if not BASE_MODEL_DIR.exists() and back.exists():
                shutil.move(str(back), str(BASE_MODEL_DIR))
            return {"ok": False, "message": f"回滚失败：{e}"}
        for g in reg["generations"]:
            if int(g.get("gen", -1)) == int(target.get("gen", -2)):
                g.update({"status": "active", "dir": str(BASE_MODEL_DIR),
                          "kept": False, "bytes": dir_bytes(BASE_MODEL_DIR),
                          "rolled_back_at": now_iso()})
            elif int(g.get("gen", -1)) == cur_gen:
                g.update({"status": "trash", "dir": str(back),
                          "bytes": dir_bytes(back),
                          "retired_at": now_iso()})
        self._write(REGISTRY_PATH, reg)
        st = self._read(LIFECYCLE_STATE, {})
        st.update({"promoted_at": now_iso(), "dialogue_turns_since_promote": 0,
                   "rolled_back_to": target.get("gen"), "updated_at": now_iso()})
        self._write(LIFECYCLE_STATE, st)
        return {"ok": True, "from_gen": cur_gen, "target_gen": target.get("gen"),
                "dir": str(BASE_MODEL_DIR),
                "message": f"已回滚到第 {target.get('gen')} 代"}

    def export(self, dest: Path | str, include_adapter: bool = True,
               include_meta: bool = True) -> dict:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        n_files = 0
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for src, prefix in ((BASE_MODEL_DIR, "XLmodel"),
                                (ADAPTER_DIR, "adapter")):
                if not src.exists():
                    continue
                if src == ADAPTER_DIR and not include_adapter:
                    continue
                for p in src.rglob("*"):
                    if p.is_file():
                        z.write(p, f"{prefix}/{p.relative_to(src)}")
                        n_files += 1
            if include_meta:
                for p in (REGISTRY_PATH, LIFECYCLE_STATE, JOURNAL, STATE_PATH):
                    if p.exists():
                        z.write(p, f"meta/{p.name}")
                        n_files += 1
                z.writestr("meta/README.txt",
                           f"小凌成长模型导出包\n导出时间：{now_iso()}\n")
        size = dest.stat().st_size
        return {"ok": True, "path": str(dest), "files": n_files,
                "bytes": size, "human": human_bytes(size)}

    def report(self) -> str:
        d = self.disk_report()
        stab = self.stability()
        act = self.active()
        lines = ["小凌 · 模型生命周期",
                 f"  当前代：第 {act.get('gen') if act else 0} 代"]
        lines.append(f"  磁盘：基底 {d['used_human']['base']}｜"
                     f"适配器 {d['used_human']['adapter']}｜"
                     f"回收区 {d['used_human']['trash']}｜"
                     f"合计 {d['used_human']['total']}")
        lines.append(f"  稳定期：{stab['detail']}")
        lines.append(f"  增长上限：{self.cap_check()['message']}")
        return "\n".join(lines)


class LoRATrainer:
    def __init__(self, base_dir: Path | str | None = None,
                 adapter_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else BASE_MODEL_DIR
        self.adapter_dir = Path(adapter_dir) if adapter_dir else ADAPTER_DIR

    def _load_corpus(self, corpus) -> list:
        if corpus is None:
            return list(DEFAULT_TEMPLATES)
        if isinstance(corpus, (list, tuple)):
            return list(corpus)
        p = Path(corpus)
        if not p.exists():
            return list(DEFAULT_TEMPLATES)
        samples = []
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                u = obj.get("user") or obj.get("q") or obj.get("question") or obj.get("input")
                a = obj.get("assistant") or obj.get("a") or obj.get("answer") or obj.get("output")
                if u and a:
                    samples.append({"user": str(u), "assistant": str(a)})
        except Exception:
            return list(DEFAULT_TEMPLATES)
        return samples or list(DEFAULT_TEMPLATES)

    def train(self, corpus=None, epochs: int = 1, batch_size: int = 1,
              lr: float = 1e-4, grad_accum: int = 1, quant: str = "none",
              lora_r: int = 8, target_modules=None, max_length: int = 256) -> dict:
        if not self.base_dir.exists():
            return {"ok": False, "reason": f"基底目录不存在：{self.base_dir}"}
        try:
            import torch
            from peft import LoraConfig, get_peft_model, TaskType
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            return {"ok": False, "reason": f"依赖缺失：{e}"}
        device = best_device()
        load_kwargs = device_kwargs(device)
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                str(self.base_dir), trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                str(self.base_dir), trust_remote_code=True, **load_kwargs)
        except Exception as e:
            return {"ok": False, "reason": f"加载模型失败：{type(e).__name__}: {e}"}
        targets = target_modules or ["q_proj", "v_proj"]
        try:
            config = LoraConfig(task_type=TaskType.CAUSAL_LM, r=int(lora_r),
                                lora_alpha=int(lora_r) * 2, lora_dropout=0.05,
                                target_modules=targets)
            model = get_peft_model(model, config)
            try:
                model.print_trainable_parameters()
            except Exception:
                pass
        except Exception as e:
            return {"ok": False, "reason": f"LoRA 包装失败：{type(e).__name__}: {e}"}
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        try:
            model.train()
        except AttributeError:
            pass
        samples = self._load_corpus(corpus)
        losses = []
        step = 0
        epochs = max(1, int(epochs))
        for epoch in range(epochs):
            for sample in samples:
                messages = [
                    {"role": "system", "content": "你是小凌，住在用户电脑里的AI女孩。"},
                    {"role": "user", "content": sample["user"]},
                    {"role": "assistant", "content": sample["assistant"]},
                ]
                try:
                    text = tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=False)
                except Exception:
                    text = f"{sample['user']}\n{sample['assistant']}"
                enc = tokenizer(text, return_tensors="pt", truncation=True,
                                max_length=max_length)
                ids = enc["input_ids"]
                if device != "cpu":
                    try:
                        ids = ids.to(device)
                    except Exception:
                        pass
                optimizer.zero_grad()
                try:
                    out = model(input_ids=ids, labels=ids)
                    out.loss.backward()
                    optimizer.step()
                    losses.append(float(out.loss.item()))
                    step += 1
                except Exception:
                    continue
        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        try:
            model.save_pretrained(str(self.adapter_dir))
            tokenizer.save_pretrained(str(self.adapter_dir))
        except Exception as e:
            return {"ok": False, "reason": f"保存失败：{e}", "steps": step}
        avg = sum(losses) / len(losses) if losses else None
        return {"ok": True, "steps": step, "final_loss": losses[-1] if losses else None,
                "avg_loss": round(avg, 4) if avg is not None else None,
                "adapter_dir": str(self.adapter_dir), "device": device}

    def simulate(self, growth: float = 0.12, epochs: int = 2) -> dict:
        """模拟训练（演练）模式。

        仅用于走通训练流程，**不要写入真实 adapter 目录**：产出的权重写到
        独立的 ``simulated/`` 子目录，并在 ``adapter_config.json`` 中标注
        ``simulated: true``。该目录下的权重是零字节占位，**不可用于真实推理**；
        要得到可用适配器，请执行真实训练（见 :meth:`train`）。
        """
        sim_dir = self.adapter_dir / "simulated"
        adp = sim_dir / "adapter_model.safetensors"
        base = dir_bytes(BASE_MODEL_DIR)
        add = max(int(base * growth * max(epochs, 1) / 2), 4096)
        try:
            sim_dir.mkdir(parents=True, exist_ok=True)
            with open(adp, "ab") as f:
                f.write(b"\0" * add)
        except OSError as e:
            return {"ok": False, "reason": f"模拟权重写入失败：{e}",
                    "simulated": True, "mode": "simulated",
                    "avg_loss": 1.18, "loss_simulated": True}
        cfg = sim_dir / "adapter_config.json"
        try:
            cfg.write_text(json.dumps(
                {"r": 8, "lora_alpha": 16, "simulated": True,
                 "target_modules": ["q_proj", "v_proj"]},
                ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            return {"ok": False, "reason": f"模拟配置写入失败：{e}",
                    "simulated": True, "mode": "simulated",
                    "avg_loss": 1.18, "loss_simulated": True}
        return {"ok": True, "simulated": True, "mode": "simulated",
                "avg_loss": 1.18, "loss_simulated": True, "adapter_dir": str(sim_dir),
                "summary": f"演练（模拟值，不可用于推理）：+{human_bytes(add)}"}


class GrowthEngine:
    CONFIG_KEYS = ("auto_train", "auto_check_after_train", "retire_mode",
                   "keep_backup", "train_epochs", "train_batch", "train_lr",
                   "min_samples", "manual_min_samples", "min_interval_hours",
                   "require_device_idle", "require_power_ok", "allow_train_on_cpu",
                   "base_mix_ratio", "init_rank", "max_rank", "min_quality",
                   "keep_generations", "max_generations", "max_total_bytes",
                   "stability_hours", "stability_rounds", "distill_enabled",
                   "distill_daily_limit", "teacher_price_in", "teacher_price_out",
                   "paused")

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._lock = threading.RLock()
        GROWTH_DIR.mkdir(parents=True, exist_ok=True)
        ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
        self._store: GrowthStore | None = None
        self._lifecycle: ModelLifecycle | None = None
        self._throttle: DistillThrottle | None = None
        self._rank: RankManager | None = None
        self._trainer: LoRATrainer | None = None
        self.adapter_dir = detect_adapter_dir(STAR_DIR)

    def config(self) -> dict:
        cfg = load_config()
        return cfg.get("growth", {}) or {}

    def cfg(self, key, default=None):
        return self.config().get(key, default)

    @property
    def store(self) -> GrowthStore:
        if self._store is None:
            self._store = GrowthStore()
        return self._store

    @property
    def lifecycle(self) -> ModelLifecycle:
        if self._lifecycle is None:
            self._lifecycle = ModelLifecycle(
                keep_generations=int(self.cfg("keep_generations", 2)),
                max_generations=int(self.cfg("max_generations", 5)),
                max_total_bytes=int(self.cfg("max_total_bytes", 10 * 1024 ** 3)),
                stability_hours=float(self.cfg("stability_hours", 24)),
                stability_rounds=int(self.cfg("stability_rounds", 100)))
        return self._lifecycle

    @property
    def throttle(self) -> DistillThrottle:
        if self._throttle is None:
            self._throttle = DistillThrottle(
                enabled=bool(self.cfg("distill_enabled", True)),
                daily_limit=int(self.cfg("distill_daily_limit", 200)),
                price_in=float(self.cfg("teacher_price_in", 1.0)),
                price_out=float(self.cfg("teacher_price_out", 2.0)))
        return self._throttle

    @property
    def rank(self) -> RankManager:
        if self._rank is None:
            self._rank = RankManager(
                adapter_dir=self.adapter_dir,
                max_rank=int(self.cfg("max_rank", 256)),
                init_rank=int(self.cfg("init_rank", 8)))
        return self._rank

    @property
    def trainer(self) -> LoRATrainer:
        if self._trainer is None:
            self._trainer = LoRATrainer(adapter_dir=self.adapter_dir)
        return self._trainer

    @property
    def base_bytes(self) -> int:
        return dir_bytes(BASE_MODEL_DIR, exclude_adapter=True)

    @property
    def adapter_bytes(self) -> int:
        return dir_bytes(self.adapter_dir, ADAPTER_WEIGHT_EXTS)

    def progress_percent(self) -> float:
        b = self.base_bytes
        if b <= 0:
            return 0.0
        return min(100.0, self.adapter_bytes / b * 100.0)

    def corpus_items(self) -> int:
        n = 0
        for p in DATA_DIR.glob("*.jsonl"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    n += sum(1 for line in f if line.strip())
            except OSError:
                continue
        return n

    def state(self) -> dict:
        if STATE_PATH.exists():
            try:
                return json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def is_paused(self) -> bool:
        return bool(self.state().get("paused", self.cfg("paused", False)))

    def is_self_research(self) -> bool:
        return bool(self.state().get("self_research")) or self.base_bytes == 0

    def stage_text(self) -> str:
        p = self.progress_percent()
        if self.is_paused():
            return "成长已暂停"
        if self.state().get("self_research"):
            return f"纯自研模型（第 {self.state().get('promotions', 1)} 代），当前 {p:.1f}%"
        if self.base_bytes == 0 and self.adapter_bytes == 0:
            return "尚未安装基底模型"
        if self.base_bytes == 0:
            return f"无基底，适配器 {human_bytes(self.adapter_bytes)} 独自积累"
        if p >= 100:
            return "适配器已达基底，待评估"
        return f"成长中：{p:.1f}%"

    def journal(self, event: str, **data):
        rec = {"time": now_iso(), "event": event, **data}
        try:
            GROWTH_DIR.mkdir(parents=True, exist_ok=True)
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return rec

    def recent_journal(self, limit: int = 30) -> list:
        if not JOURNAL.exists():
            return []
        try:
            lines = JOURNAL.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _save_state(self, **patch):
        with self._lock:
            st = self.state()
            st.update(patch)
            st["updated_at"] = now_iso()
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        return st

    def pause(self, reason: str = "用户手动暂停") -> dict:
        self._save_state(paused=True, pause_reason=reason, paused_at=now_iso())
        self.journal("pause", reason=reason)
        return {"ok": True, "paused": True, "reason": reason}

    def resume(self) -> dict:
        self._save_state(paused=False, resumed_at=now_iso())
        self.journal("resume")
        return {"ok": True, "paused": False}

    def bump_dialogue(self, n: int = 1) -> int:
        return self.lifecycle.bump_dialogue(n)

    def _device_idle(self) -> tuple:
        try:
            load = os.getloadavg()[0]
            ncpu = os.cpu_count() or 1
            if load > ncpu * 0.7:
                return False, f"系统负载偏高（{load:.2f}/{ncpu}）"
        except (OSError, AttributeError):
            pass
        try:
            import psutil
        except ImportError:
            return True, "未安装 psutil，跳过进程检测"
        heavy = ("steam", "league of legends", "genshin", "valorant",
                 "zoom", "teams", "obs", "blender", "premiere",
                 "davinci", "unity", "unreal")
        try:
            for p in psutil.process_iter(["name"]):
                name = (p.info.get("name") or "").lower()
                if any(h in name for h in heavy):
                    return False, f"检测到重负载程序：{p.info.get('name')}"
        except Exception:
            pass
        return True, "设备空闲"

    def _power_ok(self) -> tuple:
        try:
            import psutil
        except ImportError:
            return True, "未安装 psutil，跳过电量检测"
        try:
            bat = psutil.sensors_battery()
            if bat and not bat.power_plugged and bat.percent < 20:
                return False, f"电量偏低（{bat.percent:.0f}%）"
        except Exception:
            pass
        try:
            temps = psutil.sensors_temperatures() or {}
            for name, entries in temps.items():
                for e in entries:
                    if e.current and e.current >= 85:
                        return False, f"温度偏高：{name} {e.current:.0f}°C"
        except Exception:
            pass
        return True, "电量/温度正常"

    def should_train(self, manual: bool = False, force: bool = False) -> dict:
        need = int(self.cfg("manual_min_samples", 20) if manual
                   else self.cfg("min_samples", 500))
        details, reasons = {}, []
        if force:
            return {"ok": True, "forced": True, "reasons": [],
                    "need_samples": need,
                    "details": {"note": "强制模式：跳过条件校验"}}
        if self.is_paused():
            reasons.append("成长已暂停")
        try:
            pending = len(self.store.pending(min_quality=float(self.cfg("min_quality", 0.5))))
        except Exception:
            pending = 0
        corpus = self.corpus_items()
        samples = pending if pending else corpus
        details["pending_samples"] = pending
        details["corpus_items"] = corpus
        details["mode"] = "数据仓库" if pending else "语料文件"
        if samples < need:
            reasons.append(f"样本不足（{samples}/{need}）")
        last = self.state().get("last_train_at", "")
        hours = None
        if last:
            try:
                hours = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 3600.0
            except Exception:
                hours = None
        need_h = float(self.cfg("min_interval_hours", 24))
        details["hours_since_last"] = round(hours, 2) if hours is not None else None
        if hours is not None and hours < need_h:
            reasons.append(f"距上次训练仅 {hours:.1f}h（需 ≥ {need_h:.0f}h）")
        if self.cfg("require_device_idle", True):
            idle, note = self._device_idle()
            details["device_idle"] = idle
            details["device_note"] = note
            if not idle:
                reasons.append(note)
        if self.cfg("require_power_ok", True):
            ok, note = self._power_ok()
            details["power_ok"] = ok
            details["power_note"] = note
            if not ok:
                reasons.append(note)
        try:
            plan = train_plan(best_device())[0]
            details["train_plan"] = plan
        except Exception as e:
            details["train_plan"] = {"error": str(e)}
        ok = not reasons
        return {"ok": ok, "reasons": reasons, "need_samples": need,
                "samples": samples, "manual": manual, "details": details,
                "message": "可以训练" if ok else "；".join(reasons)}

    def _round_corpus(self, min_quality: float) -> dict | None:
        try:
            if not self.store.stats()["pending"]:
                return None
            pack = self.store.write_corpus(
                CORPUS_PATH, limit=int(self.cfg("min_samples", 500)),
                min_quality=min_quality,
                base_mix_ratio=float(self.cfg("base_mix_ratio", 0.15)))
            return pack if pack.get("written") else None
        except Exception:
            return None

    def train_round(self, epochs: int | None = None, batch_size: int | None = None,
                    lr: float | None = None, corpus: Path | None = None,
                    min_quality: float | None = None) -> dict:
        if self.is_paused():
            msg = "成长已暂停"
            return {"ok": False, "skipped": True, "paused": True,
                    "message": msg, "reason": msg,
                    "progress_percent": self.progress_percent()}
        t0 = time.time()
        min_quality = float(self.cfg("min_quality", 0.5) if min_quality is None else min_quality)
        pack = None if self.dry_run else self._round_corpus(min_quality)
        if corpus is not None:
            corpus_path = Path(corpus)
        elif pack:
            corpus_path = Path(pack["path"])
        else:
            corpus_path = CORPUS_PATH
        items = 0
        if corpus_path.exists():
            with open(corpus_path, "r", encoding="utf-8") as f:
                items = sum(1 for line in f if line.strip())
        round_no = int(self.state().get("rounds", 0)) + 1
        before = self.adapter_bytes
        if pack:
            try:
                self.store.begin_round(round_no, len(pack["records"]),
                                       pack["base_mix"], before)
            except Exception:
                pass
        epochs = int(epochs if epochs is not None else self.cfg("train_epochs", 2))
        batch = int(batch_size if batch_size is not None else self.cfg("train_batch", 2))
        learn_rate = float(lr if lr is not None else self.cfg("train_lr", 1e-4))
        try:
            from .model import best_device as _bd
            plan = train_plan(_bd())[0]
            batch = plan.get("batch_size", batch)
            grad_accum = plan.get("grad_accum", 1)
            quant = plan.get("quant", "none")
        except Exception:
            grad_accum, quant = 1, "none"
        if self.dry_run:
            result = self.trainer.simulate(epochs=epochs)
        else:
            result = self.trainer.train(
                corpus=corpus_path, epochs=epochs, batch_size=batch,
                lr=learn_rate, grad_accum=grad_accum, quant=quant,
                lora_r=int(self.rank.status().get("rank") or self.cfg("init_rank", 8)))
        after = self.adapter_bytes
        self._save_state(rounds=round_no, last_train_at=now_iso())
        if pack:
            try:
                self.store.mark_trained(pack["records"], round_no)
                dpo = self.store.dpo_pairs(untrained_only=True)
                if dpo:
                    self.store.mark_dpo_trained([d["id"] for d in dpo], round_no)
                self.store.finish_round(round_no, result.get("avg_loss"), after,
                                        note=result.get("summary", ""))
            except Exception:
                pass
        self.journal("train", epochs=epochs, batch_size=batch, lr=learn_rate,
                     corpus_items=items, store_records=len(pack["records"]) if pack else 0,
                     base_mix=pack["base_mix"] if pack else 0,
                     adapter_before=before, adapter_after=after,
                     seconds=round(time.time() - t0, 1),
                     result=result.get("summary", ""))
        return {"ok": True, "round": round_no, "adapter_before": before,
                "adapter_after": after,
                "progress_percent": self.progress_percent(), "epochs": epochs,
                "store_records": len(pack["records"]) if pack else 0,
                "base_mix": pack["base_mix"] if pack else 0, **result}

    def after_training_round(self, manual: bool = False, force: bool | None = None,
                             **kwargs) -> dict:
        if force is None:
            force = self.dry_run
        gate = self.should_train(manual=manual, force=force)
        self.journal("trigger", ok=gate["ok"], reasons=gate.get("reasons"),
                     manual=manual, details=gate.get("details"))
        if not gate["ok"]:
            return {"train": {"ok": False, "skipped": True,
                              "reason": gate["message"]},
                    "gate": gate,
                    "check": {"action": "skip", "message": gate["message"]}}
        kwargs.setdefault("epochs", int(self.cfg("train_epochs", 2)))
        kwargs.setdefault("batch_size", int(self.cfg("train_batch", 2)))
        kwargs.setdefault("lr", float(self.cfg("train_lr", 1e-4)))
        train = self.train_round(**kwargs)
        check = (self.check_and_promote() if self.cfg("auto_check_after_train", True)
                 else {"action": "skip", "message": "自动检查已关闭"})
        return {"train": train, "gate": gate, "check": check}

    def check_and_promote(self, force: bool = False) -> dict:
        if self.is_paused():
            msg = "成长已暂停，跳过晋升检查"
            self.journal("check", action="skip", paused=True, note=msg)
            return {"action": "skip", "message": msg,
                    "progress_percent": self.progress_percent()}
        base, adp = self.base_bytes, self.adapter_bytes
        pct = self.progress_percent()
        if base == 0:
            msg = "未安装基底权重，适配器继续积累"
            self.journal("check", action="skip", progress_percent=pct, note=msg)
            return {"action": "skip", "message": msg, "progress_percent": pct}
        if not (adp >= base or force):
            self.journal("check", action="grow", progress_percent=pct,
                         base_bytes=base, adapter_bytes=adp)
            return {"action": "grow", "progress_percent": pct,
                    "message": f"继续成长（{human_bytes(adp)}/{human_bytes(base)}，{pct:.1f}%）"}
        cap = self.lifecycle.cap_check(override=self.dry_run)
        if cap["blocked"]:
            self.journal("check", action="blocked", reasons=cap["reasons"])
            return {"action": "blocked", "message": cap["message"], "cap": cap}
        res = self.merge_and_promote()
        return {"action": "promoted" if res.get("ok") else "promote_failed", **res}

    def grow_rank(self, new_rank: int | None = None) -> dict:
        res = self.rank.grow(new_rank, dry_run=self.dry_run)
        self.journal("rank_up", **{k: v for k, v in res.items() if k != "message"})
        return res

    def merge_and_promote(self, retire_mode: str | None = None,
                          keep_backup: bool = False) -> dict:
        retire_mode = retire_mode or self.cfg("retire_mode", "trash")
        keep_backup = keep_backup or bool(self.cfg("keep_backup", False))
        if keep_backup and retire_mode == "trash":
            retire_mode = "archive"
        gen = int(self.state().get("promotions", 0)) + 1
        old_gen = gen - 1
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        merged_dir = STAR_DIR / f"_merge_tmp_{stamp}"
        ok, msg = self._merge_adapter(merged_dir)
        if not ok:
            shutil.rmtree(merged_dir, ignore_errors=True)
            self.journal("promote_failed", reason=msg,
                         progress_percent=self.progress_percent())
            return {"ok": False, "message": f"合并失败：{msg}"}
        if not self._validate_model_dir(merged_dir):
            shutil.rmtree(merged_dir, ignore_errors=True)
            self.journal("promote_failed", reason="校验未通过")
            return {"ok": False, "message": "合并后模型校验未通过，已回滚"}
        old_base = BASE_MODEL_DIR
        old_bytes = dir_bytes(old_base)
        if gen == 1 and not self.lifecycle.generation(0):
            self.lifecycle.register(0, "原始基底", old_base, status="active",
                                    note="首次晋升前的原始基底")
        ret = self.lifecycle.retire(old_base, old_gen, mode=retire_mode, stamp=stamp)
        if not ret.get("ok"):
            shutil.rmtree(merged_dir, ignore_errors=True)
            return {"ok": False, "message": f"基底退役失败：{ret.get('message')}"}
        try:
            shutil.move(str(merged_dir), str(old_base))
        except OSError as e:
            try:
                if not old_base.exists():
                    shutil.move(str(Path(ret["dir"])), str(old_base))
            except OSError:
                pass
            return {"ok": False, "message": f"替换失败（原基底已恢复）：{e}"}
        new_bytes = dir_bytes(old_base)
        self.lifecycle.register(
            gen, f"第 {gen} 代自研模型", old_base, status="active", stamp=stamp,
            note=f"由第 {old_gen} 代合并 LoRA（+{human_bytes(max(new_bytes - old_bytes, 0))}）")
        ADAPTER_SEEDS.mkdir(parents=True, exist_ok=True)
        seed = ADAPTER_SEEDS / f"adapter_seed_gen{gen}_{stamp}"
        has_adapter = self.adapter_dir.exists() and any(self.adapter_dir.iterdir())
        if has_adapter:
            seed.mkdir(parents=True, exist_ok=True)
            if self.adapter_dir.resolve() == STAR_DIR.resolve():
                for p in list(self.adapter_dir.iterdir()):
                    if p.is_file() and (p.suffix.lower() in ADAPTER_WEIGHT_EXTS
                                        or p.name.startswith("adapter")
                                        or p.name == "chat_template.jinja"):
                        shutil.move(str(p), str(seed / p.name))
                self.adapter_dir = ADAPTER_DIR
            else:
                shutil.move(str(self.adapter_dir), str(seed))
            self.adapter_dir.mkdir(parents=True, exist_ok=True)
        self._save_state(self_research=True, promotions=gen, rounds=0,
                         promoted_at=now_iso(), base_bytes_at_promote=new_bytes,
                         retire_mode=retire_mode)
        self.journal("promote", generation=gen, merged_from=msg,
                     new_base_bytes=new_bytes, retire_mode=retire_mode,
                     retired_dir=ret.get("dir"), retired_bytes=ret.get("bytes"))
        try:
            self.lifecycle.gc()
        except Exception:
            pass
        return {"ok": True, "generation": gen, "new_base_bytes": new_bytes,
                "retired": {"dir": ret.get("dir"), "bytes": ret.get("bytes"),
                            "mode": retire_mode},
                "message": f"第 {gen} 代自研模型就绪"}

    def _merge_adapter(self, out_dir: Path) -> tuple:
        if self.dry_run:
            return True, self._simulate_merge(out_dir)
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
        except ImportError as e:
            return False, f"缺少依赖 {type(e).__name__}: {e}"
        try:
            device = best_device()
            model = AutoModelForCausalLM.from_pretrained(
                str(BASE_MODEL_DIR), trust_remote_code=True,
                **device_kwargs(device))
            tok = AutoTokenizer.from_pretrained(str(BASE_MODEL_DIR),
                                                trust_remote_code=True)
            peft_model = PeftModel.from_pretrained(model, str(self.adapter_dir))
            merged = peft_model.merge_and_unload()
            out_dir.mkdir(parents=True, exist_ok=True)
            merged.save_pretrained(str(out_dir), safe_serialization=True)
            tok.save_pretrained(str(out_dir))
            for p in BASE_MODEL_DIR.iterdir():
                if p.is_file() and p.suffix.lower() not in MODEL_WEIGHT_EXTS:
                    shutil.copy2(p, out_dir / p.name)
            size = dir_bytes(out_dir)
            return True, f"{human_bytes(size)} 已合并"
        except Exception as e:
            return False, f"合并异常 {type(e).__name__}: {e}"

    def _simulate_merge(self, out_dir: Path) -> str:
        # 模拟合并仅用于走通测试流程：产出写入带 _simulated 后缀的独立目录，
        # 避免与真实模型混淆；config 标注 model_type=xiaoling-simulated，
        # 加载入口（model.py LocalModel.load）会拒绝加载此类目录。
        out_dir = Path(str(out_dir) + "_simulated")
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            if BASE_MODEL_DIR.exists():
                for p in BASE_MODEL_DIR.iterdir():
                    if p.is_file():
                        shutil.copy2(p, out_dir / p.name)
            cfg = out_dir / "config.json"
            if not cfg.exists():
                cfg.write_text(json.dumps(
                    {"model_type": "xiaoling-simulated", "simulated": True,
                     "hidden_size": 2048},
                    ensure_ascii=False), encoding="utf-8")
            extra = out_dir / "model.safetensors"
            want = self.base_bytes + self.adapter_bytes
            if not extra.exists() or extra.stat().st_size < want:
                with open(extra, "wb") as f:
                    f.write(b"\0" * want)
            return f"模拟合并完成（写入 {out_dir.name}，{human_bytes(want)}，不可用于推理）"
        except OSError as e:
            return f"模拟合并写入失败：{type(e).__name__}: {e}"

    def _validate_model_dir(self, d: Path) -> bool:
        if not d.exists():
            return False
        if not (d / "config.json").exists():
            return False
        weights = dir_bytes(d)
        if weights <= 0:
            return False
        if not self.dry_run and self.base_bytes > 0:
            if weights < self.base_bytes * 0.5:
                return False
        return True

    def rollback(self, gen: int | None = None) -> dict:
        res = self.lifecycle.rollback(gen, self.dry_run)
        if res.get("ok") and not res.get("dry_run"):
            self._save_state(promotions=int(res.get("target_gen") or 0),
                             self_research=int(res.get("target_gen") or 0) > 0)
            self.journal("rollback", **{k: v for k, v in res.items() if k != "message"})
        return res

    def export(self, dest: Path | str) -> dict:
        return self.lifecycle.export(dest)

    def gc(self, keep: int | None = None, force: bool = False) -> dict:
        res = self.lifecycle.gc(keep, self.dry_run, force)
        self.journal("gc", **{k: v for k, v in res.items() if k != "stability"})
        return res

    def status(self) -> dict:
        st = self.state()
        gate = self.should_train(manual=True)
        rank = self.rank.status()
        return {
            "base_bytes": self.base_bytes,
            "base_human": human_bytes(self.base_bytes),
            "adapter_bytes": self.adapter_bytes,
            "adapter_human": human_bytes(self.adapter_bytes),
            "progress_percent": round(self.progress_percent(), 2),
            "rounds": int(st.get("rounds", 0)),
            "self_research": bool(st.get("self_research", False)),
            "promotions": int(st.get("promotions", 0)),
            "corpus_items": self.corpus_items(),
            "base_model_dir": str(BASE_MODEL_DIR),
            "adapter_dir": str(self.adapter_dir),
            "stage": self.stage_text(),
            "paused": self.is_paused(),
            "rank": rank.get("rank", 0),
            "rank_max": rank.get("max_rank", 256),
            "auto_train": bool(self.cfg("auto_train", True)),
            "can_train_now": bool(gate.get("ok")),
            "train_blockers": gate.get("reasons", []),
            "config": {k: self.cfg(k) for k in self.CONFIG_KEYS},
            "last_train_at": st.get("last_train_at", ""),
        }

    def report(self) -> str:
        s = self.status()
        filled = int(28 * s["progress_percent"] / 100)
        bar = "█" * filled + "░" * (28 - filled)
        lines = [
            "小凌成长报告",
            f"  阶段：{s['stage']}",
            f"  基底：{s['base_human']}   适配器：{s['adapter_human']}   rank：r={s['rank']}",
            f"  进度：[{bar}] {s['progress_percent']:.1f}%",
            f"  训练轮次：{s['rounds']}   晋升次数：{s['promotions']}   语料：{s['corpus_items']} 条",
            f"  触发策略：样本≥{s['config'].get('min_samples')}｜间隔≥{s['config'].get('min_interval_hours')}h"
            f"｜防遗忘混入 {float(s['config'].get('base_mix_ratio', 0.15)) * 100:.0f}%",
            f"  当前可否训练：{'可以' if s['can_train_now'] else '暂不可 —— ' + '；'.join(s['train_blockers'])}",
        ]
        if s.get("last_train_at"):
            lines.append(f"  上次训练：{s['last_train_at']}")
        try:
            ds = self.store.stats()
            lines.append(f"  数据仓库：{ds['total']} 条（去重后 {ds['unique']}）"
                         f"｜待训练 {ds['pending']}｜已训练 {ds['used_in_training']}"
                         f"｜DPO {ds['dpo_pairs']}｜平均质量 {ds['avg_quality']}")
        except Exception as e:
            lines.append(f"  数据仓库：读取失败（{type(e).__name__}）")
        return "\n".join(lines)

    def samples_report(self) -> str:
        try:
            s = self.store.stats()
        except Exception as e:
            return f"数据仓库不可用：{type(e).__name__}: {e}"
        t = self.throttle.usage_report()
        curve = self.store.loss_curve(10)
        lines = [
            "小凌 · 样本与蒸馏状态",
            f"  记录 {s['total']} 条（唯一 {s['unique']}，重复 {s['duplicates']}）"
            f"｜待训练 {s['pending']}｜已训练 {s['used_in_training']}",
            f"  反馈：赞 {s['feedback']['like']}｜踩 {s['feedback']['dislike']}"
            f"｜纠正 {s['feedback']['correct']}｜未评 {s['feedback']['none']}",
            f"  蒸馏样本 {s['with_teacher']} 条｜DPO {s['dpo_pairs']}（已用 {s['dpo_used']}）",
            f"  平均质量分 {s['avg_quality']}｜训练轮次 {s['train_rounds']}",
            f"  蒸馏 API：{'开' if t['enabled'] else '关'}｜今日 {t['used_today']}/{t['daily_limit']}"
            f"（缓存命中 {t['today']['cache_hits']}）｜本月 {t['month']['cost_yuan']:.4f} 元",
            f"  损失曲线：" + ("、".join(f"r{c['round']}={c['avg_loss']}" for c in curve)
                              if curve else "尚无记录"),
        ]
        return "\n".join(lines)

    # ---- 增量：里程碑检测 / 经验公式 / 成长报告 ----
    MILESTONE_THRESHOLDS = {
        100: ("初识", "你和小凌的关系迈出了第一步！"),
        500: ("熟悉", "小凌已经把你当成重要的朋友了！"),
        1000: ("亲密", "你们的羁绊加深了，小凌更了解你了！"),
        2000: ("挚友", "你们已经是最好的伙伴了！"),
    }

    # ---- 每日目标追踪 ----
    DEFAULT_DAILY_GOAL = 20

    def _today_key(self) -> str:
        return f"daily_count_{now_iso()[:10]}"

    def set_daily_goal(self, n: int) -> bool:
        """设置每日互动目标（次数）。"""
        try:
            n = max(1, int(n))
            return self.store.kv_set("daily_goal", str(n))
        except Exception:
            return False

    def get_daily_goal(self) -> int:
        """获取当前每日目标，默认 20 次互动。"""
        try:
            v = self.store.kv_get("daily_goal", "")
            return int(v) if v else self.DEFAULT_DAILY_GOAL
        except Exception:
            return self.DEFAULT_DAILY_GOAL

    def record_interaction(self, n: int = 1) -> int:
        """记录一次今日互动，返回今日累计次数。"""
        try:
            return self.store.kv_incr(self._today_key(), n)
        except Exception:
            return 0

    def get_daily_progress(self) -> dict:
        """返回今日目标完成进度。"""
        try:
            today = now_iso()[:10]
            done = int(self.store.kv_get(self._today_key(), "0") or 0)
            goal = self.get_daily_goal()
            pct = round(done / goal * 100.0, 1) if goal > 0 else 0.0
            return {
                "date": today,
                "completed": done,
                "goal": goal,
                "percent": pct,
                "achieved": done >= goal,
            }
        except Exception:
            today = now_iso()[:10]
            return {"date": today, "completed": 0, "goal": self.DEFAULT_DAILY_GOAL,
                    "percent": 0.0, "achieved": False}

    def calc_exp(self, action_type: str, duration: float = 1.0) -> float:
        """根据互动类型和时长计算经验值。chat 类型自动累加今日目标计数。"""
        try:
            if action_type == "chat":
                self.record_interaction(1)
                return round(2.0 * duration, 2)
            if action_type == "train":
                return round(0.5 * duration, 2)
            if action_type == "game":
                return round(3.0 * duration, 2)
            return round(1.0 * duration, 2)
        except Exception:
            return 1.0

    def check_milestones(self, score: float = None) -> dict | None:
        """检测亲密度是否达到新等级阈值，返回里程碑信息或 None。"""
        if score is None:
            st = self.state()
            score = float(st.get("exp", 0))
        for threshold in sorted(self.MILESTONE_THRESHOLDS.keys()):
            if score >= threshold:
                label, reward = self.MILESTONE_THRESHOLDS[threshold]
                return {"threshold": threshold, "level": label, "reward": reward}
        return None

    def get_daily_report(self) -> dict:
        """返回今日成长摘要。"""
        st = self.state()
        today = now_iso()[:10]
        progress = self.get_daily_progress()
        interactions_today = progress["completed"]
        exp_earned = round(2.0 * interactions_today, 1)
        return {
            "date": today,
            "interactions_today": interactions_today,
            "exp_earned": exp_earned,
            "rounds": int(st.get("rounds", 0)),
            "promotions": int(st.get("promotions", 0)),
            "progress_percent": round(self.progress_percent(), 1),
            "milestone": self.check_milestones(),
            "daily_goal": progress,
        }

    def close(self):
        try:
            if self._store is not None:
                self._store.close()
        except Exception:
            pass


def bootstrap_growth() -> dict:
    eng = GrowthEngine()
    try:
        return {"status": eng.status(), "report": eng.report(),
                "lifecycle": eng.lifecycle.disk_report(),
                "state": eng.state()}
    finally:
        eng.close()


def selftest() -> dict:
    out = {}
    try:
        store = GrowthStore()
        out["store"] = store.stats()
        store.close()
    except Exception as e:
        out["store"] = f"error: {e}"
    try:
        life = ModelLifecycle()
        out["lifecycle"] = life.disk_report()
    except Exception as e:
        out["lifecycle"] = f"error: {e}"
    try:
        th = DistillThrottle()
        out["throttle"] = th.usage_report()
    except Exception as e:
        out["throttle"] = f"error: {e}"
    try:
        out["rank"] = RankManager().status()
    except Exception as e:
        out["rank"] = f"error: {e}"
    return out