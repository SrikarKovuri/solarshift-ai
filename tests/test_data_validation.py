import numpy as np
import pandas as pd
import pytest

from solarshift.data.validate import validate


@pytest.mark.parametrize(('column', 'value', 'reason'), [
    ('0:30', -0.1, 'negative_interval'),
    ('0:30', np.nan, 'missing_or_nonfinite_interval'),
    ('0:30', np.inf, 'missing_or_nonfinite_interval'),
    ('Row Quality', 'NA', 'non_actual_or_unknown_quality'),
    ('Consumption Category', 'EXPORT', 'invalid_channel'),
    ('Customer', 0, 'invalid_customer'),
    ('Postcode', 20, 'invalid_postcode'),
    ('Generator Capacity', 0, 'invalid_capacity'),
    ('date', pd.NaT, 'invalid_date'),
])
def test_bad_channel_day_is_excluded_and_audited(valid_frame, column, value, reason):
    # Separate the control household so this test isolates invalid-value handling.
    # Conflicting metadata within one household is tested independently below.
    valid_frame.loc[1, 'Customer'] = 2
    valid_frame.loc[0, column] = value
    accepted, excluded, report = validate(valid_frame)
    assert len(accepted) == 1
    assert reason in excluded.iloc[0].reasons
    assert report['exclusion_reasons'][reason] == 1


def test_all_duplicate_candidates_are_rejected(valid_frame):
    frame = pd.concat([valid_frame, valid_frame.iloc[[0]]], ignore_index=True)
    accepted, excluded, _ = validate(frame)
    assert len(excluded) == 2
    assert accepted.iloc[0]['Consumption Category'] == 'GG'


@pytest.mark.parametrize('date', ['2010-10-03', '2011-04-03'])
def test_both_dst_transitions_are_excluded(valid_frame, date):
    valid_frame['date'] = pd.Timestamp(date)
    accepted, excluded, _ = validate(valid_frame)
    assert accepted.empty
    assert excluded.reasons.eq('dst_transition_day').all()


def test_absent_controlled_load_is_not_created(valid_frame):
    accepted, _, _ = validate(valid_frame)
    assert set(accepted['Consumption Category']) == {'GC', 'GG'}


def test_outside_year_and_metadata_conflicts(valid_frame):
    valid_frame.loc[0, 'Postcode'] = 2000
    accepted, _, report = validate(valid_frame, '2011-07-01', '2012-06-30')
    assert accepted.empty
    assert report['exclusion_reasons']['inconsistent_postcode'] == 2
    assert report['exclusion_reasons']['outside_file_period'] == 2


def test_high_generation_is_warning_not_automatic_deletion(valid_frame):
    valid_frame.loc[1, '12:00'] = 10
    accepted, _, report = validate(valid_frame)
    assert len(accepted) == 2
    assert report['warning_pv_days_above_125_percent_nameplate'] == 1
