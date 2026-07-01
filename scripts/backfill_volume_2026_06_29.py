"""One-shot backfill: pull 2026-06-29 volume for 4 main ETFs from akshare.

ponytail: akshare call is sync + slow (~2-3s each), run sequentially.
"""
import akshare as ak
import sqlite3
from datetime import datetime, timezone

CODES = [
    ("510050", "sh510050"),
    ("510300", "sh510300"),
    ("510330", "sh510330"),
    ("510500", "sh510500"),
]

conn = sqlite3.connect("etf_data.db")
cur = conn.cursor()
now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

existing = {}
for code, _ in CODES:
    row = conn.execute("SELECT MAX(date) FROM volume_cache WHERE code=?", (code,)).fetchone()
    existing[code] = row[0] if row else None
print("existing max dates:", existing)

new_rows = []
for code, sina in CODES:
    df = ak.fund_etf_hist_sina(symbol=sina)
    df["date_str"] = df["date"].astype(str)
    df = df[df["date_str"] > (existing[code] or "0000-00-00")]
    n = len(df)
    if n:
        print(f"{code}: {n} new rows from {df['date_str'].min()} to {df['date_str'].max()}")
        for _, r in df.iterrows():
            new_rows.append((code, r["date_str"], float(r["volume"]), "akshare", now_iso))

if new_rows:
    cur.executemany(
        "INSERT OR REPLACE INTO volume_cache (code, date, volume, source, fetched_at) VALUES (?,?,?,?,?)",
        new_rows,
    )
    conn.commit()
    print(f"--- inserted {len(new_rows)} rows ---")

for code, _ in CODES:
    mn = conn.execute("SELECT MIN(date) FROM volume_cache WHERE code=?", (code,)).fetchone()[0]
    mx = conn.execute("SELECT MAX(date) FROM volume_cache WHERE code=?", (code,)).fetchone()[0]
    n = conn.execute("SELECT COUNT(*) FROM volume_cache WHERE code=?", (code,)).fetchone()[0]
    print(f"{code}: {mn} → {mx} ({n} rows)")
conn.close()
