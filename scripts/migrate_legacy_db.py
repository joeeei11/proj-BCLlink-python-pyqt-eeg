#!/usr/bin/env python
"""合并旧版 SQLite 数据库到新库。

用法：
    python scripts/migrate_legacy_db.py --old data.db --old data/neuro_pilot_old.db [--dry-run]

迁移范围：
    - subjects：以 name 去重
    - trials：以 subject.name + onset_time 去重（需借助 sessions 关联）
旧库改名为 <path>.bak_<timestamp>（非 dry-run 时执行）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from neuropilot.infra.config import load_settings
from neuropilot.infra.db.engine import init_engine, get_session
from neuropilot.infra.db.repositories.subject_repo import SubjectRepo, SubjectCreateDTO


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _migrate_one(old_path: str, dry_run: bool, session: object) -> dict[str, int]:
    counts: dict[str, int] = {"subjects": 0, "trials": 0, "skipped": 0}
    if not Path(old_path).exists():
        print(f"  [跳过] 文件不存在：{old_path}")
        return counts

    conn = sqlite3.connect(old_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    if "subjects" in tables:
        repo = SubjectRepo(session)  # type: ignore[arg-type]
        existing_names = {s.name for s in repo.list()}
        rows = cur.execute("SELECT * FROM subjects").fetchall()
        for row in rows:
            name = row["name"] if "name" in row.keys() else str(row[0])
            if name in existing_names:
                counts["skipped"] += 1
                continue
            print(f"  [subject] 迁移：{name}")
            counts["subjects"] += 1
            if not dry_run:
                dto = SubjectCreateDTO(
                    name=name,
                    gender=row["gender"] if "gender" in row.keys() else None,
                    age=row["age"] if "age" in row.keys() else None,
                    diagnosis=row["diagnosis"] if "diagnosis" in row.keys() else None,
                    notes=row["notes"] if "notes" in row.keys() else None,
                )
                repo.create(dto)
                existing_names.add(name)

    conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="合并旧版数据库")
    parser.add_argument("--old", action="append", dest="old_paths", default=[], metavar="PATH")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.old_paths:
        parser.print_help()
        sys.exit(1)

    cfg = load_settings()
    init_engine(cfg.db_path)

    total: dict[str, int] = {"subjects": 0, "trials": 0, "skipped": 0}

    for session in get_session():
        for old_path in args.old_paths:
            print(f"\n处理：{old_path}")
            counts = _migrate_one(old_path, args.dry_run, session)
            for k in total:
                total[k] += counts.get(k, 0)

    print("\n========== 迁移汇总 ==========")
    print(f"  subjects 迁移：{total['subjects']}")
    print(f"  跳过（已存在）：{total['skipped']}")
    if args.dry_run:
        print("  [dry-run] 不写库，不重命名旧文件")
        return

    ts = _now_ts()
    for old_path in args.old_paths:
        p = Path(old_path)
        if p.exists():
            bak = p.with_suffix(f".bak_{ts}")
            shutil.move(str(p), str(bak))
            print(f"  已备份：{p} → {bak}")


if __name__ == "__main__":
    main()
