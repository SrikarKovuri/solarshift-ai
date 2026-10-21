import pytest

from solarshift.data.parse import read_annual


@pytest.mark.parametrize('date', ['1-Jul-10', '1/07/2010'])
@pytest.mark.parametrize('quality', [True, False])
def test_real_date_and_header_variants(write_csv, date, quality):
    row = [1, 3.78, 2076, 'GC', date] + [0.5] * 48 + ([''] if quality else [])
    frame = read_annual(write_csv([row], quality=quality))
    assert str(frame.iloc[0]['date'].date()) == '2010-07-01'
    assert frame.iloc[0]['source_line'] == 3
    assert frame.iloc[0]['Row Quality'] == ''


def test_quality_na_not_lost_to_csv_missing_value_parser(write_csv):
    frame = read_annual(write_csv([[1, 3.78, 2076, 'GC', '1-Jul-10'] + [0.5] * 48 + ['NA']]))
    assert frame.iloc[0]['Row Quality'] == 'NA'


def test_rejects_wrong_interval_order(write_csv):
    path = write_csv()
    path.write_text(path.read_text().replace('0:30,1:00', '1:00,0:30'))
    with pytest.raises(ValueError, match='unexpected columns'):
        read_annual(path)


def test_header_without_notice(write_csv):
    frame = read_annual(write_csv(notice=False))
    assert len(frame) == 2
    assert frame.iloc[0].source_line == 2
