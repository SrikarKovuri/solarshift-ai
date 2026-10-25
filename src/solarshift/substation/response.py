"""Transparent scenario mechanics, adapted from Theo's trigger/simulation ideas.

All shares and capacity limits are scenario assumptions, not measured behaviour.
"""
from dataclasses import dataclass, asdict
import numpy as np

EVENING = np.arange(32, 42)
MIDDAY = np.arange(20, 30)
LATE = np.arange(42, 46)


def prob_exceed(quantiles, threshold):
    q = np.asarray(quantiles, dtype=float)
    t = np.asarray(threshold, dtype=float)
    if q.ndim != 2 or q.shape[1] != 3 or not np.isfinite(q).all() or not np.isfinite(t).all():
        raise ValueError('Finite n by 3 quantiles and thresholds required')
    if (np.diff(q, axis=1) < 0).any():
        raise ValueError('Quantiles must be ordered')
    lo, mid, hi = q.T
    cdf = np.where(t <= mid, .1 + .4*(t-lo)/np.maximum(mid-lo, 1e-9),
                   .5 + .4*(t-mid)/np.maximum(hi-mid, 1e-9))
    return 1 - np.clip(cdf, .01, .99)


def price_multiplier(probability):
    p = np.asarray(probability, dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Probability must be between 0 and 1')
    return 1 + .5*np.maximum(p-.3, 0)/.7


@dataclass(frozen=True)
class Scenario:
    residential_share: float = .60
    flexible_fraction: float = .15
    response_rate: float = .10
    exempt_share: float = .10
    share_solar: float = .21
    share_battery: float = .02  # subset of solar, never added as another overlapping group
    battery_factor: float = 2.
    to_midday: float = .5

    def validate(self):
        for name, value in asdict(self).items():
            if not np.isfinite(value) or value < 0 or (name != 'battery_factor' and value > 1):
                raise ValueError(f'Invalid {name}')
        if self.share_battery > self.share_solar:
            raise ValueError('Battery share must be a subset of solar share')
        return self


def effective_response(multiplier, params):
    params.validate()
    m = np.asarray(multiplier, dtype=float)
    if not np.isfinite(m).all() or ((m < 1) | (m > 1.5)).any():
        raise ValueError('Multiplier must be in [1, 1.5]')
    strength = (m-1)/.5
    normal = np.clip(params.response_rate*strength, 0, 1)
    battery = np.clip(params.response_rate*params.battery_factor*strength, 0, 1)
    # Three exclusive groups: no solar, solar only, solar+battery.
    return (1-params.exempt_share)*((1-params.share_solar)*normal +
           (params.share_solar-params.share_battery)*normal + params.share_battery*battery)


def allocate(energy, headroom_mwh, weights):
    """Weighted water filling across destinations, retaining capacity constraints."""
    room = np.asarray(headroom_mwh, float).copy()
    w = np.asarray(weights, float)
    if w.shape != (room.shape[1],) or not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError('Destination weights must be finite, nonnegative and nonzero')
    out = np.zeros_like(room)
    remaining = np.asarray(energy, float).copy()
    for _ in range(room.shape[1]+1):
        active = (room > 1e-12)*w[None, :]
        den = active.sum(1)
        share = np.divide(active, den[:, None], out=np.zeros_like(active), where=den[:, None] > 0)
        add = np.minimum(remaining[:, None]*share, room)
        out += add
        room -= add
        remaining = np.maximum(0, remaining-add.sum(1))
    if (remaining > 1e-8).any():
        raise ValueError('Insufficient destination capacity for requested allocation')
    return out


def simulate(loads, multiplier, capacity_mw, params=Scenario(), midday_weights=None, late_weights=None):
    """Vectorized complete signed MW days. Capacity is an assumed import ceiling.

    Remove only positive evening net imports. Scale removal to fit BOTH destination
    energy budgets; unshiftable energy remains in its original interval.
    """
    params.validate()
    x = np.asarray(loads, float)
    if x.ndim != 2 or x.shape[1] != 48 or not np.isfinite(x).all():
        raise ValueError('Complete finite 48-slot signed days required')
    m = np.broadcast_to(np.asarray(multiplier, float), (len(x),))
    cap = np.broadcast_to(np.asarray(capacity_mw, float), (len(x),))
    if not np.isfinite(cap).all() or (cap < 0).any():
        raise ValueError('Nonnegative finite scenario capacity required')
    rho = effective_response(m, params)
    requested_mw = np.maximum(x[:, EVENING], 0)*params.residential_share*params.flexible_fraction*rho[:, None]
    requested_mwh = requested_mw.sum(1)*.5
    wm = np.ones(len(MIDDAY)) if midday_weights is None else np.asarray(midday_weights, float)
    wl = np.ones(len(LATE)) if late_weights is None else np.asarray(late_weights, float)
    # Validate weights even in zero-response scenarios.
    for weights, size in [(wm,len(MIDDAY)),(wl,len(LATE))]:
        if weights.shape != (size,) or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
            raise ValueError('Invalid destination weights')
    hm = np.maximum(cap[:, None]-x[:, MIDDAY],0)*.5*(wm > 0)
    hl = np.maximum(cap[:, None]-x[:, LATE],0)*.5*(wl > 0)
    moved = requested_mwh.copy()
    if params.to_midday > 0:
        moved = np.minimum(moved, hm.sum(1)/params.to_midday)
    if params.to_midday < 1:
        moved = np.minimum(moved, hl.sum(1)/(1-params.to_midday))
    scale = np.divide(moved, requested_mwh, out=np.zeros_like(moved), where=requested_mwh > 0)
    after = x.copy()
    after[:, EVENING] -= requested_mw*scale[:, None]
    after[:, MIDDAY] += allocate(moved*params.to_midday,hm,wm)/.5
    after[:, LATE] += allocate(moved*(1-params.to_midday),hl,wl)/.5
    return after, {'requested_mwh':requested_mwh, 'moved_mwh':moved,
                   'capacity_limited':moved < requested_mwh-1e-10,
                   'effective_response':rho,
                   'energy_error_mwh':(after.sum(1)-x.sum(1))*.5}
