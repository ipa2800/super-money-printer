"""从参考 db 迁移最近 90 天的历史数据到新 schema。

参考 db schema (无 source 列, 默认写 'reference'):
- index_cache  → kline_cache(freq='d')
- shares_cache → shares_cache
- volume_cache → volume_cache
- macro_cache  → macro_cache

用法:
    python scripts/migrate_from_reference.py --from ~/.openclaw/workspace-padiya/scripts/etf_dashboard/etf_data.db
    python scripts/migrate_from_reference.py --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.connection import get_connection, reset_connection  # noqa: E402


DEFAULT_REF_DB = Path.home() / ".openclaw/workspace-padiya/scripts/etf_dashboard/etf_data.db"
DEFAULT_SOURCE = "reference"  # 旧 db 没 source 字段,统一标 reference
RECENT_DAYS = 90


def _cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).date().isoformat()


def migrate_kline(cur, ref, dry_run: bool) -> int:
    """index_cache → kline_cache(freq='d')"""
    cutoff = _cutoff_iso()
    rows = ref.execute(
        "SELECT code, date, open, high, low, close, volume FROM index_cache WHERE date >= ?",
        (cutoff,),
    ).fetchall()
    inserted = 0
    for r in rows:
        if dry_run:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO kline_cache
                (symbol, freq, date, open, high, low, close, volume, source, fetched_at)
            VALUES (?, 'd', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r["code"], r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"],
             DEFAULT_SOURCE, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        inserted += cur.rowcount > 0 and 1 or 0
    return inserted


def migrate_shares(cur, ref, dry_run: bool) -> int:
    cutoff = _cutoff_iso()
    rows = ref.execute(
        "SELECT code, date, shares FROM shares_cache WHERE date >= ?",
        (cutoff,),
    ).fetchall()
    inserted = 0
    for r in rows:
        if dry_run:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO shares_cache (code, date, shares, source, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (r["code"], r["date"], r["shares"], DEFAULT_SOURCE,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        inserted += cur.rowcount > 0 and 1 or 0
    return inserted


def migrate_volume(cur, ref, dry_run: bool) -> int:
    cutoff = _cutoff_iso()
    rows = ref.execute(
        "SELECT code, date, volume FROM volume_cache WHERE date >= ?",
        (cutoff,),
    ).fetchall()
    inserted = 0
    for r in rows:
        if dry_run:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO volume_cache (code, date, volume, source, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (r["code"], r["date"], r["volume"], DEFAULT_SOURCE,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        inserted += cur.rowcount > 0 and 1 or 0
    return inserted


def migrate_macro(cur, ref, dry_run: bool) -> int:
    cutoff = _cutoff_iso()
    rows = ref.execute(
        "SELECT indicator, date, value FROM macro_cache WHERE date >= ?",
        (cutoff,),
    ).fetchall()
    inserted = 0
    for r in rows:
        if dry_run:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO macro_cache (indicator, date, value, source, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (r["indicator"], r["date"], r["value"], DEFAULT_SOURCE,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        inserted += cur.rowcount > 0 and 1 or 0
    return inserted


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="src", default=str(DEFAULT_REF_DB),
                   help="参考 db 路径")
    p.add_argument("--dry-run", action="store_true", help="只统计, 不写库")
    args = p.parse_args()

    src_path = Path(args.src)
    if not src_path.exists():
        print(f"❌ 参考 db 不存在: {src_path}")
        sys.exit(1)

    reset_connection()  # 测试用清空; 主流程下首次 get_connection() 会建新连接
    conn = get_connection()
    cur = conn.cursor()
    # ATTACH 参考 db
    ref = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    ref.row_factory = sqlite3.Row

    print(f"📦 Source: {src_path}")
    print(f"📅 Window: 最近 {RECENT_DAYS} 天 (>= {_cutoff_iso()})")
    print(f"🔍 Dry-run: {args.dry_run}")

    counts = {
        "kline (index_cache)": migrate_kline(cur, ref, args.dry_run),
        "shares (shares_cache)": migrate_shares(cur, ref, args.dry_run),
        "volume (volume_cache)": migrate_volume(cur, ref, args.dry_run),
        "macro (macro_cache)":   migrate_macro(cur, ref, args.dry_run),
    }

    if not args.dry_run:
        conn.commit()

    print("✅ Migration result:")
    for k, v in counts.items():
        print(f"  - {k:24s} {v:6d} rows")
    ref.close()


if __name__ == "__main__":
    main()