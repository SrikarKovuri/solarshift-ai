"""Selection constants adapted from Theo's supplied configuration.

The Day 4 runner opens only burn-in, train and validation load files.
"""
import datetime as dt
SEED = 2112
EVENING_HH = list(range(32, 42))
SPLITS = {
    'burn_in': (dt.date(2021, 4, 1), dt.date(2021, 4, 30)),
    'train': (dt.date(2021, 5, 1), dt.date(2023, 4, 30)),
    'val': (dt.date(2023, 5, 1), dt.date(2024, 4, 30)),
}
