"""Calendar features: NSW public holidays and the sun's elevation.

Holidays: uses the `holidays` package (pip install holidays; available in Colab) when installed,
otherwise a built-in list of NSW gazetted public holidays 2020-2025. The built-in list leaves out
the NSW Bank Holiday (first Monday in August), which applies to banks only. The test
tests/test_calendar.py checks that both sources agree when `holidays` is installed.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

_D = dt.date
NSW_HOLIDAYS_FALLBACK = {
    # 2020 (tail only, for burn-in lags)
    _D(2020, 6, 8), _D(2020, 10, 5), _D(2020, 12, 25), _D(2020, 12, 26), _D(2020, 12, 28),
    # 2021
    _D(2021, 1, 1), _D(2021, 1, 26), _D(2021, 4, 2), _D(2021, 4, 3), _D(2021, 4, 4), _D(2021, 4, 5),
    _D(2021, 4, 25), _D(2021, 6, 14), _D(2021, 10, 4), _D(2021, 12, 25), _D(2021, 12, 26),
    _D(2021, 12, 27), _D(2021, 12, 28),
    # 2022 (incl. National Day of Mourning 22 Sep)
    _D(2022, 1, 1), _D(2022, 1, 3), _D(2022, 1, 26), _D(2022, 4, 15), _D(2022, 4, 16), _D(2022, 4, 17),
    _D(2022, 4, 18), _D(2022, 4, 25), _D(2022, 6, 13), _D(2022, 9, 22), _D(2022, 10, 3),
    _D(2022, 12, 25), _D(2022, 12, 26), _D(2022, 12, 27),
    # 2023
    _D(2023, 1, 1), _D(2023, 1, 2), _D(2023, 1, 26), _D(2023, 4, 7), _D(2023, 4, 8), _D(2023, 4, 9),
    _D(2023, 4, 10), _D(2023, 4, 25), _D(2023, 6, 12), _D(2023, 10, 2), _D(2023, 12, 25), _D(2023, 12, 26),
    # 2024
    _D(2024, 1, 1), _D(2024, 1, 26), _D(2024, 3, 29), _D(2024, 3, 30), _D(2024, 3, 31), _D(2024, 4, 1),
    _D(2024, 4, 25), _D(2024, 6, 10), _D(2024, 10, 7), _D(2024, 12, 25), _D(2024, 12, 26),
    # 2025
    _D(2025, 1, 1), _D(2025, 1, 27), _D(2025, 4, 18), _D(2025, 4, 19), _D(2025, 4, 20), _D(2025, 4, 21),
    _D(2025, 4, 25), _D(2025, 6, 9), _D(2025, 10, 6), _D(2025, 12, 25), _D(2025, 12, 26),
}


def nsw_holidays(years=range(2020, 2026)) -> set:
    try:
        import holidays
        h = holidays.Australia(subdiv="NSW", years=list(years))
        return {d for d, name in h.items() if "Bank Holiday" not in name}
    except ImportError:
        return set(NSW_HOLIDAYS_FALLBACK)


def solar_elevation_deg(ts_local: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Approximate solar elevation (NOAA formulas; error < ~0.5 deg, plenty for a feature).
    ts_local: naive local clock times in Australia/Sydney (DST-aware conversion done here)."""
    ts_utc = ts_local.tz_localize("Australia/Sydney", ambiguous=False, nonexistent="shift_forward").tz_convert("UTC")
    doy = ts_utc.dayofyear.to_numpy()
    hour = (ts_utc.hour + ts_utc.minute / 60).to_numpy()
    g = 2 * np.pi / 365 * (doy - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    tst = hour * 60 + eqt + 4 * lon                 # true solar time, minutes
    ha = np.radians(tst / 4 - 180)
    latr = np.radians(lat)
    cosz = np.sin(latr) * np.sin(decl) + np.cos(latr) * np.cos(decl) * np.cos(ha)
    return np.degrees(np.arcsin(np.clip(cosz, -1, 1)))
