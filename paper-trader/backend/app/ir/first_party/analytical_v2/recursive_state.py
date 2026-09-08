"""Unpublished recursive v2 candidates; no registry composition or execution authority.

Only the existing registry, contract compiler and NumericValue envelope are used.
SPECS is generated from the accepted matrix; numerical/state code is owned here.
"""
from __future__ import annotations

import collections.abc as abc
import decimal
import _decimal
import math

import pandas as pd

from app.ir import hashing, node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import common, contracts

# BEGIN accepted matrix facts plus sealed SAR mathematical-source addendum; do not hand-edit.
SPECS = node_contracts._freeze({'ACCUMULATION_DISTRIBUTION': {'constraints': ['volume >= 0'],
                               'decision': 'KEEP',
                               'dependencies': [],
                               'execution_form': 'RECURSIVE',
                               'first_valid_index': '0',
                               'formula': 'Cumulative sum of ((2*close-high-low)/(high-low))*volume; valid '
                                          'zero-range bars contribute 0.',
                               'inputs': ['high', 'low', 'close', 'volume'],
                               'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                                 'call. NaN/infinity/missing bar yields an invalid output and '
                                                 'restarts contiguous warmup; never substitute close, zero, prior '
                                                 'price or peer=open.',
                               'outputs': {'value': {'dtype': 'float64_series', 'units': 'signed_volume'}},
                               'parameters': {},
                               'refusal': None,
                               'seed': 'Accumulator 0 before first bar; first output includes first valid '
                                       'contribution.',
                               'session_reset': 'Carry across verified adjacent sessions within the same '
                                                'canonical instrument/timeframe/adjustment identity; do not reset '
                                                'ordinary rolling or recursive math just because the civil date '
                                                'changes. Reset on discontinuity, identity change or explicit '
                                                'reset.',
                               'source': 'TA:AD',
                               'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                                    'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                                    'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                                    'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                                    'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                                    'sha256:68c9e46064aa3a9db2e1d71997285b5f09d3d6a9d2264481fe8c84d62f5216c0'),
                               'threshold_class': 'RECURSIVE',
                               'variant': 'accumulation_distribution-v2',
                               'wave': 'recursive-state',
                               'zero_undefined_policy': 'A valid zero high-low range contributes exactly 0; '
                                                        'missing input is not zero-filled.'},
 'ADX': {'constraints': [],
         'decision': 'REPLACE_V2',
         'dependencies': [],
         'execution_form': 'RECURSIVE',
         'first_valid_index': '2*window - 1',
         'formula': 'Use the exact pinned TA_ADX directional-movement algorithm: strict up/down comparisons, '
                    'losing/tied movement zero, Wilder smoothing and its published initialization order. No '
                    'EMA-of-raw-differences approximation.',
         'inputs': ['high', 'low', 'close'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                           'never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'refusal': None,
         'seed': 'Pinned TA_ADX initialization with unstable period 0; capture every seed/intermediate state in '
                 'oracle vectors.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                          'math just because the civil date changes. Reset on discontinuity, identity change or '
                          'explicit reset.',
         'source': 'TA:ADX',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:a5c154b5268ef4e2b83dbac4932482870bfc7a70dba7d0c21b6e53a09395127f'),
         'threshold_class': 'RECURSIVE',
         'variant': 'adx-v2',
         'wave': 'recursive-state',
         'zero_undefined_policy': 'Use pinned TA_ADX zero-TR/zero-DX convention for valid constant input; missing '
                                  'data remains invalid.'},
 'ATR': {'constraints': [],
         'decision': 'REPLACE_V2',
         'dependencies': ['TRUE_RANGE'],
         'execution_form': 'RECURSIVE',
         'first_valid_index': 'window',
         'formula': 'Wilder average of TRUE_RANGE: seed with the first window TR values starting at input index '
                    '1, then (previous*(window-1)+TR)/window.',
         'inputs': ['high', 'low', 'close'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                           'never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'refusal': None,
         'seed': 'SMA of TR[1..window], first output at index window.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                          'math just because the civil date changes. Reset on discontinuity, identity change or '
                          'explicit reset.',
         'source': 'TA:ATR',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:e458e16023e92ecf67193af669d4142abf251c9da0be59bea2870cb0e217b637'),
         'threshold_class': 'RECURSIVE',
         'variant': 'atr-v2',
         'wave': 'recursive-state',
         'zero_undefined_policy': 'Valid constant bars yield ATR 0.'},
 'CHAIKIN_OSCILLATOR': {'constraints': ['fast_length < slow_length', 'volume >= 0'],
                        'decision': 'KEEP',
                        'dependencies': ['ACCUMULATION_DISTRIBUTION'],
                        'execution_form': 'RECURSIVE',
                        'first_valid_index': 'slow_length - 1',
                        'formula': 'Difference of the fast/slow EMA of accumulation-distribution using the pinned '
                                   'TA_ADOSC initialization, not an assumed shared SMA-seeded EMA shortcut.',
                        'inputs': ['high', 'low', 'close', 'volume'],
                        'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                          'NaN/infinity/missing bar yields an invalid output and restarts '
                                          'contiguous warmup; never substitute close, zero, prior price or '
                                          'peer=open.',
                        'outputs': {'value': {'dtype': 'float64_series', 'units': 'signed_volume'}},
                        'parameters': {'fast_length': {'default': 3,
                                                       'maximum': 4096,
                                                       'minimum': 2,
                                                       'type': 'exact_integer'},
                                       'slow_length': {'default': 10,
                                                       'maximum': 4096,
                                                       'minimum': 2,
                                                       'type': 'exact_integer'}},
                        'refusal': None,
                        'seed': 'Exact pinned TA_ADOSC seed order; independent vectors must distinguish it from '
                                'generic EMA seeding.',
                        'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                         'instrument/timeframe/adjustment identity; do not reset ordinary rolling '
                                         'or recursive math just because the civil date changes. Reset on '
                                         'discontinuity, identity change or explicit reset.',
                        'source': 'TA:ADOSC',
                        'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                             'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                             'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                             'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                             'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                             'sha256:051f690c4ef9c61c38287419dfeda989d9166d771dc14a87075daaffa46deb9e'),
                        'threshold_class': 'RECURSIVE',
                        'variant': 'chaikin_oscillator-v2',
                        'wave': 'recursive-state',
                        'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                 'never a finite substitute.'},
 'CUMULATIVE_RETURN': {'constraints': [],
                       'decision': 'REPLACE_V2',
                       'dependencies': [],
                       'execution_form': 'RECURSIVE',
                       'first_valid_index': '0',
                       'formula': 'close[t]/close[first_valid_segment_bar] - 1. The first valid segment bar is '
                                  'zero; subsequent missing bars reset the origin and invalidate the gap.',
                       'inputs': ['close'],
                       'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                         'NaN/infinity/missing bar yields an invalid output and restarts '
                                         'contiguous warmup; never substitute close, zero, prior price or '
                                         'peer=open.',
                       'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_return'}},
                       'parameters': {},
                       'refusal': None,
                       'seed': 'First valid close fixes the segment origin; retain it in the state snapshot.',
                       'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                        'instrument/timeframe/adjustment identity; do not reset ordinary rolling '
                                        'or recursive math just because the civil date changes. Reset on '
                                        'discontinuity, identity change or explicit reset.',
                       'source': 'SPEC',
                       'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                            'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                            'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                            'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                            'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                       'threshold_class': 'RECURSIVE',
                       'variant': 'cumulative_return-v2',
                       'wave': 'recursive-state',
                       'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                'never a finite substitute.'},
 'EMA': {'constraints': [],
         'decision': 'REPLACE_V2',
         'dependencies': [],
         'execution_form': 'RECURSIVE',
         'first_valid_index': 'window - 1',
         'formula': 'Seed with mean of the first window consecutive valid closes; thereafter '
                    'EMA[t]=EMA[t-1]+2/(window+1)*(close[t]-EMA[t-1]).',
         'inputs': ['close'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                           'never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'refusal': None,
         'seed': 'SMA seed at index window-1; no first-observation pandas seed.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                          'math just because the civil date changes. Reset on discontinuity, identity change or '
                          'explicit reset.',
         'source': 'TA:EMA',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:75249d5cd3475c21c1c87827e27cbddff6d841c2ada495138541a44f6571602b'),
         'threshold_class': 'RECURSIVE',
         'variant': 'ema-v2',
         'wave': 'recursive-state',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                  'substitute.'},
 'KAMA': {'constraints': ['fast_length < slow_length'],
          'decision': 'REPLACE_V2',
          'dependencies': [],
          'execution_form': 'RECURSIVE',
          'first_valid_index': 'window',
          'formula': 'Efficiency=abs(close[t]-close[t-window])/sum(abs(delta),window); when path length is zero '
                     'use efficiency 1 per pinned TA_KAMA. '
                     'SC=(efficiency*(2/(fast_length+1)-2/(slow_length+1))+2/(slow_length+1))^2. '
                     'KAMA[t]=previous+SC*(close[t]-previous).',
          'inputs': ['close'],
          'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                            'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                            'never substitute close, zero, prior price or peer=open.',
          'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
          'parameters': {'fast_length': {'default': 2, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'},
                         'slow_length': {'default': 30, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'},
                         'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
          'refusal': None,
          'seed': 'Use close[window-1] as previous KAMA; apply the first adaptive step at index window. The old '
                  'audit helper seeded close[window] and is not the target oracle.',
          'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                           'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                           'math just because the civil date changes. Reset on discontinuity, identity change or '
                           'explicit reset.',
          'source': 'TA:KAMA',
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                               'sha256:7fe1133b315bda5e5e3e36a8b5ac1d35cd423787c69c5d7d1e47ac4f5f81e77d'),
          'threshold_class': 'RECURSIVE',
          'variant': 'generalized_kama_talib_seed',
          'wave': 'recursive-state',
          'zero_undefined_policy': 'Zero path length uses efficiency 1; otherwise efficiency in [0,1]. Fast/slow '
                                   'extensions need independent scalar vectors; default 2/30 also matches pinned '
                                   'TA_KAMA.'},
 'MA_SLOPE': {'constraints': [],
              'decision': 'REPLACE_V2',
              'dependencies': ['EMA'],
              'execution_form': 'RECURSIVE',
              'first_valid_index': 'window',
              'formula': 'EMA(close,window)[t] - EMA(close,window)[t-1].',
              'inputs': ['close'],
              'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                'warmup; never substitute close, zero, prior price or peer=open.',
              'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units_per_bar'}},
              'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
              'refusal': None,
              'seed': 'EMA state plus previous EMA; no difference until two valid EMA outputs.',
              'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                               'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                               'recursive math just because the civil date changes. Reset on discontinuity, '
                               'identity change or explicit reset.',
              'source': 'SPEC',
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
              'threshold_class': 'RECURSIVE',
              'variant': 'ma_slope-v2',
              'wave': 'recursive-state',
              'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                       'finite substitute.'},
 'MINUS_DI': {'constraints': [],
              'decision': 'REPLACE_V2',
              'dependencies': [],
              'execution_form': 'RECURSIVE',
              'first_valid_index': 'window',
              'formula': 'Use the exact pinned TA_MINUS_DI directional-movement algorithm: strict up/down '
                         'comparisons, losing/tied movement zero, Wilder smoothing and its published '
                         'initialization order. No EMA-of-raw-differences approximation.',
              'inputs': ['high', 'low', 'close'],
              'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                'warmup; never substitute close, zero, prior price or peer=open.',
              'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
              'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
              'refusal': None,
              'seed': 'Pinned TA_MINUS_DI initialization with unstable period 0; capture every seed/intermediate '
                      'state in oracle vectors.',
              'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                               'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                               'recursive math just because the civil date changes. Reset on discontinuity, '
                               'identity change or explicit reset.',
              'source': 'TA:MINUS_DI',
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                   'sha256:6a5cb6ec74162b4ca996f0f0dadc6b2c4a0f191624c63ad95661d613a641a933'),
              'threshold_class': 'RECURSIVE',
              'variant': 'minus_di-v2',
              'wave': 'recursive-state',
              'zero_undefined_policy': 'Use pinned TA_MINUS_DI zero-TR/zero-DX convention for valid constant '
                                       'input; missing data remains invalid.'},
 'NATR': {'constraints': [],
          'decision': 'REPLACE_V2',
          'dependencies': ['ATR'],
          'execution_form': 'RECURSIVE',
          'first_valid_index': 'window',
          'formula': '100*ATR/close.',
          'inputs': ['high', 'low', 'close'],
          'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                            'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                            'never substitute close, zero, prior price or peer=open.',
          'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
          'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
          'refusal': None,
          'seed': 'ATR state and seed exactly as ATR.',
          'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                           'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                           'math just because the civil date changes. Reset on discontinuity, identity change or '
                           'explicit reset.',
          'source': 'TA:NATR',
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                               'sha256:3f20f409ce05334ec5d5441b7981455182a38ff39af571f63680703b01506be0'),
          'threshold_class': 'RECURSIVE',
          'variant': 'natr-v2',
          'wave': 'recursive-state',
          'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                   'substitute.'},
 'OBV': {'constraints': ['volume >= 0'],
         'decision': 'REPLACE_V2',
         'dependencies': [],
         'execution_form': 'RECURSIVE',
         'first_valid_index': '0',
         'formula': 'Seed with volume[0]. Add current volume when close rises, subtract when it falls, retain on '
                    'equality.',
         'inputs': ['close', 'volume'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                           'never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'signed_volume'}},
         'parameters': {},
         'refusal': None,
         'seed': 'First valid volume, not zero.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                          'math just because the civil date changes. Reset on discontinuity, identity change or '
                          'explicit reset.',
         'source': 'TA:OBV',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:d127644132af3f5453b8e77507f6dd924df2864a47f4a553608d753a6ed4b2c6'),
         'threshold_class': 'RECURSIVE',
         'variant': 'obv-v2',
         'wave': 'recursive-state',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                  'substitute.'},
 'PARABOLIC_SAR': {'constraints': ['0 < start <= maximum', '0 < increment <= maximum'],
                   'decision': 'REPLACE_V2',
                   'dependencies': [],
                   'execution_form': 'RECURSIVE',
                   'first_valid_index': '1',
                   'formula': 'Use pinned TA_SAR initial direction, extreme point, reversal and two-bar clamp '
                              'ordering. Generalize initial AF=start and subsequent AF increment=increment, '
                              'capped at maximum; reset AF=start on reversal.',
                   'inputs': ['high', 'low'],
                   'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                     'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                     'warmup; never substitute close, zero, prior price or peer=open.',
                   'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                   'parameters': {'increment': {'default': 0.02,
                                                'maximum': 1,
                                                'minimum': 0,
                                                'type': 'finite_number'},
                                  'maximum': {'default': 0.2, 'maximum': 1, 'minimum': 0, 'type': 'finite_number'},
                                  'start': {'default': 0.02, 'maximum': 1, 'minimum': 0, 'type': 'finite_number'}},
                   'refusal': None,
                   'seed': 'Pinned TA_SAR two-bar initialization; all EP/AF/direction/prior-high-low state must '
                           'be serialized.',
                   'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                    'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                    'recursive math just because the civil date changes. Reset on discontinuity, '
                                    'identity change or explicit reset.',
                   'source': 'SPEC',
                   'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb', 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482', 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925', 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994', 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3', 'sha256:b025f526992ba240b329d2ef5124cc73dcb9c4e5970a12e812ad2f863ec8ea5a', 'sha256:4d5d654326d8665fc94f44aaf08736305d59843e2cd9ecbd726de143ebec5e0e'),
                   'threshold_class': 'RECURSIVE',
                   'variant': 'parabolic_sar-mathematical-v2',
                   'wave': 'recursive-state',
                   'zero_undefined_policy': 'Equal highs/lows, direction, reversals and two-bar clamps follow the pinned SAR ordering under the explicitly declared Strategy OS mathematical recurrence. This mathematical variant makes no universal binary64 TA-Lib parity claim, including when start=increment. Preserve native comparisons and every raw failure separately; use the unchanged strict mathematical thresholds and exact validity masks.'},
 'PLUS_DI': {'constraints': [],
             'decision': 'REPLACE_V2',
             'dependencies': [],
             'execution_form': 'RECURSIVE',
             'first_valid_index': 'window',
             'formula': 'Use the exact pinned TA_PLUS_DI directional-movement algorithm: strict up/down '
                        'comparisons, losing/tied movement zero, Wilder smoothing and its published '
                        'initialization order. No EMA-of-raw-differences approximation.',
             'inputs': ['high', 'low', 'close'],
             'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                               'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                               'never substitute close, zero, prior price or peer=open.',
             'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
             'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
             'refusal': None,
             'seed': 'Pinned TA_PLUS_DI initialization with unstable period 0; capture every seed/intermediate '
                     'state in oracle vectors.',
             'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                              'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                              'recursive math just because the civil date changes. Reset on discontinuity, '
                              'identity change or explicit reset.',
             'source': 'TA:PLUS_DI',
             'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                  'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                  'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                  'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                  'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                  'sha256:301eae5460813f8bce3653632f5432775348ebedd2c6cad96110fe4c41c904fa'),
             'threshold_class': 'RECURSIVE',
             'variant': 'plus_di-v2',
             'wave': 'recursive-state',
             'zero_undefined_policy': 'Use pinned TA_PLUS_DI zero-TR/zero-DX convention for valid constant input; '
                                      'missing data remains invalid.'},
 'PRICE_MA_DISTANCE': {'constraints': [],
                       'decision': 'REPLACE_V2',
                       'dependencies': ['EMA'],
                       'execution_form': 'RECURSIVE',
                       'first_valid_index': 'window - 1',
                       'formula': 'close[t] - EMA(close,window)[t].',
                       'inputs': ['close'],
                       'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                         'NaN/infinity/missing bar yields an invalid output and restarts '
                                         'contiguous warmup; never substitute close, zero, prior price or '
                                         'peer=open.',
                       'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                       'parameters': {'window': {'default': 14,
                                                 'maximum': 4096,
                                                 'minimum': 2,
                                                 'type': 'exact_integer'}},
                       'refusal': None,
                       'seed': 'EMA seed/state.',
                       'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                        'instrument/timeframe/adjustment identity; do not reset ordinary rolling '
                                        'or recursive math just because the civil date changes. Reset on '
                                        'discontinuity, identity change or explicit reset.',
                       'source': 'SPEC',
                       'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                            'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                            'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                            'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                            'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                       'threshold_class': 'RECURSIVE',
                       'variant': 'price_ma_distance-v2',
                       'wave': 'recursive-state',
                       'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                'never a finite substitute.'},
 'PRICE_VOLUME_TREND': {'constraints': ['volume >= 0'],
                        'decision': 'REPLACE_V2',
                        'dependencies': [],
                        'execution_form': 'RECURSIVE',
                        'first_valid_index': '0',
                        'formula': 'Accumulator starts at zero on the first valid price/volume bar. Thereafter '
                                   'add (close[t]/close[t-1]-1)*volume[t].',
                        'inputs': ['close', 'volume'],
                        'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                          'NaN/infinity/missing bar yields an invalid output and restarts '
                                          'contiguous warmup; never substitute close, zero, prior price or '
                                          'peer=open.',
                        'outputs': {'value': {'dtype': 'float64_series', 'units': 'signed_volume'}},
                        'parameters': {},
                        'refusal': None,
                        'seed': 'Accumulator=0 and previous close=first valid close.',
                        'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                         'instrument/timeframe/adjustment identity; do not reset ordinary rolling '
                                         'or recursive math just because the civil date changes. Reset on '
                                         'discontinuity, identity change or explicit reset.',
                        'source': 'SPEC',
                        'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                             'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                             'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                             'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                             'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                        'threshold_class': 'RECURSIVE',
                        'variant': 'price_volume_trend-v2',
                        'wave': 'recursive-state',
                        'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                 'never a finite substitute.'},
 'RMA_WILDER': {'constraints': [],
                'decision': 'REPLACE_V2',
                'dependencies': [],
                'execution_form': 'RECURSIVE',
                'first_valid_index': 'window - 1',
                'formula': 'Seed with SMA(window); thereafter (previous*(window-1)+current)/window.',
                'inputs': ['close'],
                'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                  'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                  'warmup; never substitute close, zero, prior price or peer=open.',
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                'refusal': None,
                'seed': 'First window consecutive valid observations form the SMA seed.',
                'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                 'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                 'recursive math just because the civil date changes. Reset on discontinuity, '
                                 'identity change or explicit reset.',
                'source': 'SPEC',
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                'threshold_class': 'RECURSIVE',
                'variant': 'rma_wilder-v2',
                'wave': 'recursive-state',
                'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                         'finite substitute.'},
 'RSI': {'constraints': [],
         'decision': 'REPLACE_V2',
         'dependencies': [],
         'execution_form': 'RECURSIVE',
         'first_valid_index': 'window',
         'formula': 'Average gains/losses from window consecutive changes using the pinned TA_RSI default/Wilder '
                    'recurrence; output 100*average_gain/(average_gain+average_loss).',
         'inputs': ['close'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous warmup; '
                           'never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'refusal': None,
         'seed': 'SMA of gains/losses from changes 1..window, then Wilder updates.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or recursive '
                          'math just because the civil date changes. Reset on discontinuity, identity change or '
                          'explicit reset.',
         'source': 'TA:RSI',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:43845aa0e206e12551ee087a4d34a212cac8c5827eb9949f25e3e7772dfaa9a8'),
         'threshold_class': 'RECURSIVE',
         'variant': 'rsi-v2',
         'wave': 'recursive-state',
         'zero_undefined_policy': 'If both average gain and loss are zero, output 0 per pinned TA_RSI; positive '
                                  'gain and zero loss gives 100.'}})
# END accepted matrix facts.
NAMES = tuple(sorted(SPECS))

def component_key(name):
    if name not in SPECS:
        raise node_contracts.NodeContractRefusal("RECURSIVE_COMPONENT_UNAVAILABLE")
    return ("analytical." + name.lower(), 2)

def parameters_for(name, parameters=None):
    """Validate before defaults: no bool-as-int, ignored knobs or fallback source."""
    component_key(name)
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, abc.Mapping) or set(parameters) - set(SPECS[name]["parameters"]):
        raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETERS_UNKNOWN")
    result = {}
    for key, spec in SPECS[name]["parameters"].items():
        value = parameters.get(key, spec["default"])
        if spec["type"] in {"exact_integer", "enum"}:
            if type(value) is not int:
                raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_NOT_EXACT_INTEGER")
        elif type(value) not in {int, float} or not math.isfinite(value):
            raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_NOT_FINITE")
        if spec["type"] == "enum":
            if value not in spec["values"]:
                raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_OUT_OF_DOMAIN")
        elif not spec["minimum"] <= value <= spec["maximum"]:
            raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_OUT_OF_DOMAIN")
        # Canonical parameter bytes belong to the resolver. Numerically equal
        # integers/floats can have different receipt identities; preserve them.
        result[key] = value
    if name in {"KAMA", "CHAIKIN_OSCILLATOR"} and not result["fast_length"] < result["slow_length"]:
        raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_RELATION")
    if name == "PARABOLIC_SAR" and not (0 < result["start"] <= result["maximum"] and
                                         0 < result["increment"] <= result["maximum"]):
        raise node_contracts.NodeContractRefusal("RECURSIVE_PARAMETER_RELATION")
    return node_contracts._freeze(result)

def fields_by_port(name):
    fields = SPECS[name]["inputs"]
    result = {"frame": tuple(sorted(field.upper() for field in fields if field != "peer"))}
    if "peer" in fields:
        result["peer"] = ("CLOSE",)
    return node_contracts._freeze(result)

def _port(name, direction, type_id):
    result = {"port_id": name, "direction": direction, "semantic_flow": "value",
              "semantic_role": "market_frame" if direction == "input" else "analytical_value",
              "type_ref": {"type_id": type_id, "type_version": 2}, "shape": "series"}
    if direction == "input":
        result["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return result

def _type_id(name, output):
    dtype = SPECS[name]["outputs"][output]["dtype"]
    return "analytical.boolean" if dtype == "nullable_boolean_series" else "analytical.float64"

def descriptor(name):
    key = component_key(name)
    parameters = {}
    for field, spec in SPECS[name]["parameters"].items():
        parameters[field] = {
            "type": "float" if spec["type"] == "finite_number" else "int",
            "required": False, "default": spec["default"],
            "enum": list(spec["values"]) if spec["type"] == "enum" else None,
            "domain": ({"minimum": min(spec["values"]), "maximum": max(spec["values"])}
                       if spec["type"] == "enum" else {"minimum": spec["minimum"], "maximum": spec["maximum"]}),
            "units": "bars" if field in {"window", "fast_length", "slow_length"} else "acceleration_factor",
            "serialization": "canonical-json",
        }
    return node_contracts._freeze({"component_id": key[0], "component_version": 2,
                    "domain_family": "indicator", "structural_role": "transform",
                    "ports": [_port(port, "input", "analytical.market_frame") for port in fields_by_port(name)] +
                             [_port(port, "output", _type_id(name, port)) for port in sorted(SPECS[name]["outputs"])],
                    "parameters": parameters})

def _check_bound(name, parameters, bound):
    if not isinstance(bound, contracts.ResolvedNodeContract):
        raise node_contracts.NodeContractRefusal("RECURSIVE_VERIFIED_BINDING_REQUIRED")
    doc = bound.document
    replayed = contracts.materialize_node_contract(source_contract(name), _binding_registration(name),
                                                  parameters, doc["input_binding"])
    if replayed.bound_contract_address != bound.bound_contract_address:
        raise node_contracts.NodeContractRefusal("RECURSIVE_BINDING_REPLAY_MISMATCH")
    key = component_key(name)
    if (dict(doc["component"]) != {"component_id": key[0], "component_version": 2}
            or dict(doc["parameters"]) != dict(parameters)
            or doc["source_contract_address"] != hashing.content_address(node_contracts._plain(source_contract(name)))
            or doc["resolved_contract"]["warmup_history"] != first_valid_index(name, parameters)
            or dict(doc["resolved_contract"]["output_warmup"]) !=
            {port: first_valid_index(name, parameters) for port in SPECS[name]["outputs"]}):
        raise node_contracts.NodeContractRefusal("RECURSIVE_BINDING_MISMATCH")
    _check_bound_inputs(name, doc["input_binding"]["ports"])


def _check_bound_inputs(name, ports):
    if set(ports) != set(fields_by_port(name)):
        raise node_contracts.NodeContractRefusal("RECURSIVE_ROLE_MISMATCH")
    primary = ports["frame"]["binding"]
    for port, fields in fields_by_port(name).items():
        fact = ports[port]["binding"]
        if (port != "frame" and fact["instrument"]["role"] != port
                or not set(fields) <= set(fact["fields"])
                or fact["timeframe"] != primary["timeframe"]
                or dict(fact["alignment"]) != {"kind": "EXACT", "maximum_skew_seconds": 0}):
            raise node_contracts.NodeContractRefusal("RECURSIVE_ALIGNED_FIELDS_REQUIRED")

def _timestamp(value):
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError("timezone required")
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        raise node_contracts.NodeContractRefusal("RECURSIVE_CANONICAL_TIME_REQUIRED") from exc


def first_valid_index(name, parameters=None):
    values = parameters_for(name, parameters)
    rule = SPECS[name]["first_valid_index"]
    if rule == "window":
        return values["window"]
    if rule == "window - 1":
        return values["window"] - 1
    if rule == "2*window - 1":
        return 2 * values["window"] - 1
    if rule == "slow_length - 1":
        return values["slow_length"] - 1
    return int(rule)


def _binding_rule(name):
    specs = tuple((key, spec["type"], spec["minimum"], spec["maximum"])
                  for key, spec in sorted(SPECS[name]["parameters"].items()))
    fields = tuple(fields_by_port(name).items())
    rule = SPECS[name]["first_valid_index"]
    relation = ("ordered_lengths" if name in {"KAMA", "CHAIKIN_OSCILLATOR"} else
                "positive_sar" if name == "PARABOLIC_SAR" else "none")
    builder = contracts.binding_result

    def bind(parameters, inputs, _spec=(specs, fields, rule, relation, builder)):
        specs, fields, rule, relation, builder = _spec
        if set(parameters) != {row[0] for row in specs}:
            raise ValueError("exact canonical parameters required")
        for key, kind, minimum, maximum in specs:
            value = parameters[key]
            if kind == "exact_integer":
                if type(value) is not int:
                    raise ValueError("exact integer required")
            elif type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("finite number required")
            if not minimum <= value <= maximum:
                raise ValueError("parameter bounds")
        if relation == "ordered_lengths" and not parameters["fast_length"] < parameters["slow_length"]:
            raise ValueError("fast must precede slow")
        if relation == "positive_sar" and not (0 < parameters["start"] <= parameters["maximum"] and
                                                0 < parameters["increment"] <= parameters["maximum"]):
            raise ValueError("positive bounded SAR factors required")
        history = (parameters["window"] if rule == "window" else
                   parameters["window"] - 1 if rule == "window - 1" else
                   2 * parameters["window"] - 1 if rule == "2*window - 1" else
                   parameters["slow_length"] - 1 if rule == "slow_length - 1" else int(rule))
        return builder(inputs, fields_by_port=dict(fields), warmup_history=history,
                       output_warmup={"value": history})

    return bind


def source_contract(name):
    key = component_key(name)
    rule = {"rule_id": key[0] + ".binding", "rule_version": 1}
    fields = fields_by_port(name)
    slots = 8192 if name == "ADX" else 4097 if "window" in SPECS[name]["parameters"] else (
        4096 if name == "CHAIKIN_OSCILLATOR" else first_valid_index(name) + 1)
    width = len(SPECS[name]["inputs"])
    # Fixed-precision accumulators and the sole KAMA ring are bounded. Include
    # encoding/working space; validate these ceilings with measured receipts.
    profile = {"compute_microseconds_per_event": 200000,
               "memory_bytes_upper_bound": 1048576 + slots * width * 512,
               "history_bytes_upper_bound": 65536 + slots * width * 128,
               "state_bytes_upper_bound": 131072 + slots * width * 128,
               "storage_bytes_per_day_upper_bound": 0,
               "subscription_count_upper_bound": 1, "fanout_upper_bound": 1}
    return node_contracts._freeze({
        "schema": "first-party-node-contract/2", "stable_node_id": key[0], "semantic_version": 2,
        "visible_family": "TYPE_2", "input_types": {"frame": "analytical.market_frame/series"},
        "output_types": {"value": "analytical.float64/series"},
        "required_market_fields": sorted(SPECS[name]["inputs"]),
        "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
        "warmup_history": rule, "execution_form": "RECURSIVE",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": ["DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE"]},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE", "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX", "evaluation_triggers": ["completed_bar"],
        "streaming_support": True, "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [], "resource_profile": profile,
        "reference_provenance": sorted(set(SPECS[name]["source_addresses"] +
                                            (hashing.content_address(node_contracts._plain(SPECS[name])),))),
        "parameter_binding": {"scheme": "analytical-contract-binding/1", **rule,
                              "parameter_names": sorted(SPECS[name]["parameters"]), "input_ports": ["frame"]},
    })


def _precision_context():
    # Finite binary64 input differences can span 632 decimal orders. PVT can
    # multiply their ratio by volume, spanning 1264 orders against subnormals.
    # Keep fixed, bounded headroom without inheriting the caller's context.
    return _decimal.Context(prec=1536, rounding=decimal.ROUND_HALF_EVEN,
                           Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[],
                           traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow])


def _d(value):
    return decimal.Decimal.from_float(float(value))


def _native_zero(value):
    # Pinned ta_utility.h TA_EPSILON is 1e-14, with STRICT comparisons.
    # Only ADX/DI specify this native zero convention. RSI/KAMA explicitly use
    # mathematical zero in the accepted contract and do not call this helper.
    return abs(value) < _d(1e-14)


def _numeric_keys(name):
    if name in {"EMA", "RMA_WILDER", "MA_SLOPE", "PRICE_MA_DISTANCE"}:
        return ("sum", "mean")
    if name in {"ATR", "NATR"}:
        return ("sum", "atr")
    if name == "RSI":
        return ("gain", "loss")
    if name in {"ADX", "PLUS_DI", "MINUS_DI"}:
        return ("plus", "minus", "tr", "dx_sum", "adx")
    if name == "KAMA":
        return ("path", "mean")
    if name == "PARABOLIC_SAR":
        return ("sar", "ep", "af")
    if name == "CHAIKIN_OSCILLATOR":
        return ("ad", "fast", "slow")
    if name == "CUMULATIVE_RETURN":
        return ("origin",)
    return ("total",)


class RecursiveState:
    """One bounded, causal state for one compiler-verified input identity.

    Only KAMA stores a window. All other recurrences store fixed accumulators,
    one prior bar and a capped warmup counter. Ordinary session transitions carry
    state; the canonical data producer distinguishes DATA_GAP from a closure.
    """

    def __init__(self, name, parameters, bound_contract):
        self.name = name
        self.parameters = parameters_for(name, parameters)
        _check_bound(name, self.parameters, bound_contract)
        self.bound_contract = bound_contract
        self.first = first_valid_index(name, self.parameters)
        self._last_time = None
        self._clear()

    def _clear(self):
        self._seen = 0
        self._previous = {}
        self._numbers = {key: decimal.Decimal(0) for key in _numeric_keys(self.name)}
        self._history = []
        self._poisoned = False
        self._long = True

    def _sar(self, row, previous, n):
        state, p = self._numbers, self.parameters
        high, low = row["high"], row["low"]
        if n == 1:
            # TA_MINUS_DM(period=1): strict losing/tied direction contributes 0.
            up, down = high - previous["high"], previous["low"] - low
            self._long = not (down > 0 and down > up)
            state["ep"] = high if self._long else low
            state["sar"] = previous["low"] if self._long else previous["high"]
            state["af"] = _d(p["start"])
            # TA_SAR primes newHigh/newLow to bar 1 BEFORE its first loop,
            # so both clamp references at the first output are bar 1.
            previous = row
        sar, ep, af = state["sar"], state["ep"], state["af"]
        reversal = low <= sar if self._long else high >= sar
        if reversal:
            self._long = not self._long
            sar = min(ep, previous["low"], low) if self._long else max(ep, previous["high"], high)
            ep = high if self._long else low
            af = _d(p["start"])
        else:
            new_extreme = high > ep if self._long else low < ep
            if new_extreme:
                ep = high if self._long else low
                af = min(af + _d(p["increment"]), _d(p["maximum"]))
        output = sar
        sar += af * (ep - sar)
        sar = min(sar, previous["low"], low) if self._long else max(sar, previous["high"], high)
        state.update(sar=sar, ep=ep, af=af)
        return output

    def _advance(self, raw):
        row = {key: _d(value) for key, value in raw.items()}
        previous = {key: _d(value) for key, value in self._previous.items()}
        s, p, n, name = self._numbers, self.parameters, self._seen, self.name
        w = p.get("window", 0)
        close = row.get("close")
        zero = decimal.Decimal(0)
        if name in {"ACCUMULATION_DISTRIBUTION", "CHAIKIN_OSCILLATOR"}:
            spread = row["high"] - row["low"]
            contribution = zero if spread == 0 else ((close - row["low"]) - (row["high"] - close)) / spread * row["volume"]
            if name == "ACCUMULATION_DISTRIBUTION":
                s["total"] += contribution
                return s["total"]
            s["ad"] += contribution
            if n == 0:
                s["fast"] = s["slow"] = s["ad"]
            else:
                s["fast"] += decimal.Decimal(2) / (p["fast_length"] + 1) * (s["ad"] - s["fast"])
                s["slow"] += decimal.Decimal(2) / (p["slow_length"] + 1) * (s["ad"] - s["slow"])
            return s["fast"] - s["slow"]
        if name == "CUMULATIVE_RETURN":
            if n == 0:
                s["origin"] = close
            return None if s["origin"] == 0 else (close - s["origin"]) / s["origin"]
        if name == "OBV":
            if n == 0:
                s["total"] = row["volume"]
            elif close != previous["close"]:
                s["total"] += row["volume"] if close > previous["close"] else -row["volume"]
            return s["total"]
        if name == "PRICE_VOLUME_TREND":
            if n:
                if previous["close"] == 0:
                    self._poisoned = True
                elif not self._poisoned:
                    s["total"] += (close - previous["close"]) / previous["close"] * row["volume"]
            # An undefined cumulative addend cannot be silently dropped. Only a
            # declared reset or invalid input starts another cumulative segment.
            return None if self._poisoned else s["total"]
        if name in {"EMA", "RMA_WILDER", "MA_SLOPE", "PRICE_MA_DISTANCE"}:
            old = s["mean"]
            if n < w:
                s["sum"] += close
                if n == w - 1:
                    s["mean"] = s["sum"] / w
                    s["sum"] = zero
            elif name == "RMA_WILDER":
                s["mean"] = (old * (w - 1) + close) / w
            else:
                s["mean"] = old + decimal.Decimal(2) / (w + 1) * (close - old)
            return (s["mean"] - old if name == "MA_SLOPE" else
                    close - s["mean"] if name == "PRICE_MA_DISTANCE" else s["mean"])
        if name == "KAMA":
            if n:
                s["path"] += abs(close - previous["close"])
            self._history.append(raw["close"])
            if len(self._history) > w + 1:
                s["path"] -= abs(_d(self._history[1]) - _d(self._history[0]))
                del self._history[0]
            if n < w:
                s["mean"] = close
                return None
            efficiency = decimal.Decimal(1) if s["path"] == 0 else abs(close - _d(self._history[0])) / s["path"]
            fast, slow = decimal.Decimal(2) / (p["fast_length"] + 1), decimal.Decimal(2) / (p["slow_length"] + 1)
            smoothing = (efficiency * (fast - slow) + slow) ** 2
            s["mean"] += smoothing * (close - s["mean"])
            return s["mean"]
        if n == 0:
            return None
        if name == "PARABOLIC_SAR":
            return self._sar(row, previous, n)
        if name == "RSI":
            delta = close - previous["close"]
            gain, loss = max(delta, zero), max(-delta, zero)
            if n <= w:
                s["gain"] += gain
                s["loss"] += loss
                if n == w:
                    s["gain"] /= w
                    s["loss"] /= w
            else:
                s["gain"] = (s["gain"] * (w - 1) + gain) / w
                s["loss"] = (s["loss"] * (w - 1) + loss) / w
            denominator = s["gain"] + s["loss"]
            return zero if denominator == 0 else 100 * s["gain"] / denominator
        tr = max(row["high"] - row["low"], abs(row["high"] - previous["close"]), abs(row["low"] - previous["close"]))
        if name in {"ATR", "NATR"}:
            if n <= w:
                s["sum"] += tr
                if n == w:
                    s["atr"] = s["sum"] / w
                    s["sum"] = zero
            else:
                s["atr"] = (s["atr"] * (w - 1) + tr) / w
            return s["atr"] if name == "ATR" else None if close == 0 else 100 * s["atr"] / close
        if name in {"PLUS_DI", "MINUS_DI", "ADX"}:
            up, down = row["high"] - previous["high"], previous["low"] - row["low"]
            plus = up if up > 0 and up > down else zero
            minus = down if down > 0 and down > up else zero
            if n < w:
                s["plus"] += plus
                s["minus"] += minus
                s["tr"] += tr
                return None
            s["plus"] = s["plus"] - s["plus"] / w + plus
            s["minus"] = s["minus"] - s["minus"] / w + minus
            s["tr"] = s["tr"] - s["tr"] / w + tr
            plus_di = zero if _native_zero(s["tr"]) else 100 * s["plus"] / s["tr"]
            minus_di = zero if _native_zero(s["tr"]) else 100 * s["minus"] / s["tr"]
            if name != "ADX":
                return plus_di if name == "PLUS_DI" else minus_di
            dx = None if _native_zero(plus_di + minus_di) else 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            if n < 2 * w:
                s["dx_sum"] += zero if dx is None else dx
                if n == 2 * w - 1:
                    s["adx"] = s["dx_sum"] / w
                    s["dx_sum"] = zero
            elif dx is not None:
                s["adx"] = (s["adx"] * (w - 1) + dx) / w
            return s["adx"]
        raise node_contracts.NodeContractRefusal("RECURSIVE_COMPONENT_UNAVAILABLE")

    def step(self, inputs, *, event_time, reset_reasons=(), event_kind="completed_bar"):
        if event_kind != "completed_bar":
            raise node_contracts.NodeContractRefusal("RECURSIVE_COMPLETED_BAR_REQUIRED")
        timestamp = _timestamp(event_time)
        if self._last_time is not None and timestamp <= self._last_time:
            raise node_contracts.NodeContractRefusal("RECURSIVE_EVENT_ORDER")
        reasons = common.contract_reset_reasons(self.bound_contract, reset_reasons)
        if not isinstance(inputs, abc.Mapping) or set(inputs) != {"frame"}:
            raise node_contracts.NodeContractRefusal("RECURSIVE_INPUT_PORTS")
        if not isinstance(inputs["frame"], abc.Mapping):
            raise node_contracts.NodeContractRefusal("RECURSIVE_NAMED_FIELDS_REQUIRED")
        cells = {field: common.required_numeric_scalar(inputs["frame"], field) for field in SPECS[self.name]["inputs"]}
        bad = validity.propagate(cells.values())
        if bad is None:
            raw = {key: cell.value for key, cell in cells.items()}
            if ("volume" in raw and raw["volume"] < 0 or
                    "high" in raw and "low" in raw and (raw["high"] < raw["low"] or
                    "close" in raw and not raw["low"] <= raw["close"] <= raw["high"])):
                bad = validity.invalid(validity.ValidityState.INVALID)
        self._last_time = timestamp
        if reasons or bad is not None:
            self._clear()
        if bad is not None:
            return {"value": bad}
        n = self._seen
        with decimal.localcontext(_precision_context()):
            number = self._advance(raw)
        self._previous = raw
        self._seen = min(self._seen + 1, self.first + 1)
        if n < self.first:
            return {"value": validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY)}
        if number is None or not math.isfinite(float(number)):
            return {"value": validity.invalid(validity.ValidityState.MATHEMATICALLY_UNDEFINED)}
        return {"value": validity.valid(float(number))}

    def snapshot(self):
        # Numerical payload for the existing bound-state transport at integration;
        # this checksum is not a substitute for that transport's authority proof.
        body = {"schema": "analytical-recursive-state/2", "component": list(component_key(self.name)),
                "bound_contract_address": self.bound_contract.bound_contract_address,
                "parameters": node_contracts._plain(self.parameters),
                "last_time": self._last_time.isoformat() if self._last_time is not None else None,
                "seen": self._seen, "previous": dict(self._previous), "history": list(self._history),
                "numbers": {key: str(value) for key, value in self._numbers.items()},
                "poisoned": self._poisoned, "long": self._long}
        return {**body, "payload_address": hashing.content_address(body)}

    @classmethod
    def restore(cls, name, parameters, bound_contract, document):
        state = cls(name, parameters, bound_contract)
        fields = {"schema", "component", "bound_contract_address", "parameters", "last_time", "seen", "previous", "history", "numbers", "poisoned", "long", "payload_address"}
        if not isinstance(document, abc.Mapping) or set(document) != fields:
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_CLOSED_SCHEMA")
        body = {key: value for key, value in document.items() if key != "payload_address"}
        if not isinstance(document["parameters"], abc.Mapping) or set(document["parameters"]) != set(state.parameters):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_PARAMETERS")
        parameters_for(name, document["parameters"])
        if (document["schema"] != "analytical-recursive-state/2" or
                document["component"] != list(component_key(name)) or
                document["bound_contract_address"] != bound_contract.bound_contract_address or
                hashing.content_address(document["parameters"]) != hashing.content_address(dict(state.parameters))):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_IDENTITY")
        seen = document["seen"]
        if type(seen) is not int or not 0 <= seen <= state.first + 1:
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_COUNTER")
        previous, history, numbers = document["previous"], document["history"], document["numbers"]
        expected_previous = set(SPECS[name]["inputs"]) if seen else set()
        if (not isinstance(previous, abc.Mapping) or set(previous) != expected_previous or
                any(type(v) not in {int, float} or not math.isfinite(v) for v in previous.values())):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_PREVIOUS")
        if ("volume" in previous and previous["volume"] < 0 or
                "high" in previous and (previous["high"] < previous["low"] or
                "close" in previous and not previous["low"] <= previous["close"] <= previous["high"])):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_PREVIOUS")
        expected_length = seen if name == "KAMA" else 0
        if (not isinstance(history, list) or len(history) != expected_length or
                any(type(v) not in {int, float} or not math.isfinite(v) for v in history) or
                history and history[-1] != previous["close"]):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_HISTORY")
        if not isinstance(numbers, abc.Mapping) or set(numbers) != set(_numeric_keys(name)):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_NUMBERS")
        decoded = {}
        for key, value in numbers.items():
            if not isinstance(value, str) or len(value) > 1560:
                raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_DECIMAL")
            try:
                parsed = decimal.Decimal(value)
                if (not parsed.is_finite() or len(parsed.as_tuple().digits) > 1536 or
                        abs(parsed.as_tuple().exponent) > 1001534 or str(parsed) != value):
                    raise ValueError("bounded canonical decimal required")
            except (decimal.DecimalException, ValueError) as exc:
                raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_DECIMAL") from exc
            decoded[key] = parsed
        if (type(document["poisoned"]) is not bool or type(document["long"]) is not bool or
                name != "PRICE_VOLUME_TREND" and document["poisoned"] or
                name != "PARABOLIC_SAR" and not document["long"]):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_FLAGS")
        if seen and document["last_time"] is None:
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_CLOCK")
        if not seen and (any(decoded.values()) or document["poisoned"] or not document["long"]):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_EMPTY")
        if name in {"RSI", "ADX", "PLUS_DI", "MINUS_DI", "ATR", "NATR"} and any(v < 0 for v in decoded.values()):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_DOMAIN")
        if name == "KAMA":
            with decimal.localcontext(_precision_context()):
                path = sum((abs(_d(b) - _d(a)) for a, b in zip(history, history[1:])), decimal.Decimal(0))
            if decoded["path"] != path:
                raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_PATH")
        if name == "PARABOLIC_SAR" and seen > 1 and not _d(state.parameters["start"]) <= decoded["af"] <= _d(state.parameters["maximum"]):
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_ACCELERATION")
        try:
            if document["payload_address"] != hashing.content_address(body):
                raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_DIGEST")
        except (TypeError, ValueError) as exc:
            raise node_contracts.NodeContractRefusal("RECURSIVE_STATE_DIGEST") from exc
        state._last_time = _timestamp(document["last_time"]) if document["last_time"] is not None else None
        state._seen, state._previous, state._history = seen, dict(previous), list(history)
        state._numbers, state._poisoned, state._long = decoded, document["poisoned"], document["long"]
        return state


def evaluate(name, parameters, inputs, *, bound_contract, resets=None):
    """Complete named arrays; supplied indexes denote completed-bar availability."""
    state = RecursiveState(name, parameters, bound_contract)
    fields = fields_by_port(name)
    if not isinstance(inputs, abc.Mapping) or set(inputs) != set(fields):
        raise node_contracts.NodeContractRefusal("RECURSIVE_INPUT_PORTS")
    index = None
    columns = {}
    for port, required in fields.items():
        frame = inputs[port]
        if not isinstance(frame, abc.Mapping):
            raise node_contracts.NodeContractRefusal("RECURSIVE_NAMED_FIELDS_REQUIRED")
        for field in required:
            key = field.lower()
            if key not in frame or not isinstance(frame[key], pd.Series):
                raise node_contracts.NodeContractRefusal("RECURSIVE_INDEXED_FIELD_REQUIRED")
            series = frame[key]
            if not isinstance(series.index, pd.DatetimeIndex) or series.index.tz is None or series.index.hasnans or not series.index.is_unique or not series.index.is_monotonic_increasing:
                raise node_contracts.NodeContractRefusal("RECURSIVE_CANONICAL_INDEX_REQUIRED")
            if index is None:
                index = series.index
            if not series.index.equals(index):
                raise node_contracts.NodeContractRefusal("RECURSIVE_EXACT_ALIGNMENT_REQUIRED")
            columns[(port, key)] = series.tolist()
    if resets is None:
        resets = ((),) * len(index)
    if not isinstance(resets, (tuple, list)) or len(resets) != len(index):
        raise node_contracts.NodeContractRefusal("RECURSIVE_RESET_ARRAY_REQUIRED")
    results = {port: [] for port in sorted(SPECS[name]["outputs"])}
    for i, event_time in enumerate(index):
        row = {port: {field.lower(): columns[(port, field.lower())][i] for field in required} for port, required in fields.items()}
        produced = state.step(row, event_time=event_time, reset_reasons=resets[i])
        for port, value in produced.items():
            results[port].append(value)
    return {port: pd.Series(values, index=index, name=port, dtype=object) for port, values in results.items()}


def implementation_for(name):
    def implementation(parameters, inputs, *, evaluation_context=None, _name=name):
        if not isinstance(evaluation_context, abc.Mapping) or not {"bound_contract"} <= set(evaluation_context) or set(evaluation_context) - {"bound_contract", "resets"}:
            raise node_contracts.NodeContractRefusal("RECURSIVE_VERIFIED_EVALUATION_CONTEXT_REQUIRED")
        return evaluate(_name, parameters, inputs, bound_contract=evaluation_context["bound_contract"], resets=evaluation_context.get("resets"))
    return implementation


def _binding_registration(name):
    # The whole immutable defining module enters the binding identity. Therefore
    # changing numerical, validity or restart code also invalidates old bound
    # contracts and state, even when the pure history recipe is unchanged.
    return registry.registered_contract_binding(
        component=component_key(name), source_contract=source_contract(name),
        implementation=_binding_rule(name),
        dependency_boundary=registry.DependencyBoundary("defining_module", (contracts.binding_result, math)),
    )

# Explicit unpublished contributor exports. compose_v2 is deliberately unchanged.
V2_TYPES = node_contracts._freeze({
    ("analytical.market_frame", 2): {"type_id": "analytical.market_frame", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "named indexed market fields"},
    ("analytical.float64", 2): {"type_id": "analytical.float64", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "indexed NumericValue float64 cells"},
    ("analytical.boolean", 2): {"type_id": "analytical.boolean", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "indexed NumericValue boolean cells"},
})
V2_COMPONENTS = node_contracts._freeze({component_key(name): descriptor(name) for name in NAMES})
NODE_CONTRACTS = node_contracts._freeze({component_key(name): source_contract(name) for name in NAMES})
DATA_REQUIREMENTS = node_contracts._freeze({})
# These local records identify candidates. Only the later integration capsule may
# insert them into the platform registry after the independent assurance gate.
CONTRACT_BINDINGS = node_contracts._freeze({component_key(name): _binding_registration(name) for name in NAMES})
V2_IMPLEMENTATIONS = node_contracts._freeze({component_key(name): registry.registered_v2_implementation(
    component=component_key(name), implementation=implementation_for(name),
    dependency_boundary=registry.DependencyBoundary("defining_module", (abc, pd, math, decimal, _decimal, hashing, node_contracts, registry, validity, common, contracts)),
) for name in NAMES})
