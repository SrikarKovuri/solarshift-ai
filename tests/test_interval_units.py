import pandas as pd
import pytest

from solarshift.data.validate import to_intervals


def test_energy_power_and_midnight_are_physical(valid_frame):
    rows = to_intervals(valid_frame)
    assert len(rows) == 96
    gc = rows[rows.channel == 'GC'].sort_values('slot')
    assert gc.energy_kwh.sum() == 24
    assert gc.average_power_kw.eq(1).all()
    assert gc.iloc[0].interval_start.isoformat() == '2010-07-01T00:00:00+10:00'
    assert gc.iloc[-1].interval_end.isoformat() == '2010-07-02T00:00:00+10:00'
    assert ((gc.interval_end - gc.interval_start) == pd.Timedelta(minutes=30)).all()
    assert not rows.duplicated(['customer', 'source_date', 'channel', 'slot']).any()


def test_summer_timezone(valid_frame):
    valid_frame['date'] = pd.Timestamp('2011-01-01')
    assert to_intervals(valid_frame).iloc[0].interval_start.isoformat().endswith('+11:00')


def test_conversion_rejects_dst_even_if_validation_skipped(valid_frame):
    valid_frame['date'] = pd.Timestamp('2010-10-03')
    with pytest.raises(ValueError, match='DST'):
        to_intervals(valid_frame)
