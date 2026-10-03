#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.lifecycle —— 模型生命周期（退役 / trash / 稳定期 / 保留代数 / 回滚 / 导出）
====================================================================================

对应设计文档 1.4 节与第四章「有自有模型后基底自动删除」：

    原则 2：删除改为退役，不可逆操作必须留后路
        · 基底不直接删，先移入 trash/，标记 retired
        · 新模型稳定运行 24 小时 / 100 轮对话后，才真删
        · 任何一代都可回滚

    4.2 磁盘策略
        · 最多保留 2 代（当前自有模型 + 上一代基底），更老的自动清理
        · 用户可设置"保留代数"
        · 删除前二次确认，并显示将释放的空间

    7.6 无限增长防护
        · 最多晋升 5 代，或总体积超过 10GB 停止
        · 用户可手动解除限制

目录约定（在既有布局上扩展，不破坏老版本数据）：

    .star_core/XLmodel/            当前基底（原始基底，或上一代自研模型）
    .star_core/adapter/            当前 LoRA
    .star_core/trash/gen<N>_<stamp>/   退役待删（旧版本用的是 base_retired/，本模块兼容读取）
    .star_core/adapter_seeds/      晋升时归档的适配器种子
    .star_core/growth/generations.json 代数登记表
    .star_core/growth/lifecycle.json   生命周期状态（对话轮次、稳定期）

用法：
    python3 -m core.lifecycle status
    python3 -m core.lifecycle generations
    python3 -m core.lifecycle gc --keep 2 --dry-run
    python3 -m core.lifecycle rollback                 # 回滚到上一代
    python3 -m core.lifecycle rollback --gen 1
    python3 -m core.lifecycle export backups/xiaoling-model.zip
    python3 -m core.lifecycle cap-check
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

from core.paths import APP_DIR

WEIGHT_EXT = ('.safetensors', '.bin', '.gguf', '.pt', '.pth')
DEFAULT_KEEP_GENERATIONS = 2          # 文档 4.2：当前 + 上一代
DEFAULT_MAX_GENERATIONS = 5           # 文档 7.6
DEFAULT_MAX_BYTES = 10 * 1024 ** 3    # 文档 7.6：10GB
DEFAULT_STABILITY_HOURS = 24          # 文档 4.1
DEFAULT_STABILITY_ROUNDS = 100        # 文档 4.1


def human(n: float) -> str:
    for unit, div in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= div:
            return f'{n / div:.2f} {unit}'
    return f'{int(n)} B'


def dir_bytes(d: Path, exts=WEIGHT_EXT) -> int:
    if not d or not d.exists():
        return 0
    total = 0
    for p in d.rglob('*'):
        try:
            if p.is_file() and (not exts or p.suffix.lower() in exts):
                total += p.stat().st_size
        except OSError:
            pass
    return total


