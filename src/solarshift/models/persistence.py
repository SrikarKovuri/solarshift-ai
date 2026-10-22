"""Same local half-hour slot seven calendar days earlier."""

import numpy as np

from solarshift.features.dataset import assert_available


def predict(frame):
    assert_available(frame)
    values = frame['lag_7d_kwh'].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Weekly persistence requires finite non-negative history')
    return values
