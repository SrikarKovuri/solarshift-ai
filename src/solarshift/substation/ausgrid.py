"""Read Ausgrid zone substation zip files into one tidy (long) table.

Plain-language summary
----------------------
Each Ausgrid zip has one CSV per substation. Each CSV row is one day:
    year, Zone Substation, Date, Unit, then 96 columns of 15-minute MW values.

Things we found in the REAL files (Oct 2026) that this parser handles:
  * Column labels are interval END times: the first is 0:15, the last is 24:00
    (or 00:00 / 24:00:00 in some years). So "0:15" = the interval 00:00-00:15.
  * The FY2025 file has its time columns OUT OF ORDER (01:00 comes after 01:45).
    We therefore sort the value columns by their time label, never by position.
  * Each year writes the date differently: 01MAY2020, 01/05/2023, 2024-05-01.
  * Every row has 96 slots, even on daylight-saving change days (see dst_report()).
  * Some FY2023 rows are cut short (fewer than 96 values); missing slots become NaN.

Output columns of read_year():
    substation (str), date (local calendar date), slot (0..95, interval START = slot*15 min),
    mw (float32), fy (int, the file label)
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

N_SLOTS = 96


def _label_to_end_minutes(label: str) -> int:
    """'0:15' -> 15, '01:00' -> 60, '24:00' / '24:00:00' / '00:00' (last col) -> 1440."""
    parts = label.strip().split(":")
    h, m = int(parts[0]), int(parts[1])
    mins = h * 60 + m
    return 1440 if mins == 0 else mins


def _parse_dates(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    out = pd.to_datetime(s, format="%d%b%Y", errors="coerce")          # 01MAY2020
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):                    # 01/05/2023, 2024-05-01
        miss = out.isna()
        if not miss.any():
            break
        out[miss] = pd.to_datetime(s[miss], format=fmt, errors="coerce")
    return out.dt.date


def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    header, body = rows[0], [r for r in rows[1:] if r and any(c.strip() for c in r)]
    labels = header[4:]
    end_min = [_label_to_end_minutes(l) for l in labels]
    if sorted(end_min) != list(range(15, 1441, 15)):
        raise ValueError(f"Unexpected time columns: {labels[:6]}...")
    order = np.argsort(end_min)                       # fixes FY2025 column order
    vals = np.full((len(body), N_SLOTS), np.nan, dtype="float64")
    for i, r in enumerate(body):
        v = r[4:4 + N_SLOTS]
        arr = pd.to_numeric(pd.Series(v + [""] * (N_SLOTS - len(v))), errors="coerce").to_numpy()
        vals[i] = arr[order]
    meta = pd.DataFrame({
        "substation": [r[1].strip() for r in body],
        "date": _parse_dates(pd.Series([r[2] for r in body])),
        "unit": [r[3].strip() if len(r) > 3 else "" for r in body],
        "n_values_in_row": [len(r) - 4 for r in body],
    })
    wide = pd.concat([meta, pd.DataFrame(vals, columns=range(N_SLOTS))], axis=1)
    return wide


def read_year_wide(zip_path: str | Path) -> pd.DataFrame:
    """One row per substation-day, 96 value columns (0..95 = interval start slot)."""
    zip_path = Path(zip_path)
    fy = int(re.search(r"(20\d\d)", zip_path.name).group(1))
    frames = []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith(".csv"):
                continue
            df = read_csv_bytes(z.read(name))
            df["file"] = name.split("/")[-1]
            frames.append(df)
    wide = pd.concat(frames, ignore_index=True)
    wide["fy"] = fy
    return wide


def wide_to_long(wide: pd.DataFrame) -> pd.DataFrame:
    long = wide.melt(id_vars=["substation", "date", "fy"], value_vars=list(range(N_SLOTS)),
                     var_name="slot", value_name="mw")
    long["slot"] = long["slot"].astype("int16")
    long["mw"] = long["mw"].astype("float32")
    return long.sort_values(["substation", "date", "slot"]).reset_index(drop=True)


def canonical_name(name: str) -> str:
    """Normalise substation names across years ('Aberdeen 66_11kV' style)."""
    return re.sub(r"\s+", " ", name.strip())
