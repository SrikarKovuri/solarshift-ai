"""Offline CodeCarbon estimate with explicit assumed power and no elevated sampling."""

from contextlib import contextmanager
import math
import time

import pandas as pd

from solarshift.data.common import write_json


@contextmanager
def training_carbon(output, config):
    evidence = {'status': 'unavailable', 'method': 'CodeCarbon offline, assumed CPU TDP and constant RAM power',
                'country_iso_code': config['country_iso_code'],
                'assumed_cpu_tdp_w': config['cpu_power_w'],
                'assumed_ram_power_w': config['ram_power_w'],
                'scope': 'All candidate fitting, validation prediction, scoring and model serialization inside the search; excludes data preparation, final report, audits, development and AI assistance.',
                'limitations': 'An estimate, not a wall-meter measurement. Uses bundled country-average electricity intensity, not historical household emissions or a current NSW marginal factor. Other machine activity and embodied emissions are not attributed.'}
    tracker = None
    raw = output / 'carbon_raw.csv'
    try:
        from codecarbon import OfflineEmissionsTracker
        tracker = OfflineEmissionsTracker(
            country_iso_code=config['country_iso_code'], project_name='solarshift-model-search',
            output_dir=str(output), output_file=raw.name, save_to_file=True,
            save_to_api=False, save_to_prometheus=False, tracking_mode='machine',
            force_cpu_power=config['cpu_power_w'], force_ram_power=config['ram_power_w'],
            measure_power_secs=1, log_level='error', allow_multiple_runs=True)
        tracker.start()
    except Exception as exc:
        evidence['error'] = f'{type(exc).__name__}: {exc}'
    start = time.perf_counter()
    try:
        yield evidence
    finally:
        evidence['wall_seconds'] = time.perf_counter() - start
        if tracker is not None:
            try:
                emissions = tracker.stop()
                if emissions is not None and raw.exists():
                    record = pd.read_csv(raw).iloc[-1]
                    for key in ['duration', 'emissions', 'energy_consumed', 'cpu_energy', 'ram_energy', 'gpu_energy', 'cpu_power', 'ram_power']:
                        evidence[key] = float(record[key])
                    if not all(math.isfinite(evidence[k]) and evidence[k] >= 0 for k in ['emissions', 'energy_consumed']):
                        raise ValueError('Invalid CodeCarbon estimate')
                    evidence['status'] = 'estimated'
                    evidence['cpu_method_note'] = 'CodeCarbon 3.0.7 constant mode uses 50% of the supplied CPU TDP; effective CPU watts are recorded in cpu_power.'
                    evidence['units'] = {'emissions': 'kg CO2e', 'energy_consumed': 'kWh', 'duration': 'seconds'}
                else:
                    evidence['error'] = 'CodeCarbon returned no estimate'
            except Exception as exc:
                evidence['error'] = f'{type(exc).__name__}: {exc}'
        write_json(output / 'carbon.json', evidence)
