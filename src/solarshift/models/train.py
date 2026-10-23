"""Train a bounded two-target search on training data; select on validation only."""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import tempfile
import time

import numpy as np
import pandas as pd

from solarshift.data.common import sha256, write_json
from solarshift.evaluation.metrics import errors, evening_mask
from solarshift.features.dataset import FEATURE_COLUMNS
from .boosted import read_config, load_development, make_model, feature_matrix, predict_nonnegative, load_model
from .tracking import training_carbon


def train(path):
    config = read_config(path)
    experiment = config['experiment']
    frame, manifest, forecast = load_development(experiment['forecast_config'])
    manifest_hash = sha256(forecast['output_dir'] / 'manifest.json')
    output = experiment['output_dir']
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.model-search-', dir=output.parent))
    candidates = []
    selected = {}
    versions = {name: version(name) for name in ['xgboost', 'numpy', 'pandas', 'scikit-learn', 'codecarbon']}
    versions['python'] = platform.python_version()
    try:
        with training_carbon(stage, config['carbon']):
            for channel, key in [('GC', 'selection_demand'), ('GG', 'selection_pv')]:
                target = frame[frame.channel.eq(channel)]
                train_rows = target[target.split.eq('train')]
                validation = target[target.split.eq('validation')]
                x_train = feature_matrix(train_rows)
                window = experiment[key]
                mask = evening_mask(validation) if window == 'evening_16_21' else np.ones(len(validation), dtype=bool)
                best_score = float('inf')
                directory = stage / channel
                directory.mkdir()
                for candidate in config['candidates']:
                    started = time.perf_counter()
                    model = make_model(candidate, experiment['seed'], experiment['threads'])
                    model.fit(x_train, train_rows.energy_kwh)
                    prediction = predict_nonnegative(model, validation)
                    metrics = {name: errors(validation.loc[m, 'energy_kwh'], prediction[m])
                               for name, m in [('full_day', np.ones(len(validation), dtype=bool)), ('evening_16_21', evening_mask(validation))]}
                    score = errors(validation.loc[mask, 'energy_kwh'], prediction[mask])['mae_kwh']
                    record = {'channel': channel, 'candidate': candidate['name'], 'parameters': candidate,
                              'selection_window': window, 'selection_mae_kwh': score,
                              'train_rows': len(train_rows), 'validation_rows': len(validation),
                              'fit_predict_seconds': time.perf_counter() - started, 'metrics': metrics}
                    candidates.append(record)
                    print(f'{channel} {candidate["name"]}: selection MAE={score:.6f} ({record["fit_predict_seconds"]:.1f}s)', flush=True)
                    # Stable ties keep the earlier, smaller candidate. No refit on validation.
                    if score < best_score:
                        best_score = score
                        model.save_model(directory / 'model.ubj')
                        metadata = {'channel': channel, 'feature_columns': FEATURE_COLUMNS,
                                    'prediction_policy': 'clip_lower_zero', 'threads': experiment['threads'],
                                    'feature_manifest_sha256': manifest_hash, 'model_sha256': sha256(directory / 'model.ubj'),
                                    'seed': experiment['seed'], 'versions': versions, 'selected': record,
                                    'training_dates': [str(train_rows.source_date.min().date()), str(train_rows.source_date.max().date())],
                                    'validation_dates': [str(validation.source_date.min().date()), str(validation.source_date.max().date())],
                                    'test_evaluated': False}
                        write_json(directory / 'metadata.json', metadata)
                        reloaded, _ = load_model(directory, channel)
                        # XGBoost 3.0 JSON scalar serialization may round the base score.
                        # Permit sub-micro-kWh float32 roundoff, never material drift.
                        np.testing.assert_allclose(prediction, predict_nonnegative(reloaded, validation), rtol=0, atol=1e-6)
                        selected[channel] = metadata
        summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'partition': 'validation',
                   'test_evaluated': False, 'cohort': manifest['cohort'], 'versions': versions,
                   'config_sha256': sha256(Path(path)), 'feature_manifest_sha256': manifest_hash,
                   'selection_policy': f"GC {experiment['selection_demand']} MAE; GG {experiment['selection_pv']} MAE; ties retain first candidate. Validation is used for selection and is not an unbiased final-test estimate.",
                   'selected': selected, 'candidates': candidates,
                   'carbon': json.loads((stage / 'carbon.json').read_text())}
        write_json(stage / 'training_summary.json', summary)
        shutil.copyfile(path, stage / 'experiment.toml')
        # Publish only after both targets and reload equivalence checks succeed.
        output.mkdir(parents=True, exist_ok=True)
        for child in stage.iterdir():
            if child.is_dir():
                shutil.copytree(child, output / child.name, dirs_exist_ok=True)
            else:
                child.replace(output / child.name)
    finally:
        shutil.rmtree(stage)
    from solarshift.evaluation.boosted import evaluate
    return evaluate(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='configs/models.toml')
    args = parser.parse_args()
    train(args.config)


if __name__ == '__main__':
    main()