class ModelLifecycle:
    """代数登记 + 退役 + 稳定期 + 垃圾回收 + 回滚 + 导出。"""

    def __init__(self, root: Path | str | None = None, log=print,
                 keep_generations: int | None = None, max_generations: int | None = None,
                 max_total_bytes: int | None = None,
                 stability_hours: float | None = None, stability_rounds: int | None = None):
        self.app_dir = Path(root) if root else APP_DIR
        self.star = self.app_dir / '.star_core'
        self.growth_dir = self.star / 'growth'
        self.growth_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = self.star / 'XLmodel'
        self.adapter_dir = self.star / 'adapter'
        self.trash_dir = self.star / 'trash'
        self.legacy_retired = self.star / 'base_retired'
        self.seeds_dir = self.star / 'adapter_seeds'
        self.reg_path = self.growth_dir / 'generations.json'
        self.state_path = self.growth_dir / 'lifecycle.json'
        self.log = log or (lambda *a, **k: None)
        self.keep_generations = int(keep_generations or DEFAULT_KEEP_GENERATIONS)
        self.max_generations = int(max_generations or DEFAULT_MAX_GENERATIONS)
        self.max_total_bytes = int(max_total_bytes or DEFAULT_MAX_BYTES)
        self.stability_hours = float(DEFAULT_STABILITY_HOURS if stability_hours is None else stability_hours)
        self.stability_rounds = int(DEFAULT_STABILITY_ROUNDS if stability_rounds is None else stability_rounds)

    # --------------------------------------------------------------- 登记表
    def registry(self) -> dict:
        if self.reg_path.exists():
            try:
                data = json.loads(self.reg_path.read_text(encoding='utf-8'))
                data.setdefault('generations', [])
                return data
            except Exception:                                        # noqa: BLE001
                pass
        return {'generations': [], 'updated_at': ''}

    def _save_registry(self, reg: dict):
        reg['updated_at'] = datetime.now().isoformat(timespec='seconds')
        self.reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding='utf-8')

    def state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding='utf-8'))
            except Exception:                                        # noqa: BLE001
                pass
        return {}

    def _save_state(self, **patch):
        st = self.state()
        st.update(patch)
        st['updated_at'] = datetime.now().isoformat(timespec='seconds')
        self.state_path.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
        return st

    def generations(self) -> list:
        return self.registry().get('generations', [])

    def generation(self, gen: int) -> dict | None:
        for g in self.generations():
            if int(g.get('gen', -1)) == int(gen):
                return g
        return None

    def active(self) -> dict | None:
        for g in self.generations():
            if g.get('status') == 'active':
                return g
        return None

    def register(self, gen: int, label: str, path: Path, status: str = 'active',
                 stamp: str = '', note: str = '') -> dict:
        reg = self.registry()
        for g in reg['generations']:
            if int(g.get('gen', -1)) == int(gen) and g.get('status') in ('trash', 'active'):
                g.update({'label': label, 'dir': str(path), 'status': status,
                          'bytes': dir_bytes(path), 'stamp': stamp, 'note': note})
                self._save_registry(reg)
                return g
        entry = {'gen': int(gen), 'label': label, 'dir': str(path), 'status': status,
                 'bytes': dir_bytes(path), 'stamp': stamp, 'note': note,
                 'created_at': datetime.now().isoformat(timespec='seconds'),
                 'retired_at': '', 'kept': False}
        reg['generations'].append(entry)
        reg['generations'].sort(key=lambda g: int(g.get('gen', 0)))
        self._save_registry(reg)
        return entry

    # --------------------------------------------------------- 退役（trash）
    def retire(self, old_base: Path, gen: int, mode: str = 'trash', stamp: str = '') -> dict:
        """把旧基底移入 trash/（文档原则 2）。

        mode:
            trash    默认 —— 移入 trash/，标记 retired，等稳定期过后由 gc() 真删
            delete   移入 trash/ 后立即删除（旧版本默认行为，供老配置兼容）
            archive  移入 trash/ 并标记 kept（永久保留，用户手动管理）
        """
        stamp = stamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        dest = self.trash_dir / f'gen{gen}_{stamp}'
        size = dir_bytes(old_base)
        moved = False
        try:
            if old_base.exists():
                shutil.move(str(old_base), str(dest))
                moved = True
        except OSError as e:
            self.log(f'  [退役] 移动失败：{e}')
            return {'ok': False, 'message': f'退役失败：{e}'}
        entry = self.register(gen, f'第 {gen} 代（{mode}）', dest,
                              status='trash' if mode != 'delete' else 'deleted',
                              stamp=stamp, note=f'退役方式 {mode}')
        entry['retired_at'] = datetime.now().isoformat(timespec='seconds')
        entry['kept'] = (mode == 'archive')
        reg = self.registry()
        for g in reg['generations']:
            if int(g.get('gen', -1)) == int(gen) and g.get('dir') == str(dest):
                g.update({'retired_at': entry['retired_at'], 'kept': entry['kept'],
                          'status': entry['status']})
        self._save_registry(reg)
        if mode == 'delete':
            shutil.rmtree(dest, ignore_errors=True)
            self.log(f'  [退役] 旧基底已删除（释放 {human(size)}）')
        elif mode == 'archive':
            self.log(f'  [退役] 旧基底已归档保留：{dest}（{human(size)}）')
        else:
            self.log(f'  [退役] 旧基底已移入回收区：{dest}（{human(size)}），稳定期后自动清理')
        self._save_state(promoted_at=datetime.now().isoformat(timespec='seconds'),
                         dialogue_turns_since_promote=0, retired_gen=gen)
        return {'ok': True, 'moved': moved, 'dir': str(dest), 'bytes': size, 'mode': mode}

    def bump_dialogue(self, n: int = 1) -> int:
        """新模型跑一轮对话就记一次（文档 4.1「24 小时 / 100 轮对话」的观察期）。"""
        st = self.state()
        total = int(st.get('dialogue_turns_since_promote', 0)) + int(n)
        self._save_state(dialogue_turns_since_promote=total)
        return total

    # ------------------------------------------------------------- 稳定期
    def stability(self) -> dict:
        st = self.state()
        promoted = st.get('promoted_at', '')
        hours = 0.0
        if promoted:
            try:
                dt = datetime.fromisoformat(promoted)
                hours = (datetime.now() - dt).total_seconds() / 3600.0
            except Exception:                                        # noqa: BLE001
                hours = 0.0
        turns = int(st.get('dialogue_turns_since_promote', 0))
        ok = (hours >= self.stability_hours) or (turns >= self.stability_rounds)
        return {'promoted_at': promoted, 'hours_elapsed': round(hours, 2), 'dialogue_turns': turns,
                'need_hours': self.stability_hours, 'need_turns': self.stability_rounds,
                'stable': bool(ok),
                'detail': (f'已观察 {hours:.1f} 小时 / {turns} 轮对话'
                           f'（达标线：{self.stability_hours:.0f} 小时 或 {self.stability_rounds} 轮）')}

    # ------------------------------------------------------------ 磁盘概览
    def disk_report(self) -> dict:
        reg = self.registry()
        used = {'base': dir_bytes(self.base_dir), 'adapter': dir_bytes(self.adapter_dir),
                'trash': dir_bytes(self.trash_dir), 'seeds': dir_bytes(self.seeds_dir),
                'legacy_retired': dir_bytes(self.legacy_retired)}
        used['total'] = sum(used.values())
        return {'used': used, 'used_human': {k: human(v) for k, v in used.items()},
                'max_total_bytes': self.max_total_bytes, 'max_total_human': human(self.max_total_bytes),
                'keep_generations': self.keep_generations, 'max_generations': self.max_generations,
                'generations': len(reg.get('generations', []))}

    # -------------------------------------------------------- 增长上限检查
    def cap_check(self, override: bool = False) -> dict:
        """文档 7.6：最多晋升 N 代，或总体积超阈值停止；用户可手动解除。"""
        reg = self.registry()
        gens = [g for g in reg.get('generations', []) if g.get('status') != 'deleted']
        d = self.disk_report()
        reasons = []
        if len(gens) >= self.max_generations:
            reasons.append(f'已达代数上限（{len(gens)}/{self.max_generations} 代）')
        if d['used']['total'] >= self.max_total_bytes:
            reasons.append(f"总体积 {human(d['used']['total'])} 已达上限 {human(self.max_total_bytes)}")
        blocked = bool(reasons) and not override
        return {'ok': not blocked, 'blocked': blocked, 'override': override, 'reasons': reasons,
                'generations': len(gens), 'max_generations': self.max_generations,
                'total_bytes': d['used']['total'], 'max_total_bytes': self.max_total_bytes,
                'message': ('；'.join(reasons) + '。可清理旧代、导出备份后删除，或用 --override 手动解除'
                            if blocked else '未触及增长上限')}

    # --------------------------------------------------------------- 垃圾回收
    def gc(self, keep: int | None = None, dry_run: bool = False, force: bool = False,
           max_generations: int | None = None) -> dict:
        """清理 trash/ 中的旧代（文档 4.2 / 7.6）。

        默认保留 `keep` 代（当前 + keep-1 个历史代）；只有稳定期达标或 force=True 才真删，
        否则只报告"可释放"空间 —— 即文档要求的"删除前二次确认 + 显示将释放的空间"。
        """
        keep = int(keep if keep is not None else self.keep_generations)
        max_generations = int(max_generations if max_generations is not None else self.max_generations)
        reg = self.registry()
        gens = [g for g in reg.get('generations', []) if g.get('status') == 'trash']
        gens.sort(key=lambda g: int(g.get('gen', 0)), reverse=True)     # 新 → 旧
        keepers = gens[:max(keep - 1, 0)]                               # 当前代 + keep-1 个历史代
        candidates = [g for g in gens[len(keepers):] if not g.get('kept')]
        stab = self.stability()
        d = self.disk_report()
        over_bytes = d['used']['total'] >= self.max_total_bytes
        over_gens = len([g for g in reg.get('generations', []) if g.get('status') != 'deleted']) > max_generations
        allowed = bool(force or stab['stable'] or over_bytes or over_gens)

        deletable, freed = [], 0
        for g in candidates:
            p = Path(g.get('dir', ''))
            b = g.get('bytes') or dir_bytes(p)
            deletable.append({'gen': g.get('gen'), 'dir': str(p), 'bytes': b, 'human': human(b)})
            freed += b
        result = {'keep_generations': keep, 'max_generations': max_generations,
                  'trash_generations': len(gens), 'keepers': [g.get('gen') for g in keepers],
                  'deletable': deletable, 'freed_bytes': freed, 'freed_human': human(freed),
                  'stability': stab, 'allowed': allowed, 'deleted': [], 'dry_run': dry_run}
        if not allowed:
            result['message'] = (f"稳定期未达标（{stab['detail']}），暂不删除；"
                                 f"确认无异常后可释放 {human(freed)}（加 --force 或稳定期达标后自动清理）")
            return result
        if dry_run:
            result['message'] = f'演练：将删除 {len(deletable)} 个旧代，释放 {human(freed)}'
            return result
        for item in deletable:
            p = Path(item['dir'])
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
            result['deleted'].append(item['gen'])
        if result['deleted']:
            for g in reg['generations']:
                if g.get('gen') in result['deleted'] and g.get('status') == 'trash':
                    g['status'] = 'deleted'
                    g['bytes'] = 0
            self._save_registry(reg)
        # 兼容清理老版本的 base_retired/
        if self.legacy_retired.exists():
            old = dir_bytes(self.legacy_retired)
            if old and allowed and not dry_run:
                shutil.rmtree(self.legacy_retired, ignore_errors=True)
                result['legacy_freed'] = old
        result['message'] = (f"已删除 {len(result['deleted'])} 个旧代，释放 {human(freed)}"
                             if result['deleted'] else '没有可清理的旧代')
        return result

    # --------------------------------------------------------------- 回滚
    def rollback(self, gen: int | None = None, dry_run: bool = False) -> dict:
        """回滚到指定代（默认：最近一个还在 trash/ 里的历史代）。文档 4.1「任何一代都可回滚」。"""
        reg = self.registry()
        act = self.active()
        gens = [g for g in reg.get('generations', []) if g.get('status') == 'trash']
        gens.sort(key=lambda g: int(g.get('gen', 0)), reverse=True)
        target = None
        if gen is None:
            target = gens[0] if gens else None
        else:
            for g in gens:
                if int(g.get('gen', -1)) == int(gen):
                    target = g
                    break
        if target is None:
            return {'ok': False, 'message': '回收区里没有可回滚的代数'
                                            '（若已被 gc 清理，可用 export 备份恢复）'}
        tdir = Path(target.get('dir', ''))
        if not tdir.exists():
            return {'ok': False, 'message': f'第 {target.get("gen")} 代文件不存在：{tdir}'}
        cur_gen = int(act.get('gen', 0)) if act else 0
        if dry_run:
            return {'ok': True, 'dry_run': True, 'target_gen': target.get('gen'),
                    'from_gen': cur_gen, 'dir': str(tdir),
                    'message': f'演练：将第 {cur_gen} 代退入回收区，并把第 {target.get("gen")} 代恢复为当前基底'}
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        back = self.trash_dir / f'rollback_gen{cur_gen}_{stamp}'
        try:
            if self.base_dir.exists():
                self.trash_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(self.base_dir), str(back))
            shutil.move(str(tdir), str(self.base_dir))
        except OSError as e:
            # 尽力回滚文件操作
            if not self.base_dir.exists() and back.exists():
                shutil.move(str(back), str(self.base_dir))
            return {'ok': False, 'message': f'回滚失败：{e}'}
        # 登记表更新
        for g in reg['generations']:
            if int(g.get('gen', -1)) == int(target.get('gen', -2)):
                g.update({'status': 'active', 'dir': str(self.base_dir), 'kept': False,
                          'bytes': dir_bytes(self.base_dir),
                          'rolled_back_at': datetime.now().isoformat(timespec='seconds')})
            elif int(g.get('gen', -1)) == cur_gen:
                g.update({'status': 'trash', 'dir': str(back), 'bytes': dir_bytes(back),
                          'retired_at': datetime.now().isoformat(timespec='seconds')})
        self._save_registry(reg)
        self._save_state(promoted_at=datetime.now().isoformat(timespec='seconds'),
                         dialogue_turns_since_promote=0, rolled_back_to=target.get('gen'))
        self.log(f"  [回滚] 已从第 {cur_gen} 代回滚到第 {target.get('gen')} 代")
        return {'ok': True, 'from_gen': cur_gen, 'target_gen': target.get('gen'),
                'dir': str(self.base_dir), 'message': f'已回滚到第 {target.get("gen")} 代'}

    # --------------------------------------------------------------- 导出
    def export(self, dest: Path | str, include_adapter: bool = True,
               include_meta: bool = True) -> dict:
        """打包当前模型 + 适配器 + 成长档案，供用户带走自己的模型（文档 7.7）。"""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        n_files = 0
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
            for src, prefix in ((self.base_dir, 'XLmodel'), (self.adapter_dir, 'adapter')):
                if not src.exists():
                    continue
                if src == self.adapter_dir and not include_adapter:
                    continue
                for p in src.rglob('*'):
                    if p.is_file():
                        z.write(p, f'{prefix}/{p.relative_to(src)}')
                        n_files += 1
            if include_meta:
                for p in (self.reg_path, self.state_path,
                          self.growth_dir / 'journal.jsonl',
                          self.growth_dir / 'replacement_state.json'):
                    if p.exists():
                        z.write(p, f'meta/{p.name}')
                        n_files += 1
                z.writestr('meta/README.txt',
                           '小凌成长模型导出包\n'
                           f'导出时间：{datetime.now().isoformat(timespec="seconds")}\n'
                           '包含：XLmodel/（当前基底）、adapter/（当前 LoRA）、meta/（成长档案）。\n'
                           '用法：解压后放回 .star_core/ 即可继续成长；meta/journal.jsonl 是完整成长日志。\n')
        size = dest.stat().st_size
        self.log(f'  [导出] {dest}（{n_files} 个文件，{human(size)}）')
        return {'ok': True, 'path': str(dest), 'files': n_files, 'bytes': size, 'human': human(size)}

    # --------------------------------------------------------------- 报告
    def report(self) -> str:
        d = self.disk_report()
        stab = self.stability()
        act = self.active()
        lines = ['小凌 · 模型生命周期', f"  当前代：第 {act.get('gen') if act else 0} 代"
                                       f"（{act.get('label', '—') if act else '—'}）"]
        lines.append(f"  磁盘：基底 {d['used_human']['base']}｜适配器 {d['used_human']['adapter']}"
                     f"｜回收区 {d['used_human']['trash']}｜种子 {d['used_human']['seeds']}"
                     f"｜合计 {d['used_human']['total']} / 上限 {d['max_total_human']}")
        lines.append(f"  稳定期：{stab['detail']} → {'已稳定（可清理旧代）' if stab['stable'] else '观察中'}")
        cap = self.cap_check()
        lines.append(f"  增长上限：{cap['message']}")
        reg = self.registry().get('generations', [])
        if reg:
            lines.append('  代数登记：')
            for g in reg:
                lines.append(f"    · 第 {g.get('gen')} 代  [{g.get('status')}]  "
                             f"{human(g.get('bytes', 0))}  {g.get('dir', '')}")
        return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌模型生命周期管理')
    ap.add_argument('cmd', choices=['status', 'generations', 'gc', 'rollback', 'export',
                                    'cap-check', 'stability', 'bump'])
    ap.add_argument('--keep', type=int, default=None)
    ap.add_argument('--gen', type=int, default=None)
    ap.add_argument('--path', default='')
    ap.add_argument('--n', type=int, default=1)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--override', action='store_true')
    ap.add_argument('--root', default=str(APP_DIR))
    a = ap.parse_args(argv)
    lc = ModelLifecycle(a.root)
    if a.cmd == 'status':
        print(lc.report())
    elif a.cmd == 'generations':
        print(json.dumps(lc.generations(), ensure_ascii=False, indent=1))
    elif a.cmd == 'gc':
        print(json.dumps(lc.gc(a.keep, a.dry_run, a.force), ensure_ascii=False, indent=1))
    elif a.cmd == 'rollback':
        print(json.dumps(lc.rollback(a.gen, a.dry_run), ensure_ascii=False, indent=1))
    elif a.cmd == 'export':
        if not a.path:
            print(json.dumps({'ok': False, 'error': '请用 --path 指定导出文件'}))
        else:
            print(json.dumps(lc.export(a.path), ensure_ascii=False, indent=1))
    elif a.cmd == 'cap-check':
        print(json.dumps(lc.cap_check(a.override), ensure_ascii=False, indent=1))
    elif a.cmd == 'stability':
        print(json.dumps(lc.stability(), ensure_ascii=False, indent=1))
    elif a.cmd == 'bump':
        print(json.dumps({'dialogue_turns': lc.bump_dialogue(a.n)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
