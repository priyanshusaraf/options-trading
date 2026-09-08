"""Unpublished multi-output v2 candidates. No registry composition or live authority.

Generated from the sealed matrix and this wave's bounded producer/body artifacts.
Existing contract, registry and NumericValue authorities remain the sole consumers.
"""
from __future__ import annotations

import collections.abc as abc
import decimal
import _decimal
import fractions
import math
import pandas as pd
from app.ir import hashing, node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import common, contracts

# BEGIN immutable accepted matrix facts; regenerate, do not hand-edit.
SPECS = node_contracts._freeze({'BOLLINGER_BANDS': {'constraints': [],
                     'decision': 'REPLACE_V2',
                     'dependencies': ['SMA', 'ROLLING_STDDEV'],
                     'execution_form': 'ROLLING',
                     'first_valid_index': 'window - 1',
                     'formula': 'Strategy OS mathematical Bollinger bands: middle is the exact trailing arithmetic mean of close over window; population variance is sum((close_i-middle)^2)/window; lower=middle-deviations*sqrt(variance), upper=middle+deviations*sqrt(variance). Exact finite binary64 observations and deviation parameters are real-valued inputs; float64 outputs share first-valid window-1. Pinned TA_BBANDS arithmetic remains comparison evidence, not a universal native-value parity promise.',
                     'inputs': ['close'],
                     'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                       'NaN/infinity/missing bar yields an invalid output and restarts '
                                       'contiguous warmup; never substitute close, zero, prior price or '
                                       'peer=open.',
                     'outputs': {'lower': {'dtype': 'float64_series', 'units': 'input_units'},
                                 'middle': {'dtype': 'float64_series', 'units': 'input_units'},
                                 'upper': {'dtype': 'float64_series', 'units': 'input_units'}},
                     'parameters': {'deviations': {'default': 2,
                                                   'maximum': 20,
                                                   'minimum': 1e-06,
                                                   'type': 'finite_number'},
                                    'window': {'default': 14,
                                               'maximum': 4096,
                                               'minimum': 2,
                                               'type': 'exact_integer'}},
                     'refusal': None,
                     'seed': 'No recursive seed. Trailing closed window, population variance (ddof=0), and common three-port first-valid index window-1. Mathematical real arithmetic; preserve all existing gap/reset and mask rules.',
                     'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                      'instrument/timeframe/adjustment identity; do not reset ordinary '
                                      'rolling or recursive math just because the civil date changes. Reset '
                                      'on discontinuity, identity change or explicit reset.',
                     'source': 'SPEC',
                     'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb', 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482', 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925', 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994', 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3', 'sha256:8c88ba4cf4bb14ea67813de42e4d8e7f8735a1d885f8ffa931eaa9b99f244866', 'sha256:2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1'),
                     'threshold_class': 'NONRECURSIVE',
                     'variant': 'bollinger_bands-mathematical-v2',
                     'wave': 'multi-output',
                     'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                              'never a finite substitute.'},
 'BOLLINGER_BANDWIDTH': {'constraints': [],
                         'decision': 'REPLACE_V2',
                         'dependencies': ['BOLLINGER_BANDS'],
                         'execution_form': 'ROLLING',
                         'first_valid_index': 'window - 1',
                         'formula': '100*(upper-lower)/middle using the same Bollinger parameters; '
                                    'percentage points.',
                         'inputs': ['close'],
                         'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                           'call. NaN/infinity/missing bar yields an invalid output and '
                                           'restarts contiguous warmup; never substitute close, zero, prior '
                                           'price or peer=open.',
                         'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
                         'parameters': {'deviations': {'default': 2,
                                                       'maximum': 20,
                                                       'minimum': 1e-06,
                                                       'type': 'finite_number'},
                                        'window': {'default': 14,
                                                   'maximum': 4096,
                                                   'minimum': 2,
                                                   'type': 'exact_integer'}},
                         'refusal': None,
                         'seed': 'No recursive seed; trailing closed window only.',
                         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                          'instrument/timeframe/adjustment identity; do not reset ordinary '
                                          'rolling or recursive math just because the civil date changes. '
                                          'Reset on discontinuity, identity change or explicit reset.',
                         'source': 'SPEC',
                         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                         'threshold_class': 'NONRECURSIVE',
                         'variant': 'bollinger_bandwidth-v2',
                         'wave': 'multi-output',
                         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is '
                                                  'invalid, never a finite substitute.'},
 'BOLLINGER_PERCENT_B': {'constraints': [],
                         'decision': 'REPLACE_V2',
                         'dependencies': ['BOLLINGER_BANDS'],
                         'execution_form': 'ROLLING',
                         'first_valid_index': 'window - 1',
                         'formula': '(close-lower)/(upper-lower), decimal fraction; not multiplied by 100.',
                         'inputs': ['close'],
                         'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                           'call. NaN/infinity/missing bar yields an invalid output and '
                                           'restarts contiguous warmup; never substitute close, zero, prior '
                                           'price or peer=open.',
                         'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
                         'parameters': {'deviations': {'default': 2,
                                                       'maximum': 20,
                                                       'minimum': 1e-06,
                                                       'type': 'finite_number'},
                                        'window': {'default': 14,
                                                   'maximum': 4096,
                                                   'minimum': 2,
                                                   'type': 'exact_integer'}},
                         'refusal': None,
                         'seed': 'No recursive seed; trailing closed window only.',
                         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                          'instrument/timeframe/adjustment identity; do not reset ordinary '
                                          'rolling or recursive math just because the civil date changes. '
                                          'Reset on discontinuity, identity change or explicit reset.',
                         'source': 'SPEC',
                         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                         'threshold_class': 'NONRECURSIVE',
                         'variant': 'bollinger_percent_b-v2',
                         'wave': 'multi-output',
                         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is '
                                                  'invalid, never a finite substitute.'},
 'DONCHIAN_CHANNELS': {'constraints': [],
                       'decision': 'REPLACE_V2',
                       'dependencies': [],
                       'execution_form': 'ROLLING',
                       'first_valid_index': 'window - 1',
                       'formula': 'lower=min(low,window); upper=max(high,window); middle=(lower+upper)/2; '
                                  'include current completed bar.',
                       'inputs': ['high', 'low'],
                       'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                         'call. NaN/infinity/missing bar yields an invalid output and '
                                         'restarts contiguous warmup; never substitute close, zero, prior '
                                         'price or peer=open.',
                       'outputs': {'lower': {'dtype': 'float64_series', 'units': 'input_units'},
                                   'middle': {'dtype': 'float64_series', 'units': 'input_units'},
                                   'upper': {'dtype': 'float64_series', 'units': 'input_units'}},
                       'parameters': {'window': {'default': 14,
                                                 'maximum': 4096,
                                                 'minimum': 2,
                                                 'type': 'exact_integer'}},
                       'refusal': None,
                       'seed': 'No recursive seed; trailing closed window only.',
                       'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                        'instrument/timeframe/adjustment identity; do not reset ordinary '
                                        'rolling or recursive math just because the civil date changes. '
                                        'Reset on discontinuity, identity change or explicit reset.',
                       'source': 'SPEC',
                       'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                            'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                            'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                            'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                            'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                       'threshold_class': 'NONRECURSIVE',
                       'variant': 'donchian_channels-v2',
                       'wave': 'multi-output',
                       'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                'never a finite substitute.'},
 'KELTNER_CHANNELS': {'constraints': [],
                      'decision': 'REPLACE_V2',
                      'dependencies': ['SMA', 'EMA', 'ATR'],
                      'execution_form': 'RECURSIVE',
                      'first_valid_index': 'max(window - 1, atr_length)',
                      'formula': 'middle is the selected SMA or seeded EMA of close over window; '
                                 'lower/upper=middle +/- multiplier*ATR(atr_length).',
                      'inputs': ['high', 'low', 'close'],
                      'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                        'call. NaN/infinity/missing bar yields an invalid output and '
                                        'restarts contiguous warmup; never substitute close, zero, prior '
                                        'price or peer=open.',
                      'outputs': {'lower': {'dtype': 'float64_series', 'units': 'input_units'},
                                  'middle': {'dtype': 'float64_series', 'units': 'input_units'},
                                  'upper': {'dtype': 'float64_series', 'units': 'input_units'}},
                      'parameters': {'atr_length': {'default': 14,
                                                    'maximum': 4096,
                                                    'minimum': 2,
                                                    'type': 'exact_integer'},
                                     'basis_type': {'default': 'EMA',
                                                    'type': 'enum',
                                                    'values': ['EMA', 'SMA']},
                                     'multiplier': {'default': 2,
                                                    'maximum': 20,
                                                    'minimum': 1e-06,
                                                    'type': 'finite_number'},
                                     'window': {'default': 14,
                                                'maximum': 4096,
                                                'minimum': 2,
                                                'type': 'exact_integer'}},
                      'refusal': None,
                      'seed': 'Selected basis state and ATR state, independently warmed.',
                      'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                       'instrument/timeframe/adjustment identity; do not reset ordinary '
                                       'rolling or recursive math just because the civil date changes. Reset '
                                       'on discontinuity, identity change or explicit reset.',
                      'source': 'SPEC',
                      'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                           'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                           'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                           'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                           'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                      'threshold_class': 'RECURSIVE',
                      'variant': 'modern_close_atr_keltner',
                      'wave': 'multi-output',
                      'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                               'never a finite substitute.'},
 'MACD': {'conditional_input_fields': {'close': ['close'],
                                       'high': ['high'],
                                       'hl2': ['high', 'low'],
                                       'hlc3': ['high', 'low', 'close'],
                                       'low': ['low'],
                                       'ohlc4': ['open', 'high', 'low', 'close'],
                                       'open': ['open']},
          'constraints': ['fast_length < slow_length'],
          'decision': 'REPLACE_V2',
          'dependencies': ['EMA'],
          'execution_form': 'RECURSIVE',
          'first_valid_index': 'slow_length + signal_length - 2',
          'formula': 'Strategy OS mathematical MACD on the selected source: SMA-seed slow EMA from source[0:slow_length] and fast EMA from source[slow_length-fast_length:slow_length], both first at slow_length-1; thereafter EMA_n(t)=EMA_n(t-1)+2/(n+1)*(source(t)-EMA_n(t-1)). macd=fast-slow; signal is SMA-seeded EMA(signal_length) of the aligned macd sequence; histogram=macd-signal. Emit all three ports from slow_length+signal_length-2. Exact finite binary64 observations are real-valued inputs to this mathematical recurrence; rounded native TA-Lib trajectories remain comparison evidence, not a universal parity promise.',
          'inputs': ['close'],
          'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                            'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                            'warmup; never substitute close, zero, prior price or peer=open.',
          'outputs': {'histogram': {'dtype': 'float64_series', 'units': 'input_units'},
                      'macd': {'dtype': 'float64_series', 'units': 'input_units'},
                      'signal': {'dtype': 'float64_series', 'units': 'input_units'}},
          'parameters': {'fast_length': {'default': 12,
                                         'maximum': 4096,
                                         'minimum': 2,
                                         'type': 'exact_integer'},
                         'signal_length': {'default': 9,
                                           'maximum': 4096,
                                           'minimum': 1,
                                           'type': 'exact_integer'},
                         'slow_length': {'default': 26,
                                         'maximum': 4096,
                                         'minimum': 2,
                                         'type': 'exact_integer'},
                         'source': {'default': 'close',
                                    'type': 'enum',
                                    'values': ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4']}},
          'refusal': None,
          'seed': 'Pinned TA_MACD DEFAULT/unstable-zero alignment and common start, with explicitly mathematical SMA/EMA arithmetic. Fast and slow seed at slow_length-1; signal seeds from its first signal_length aligned differences. No independent-fast-start substitution and no universal native-value parity claim.',
          'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                           'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                           'recursive math just because the civil date changes. Reset on discontinuity, '
                           'identity change or explicit reset.',
          'source': 'SPEC',
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb', 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482', 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925', 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994', 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3', 'sha256:f994e846f8eede929155c223cf15305bd8cd7064a788a55de50c339012cfae79', 'sha256:f954430f5b7981078faf609fba47a0754187f3923f2ae2dc596368a18c3e271a'),
          'threshold_class': 'RECURSIVE',
          'variant': 'macd-mathematical-v2',
          'wave': 'multi-output',
          'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                   'finite substitute.'},
 'PPO': {'constraints': ['fast_length < slow_length'],
         'decision': 'REPLACE_V2',
         'dependencies': ['SMA', 'EMA'],
         'execution_form': 'RECURSIVE',
         'first_valid_index': 'slow_length - 1',
         'formula': 'Strategy OS mathematical PPO: 100*(MA(close,fast_length)-MA(close,slow_length))/MA(close,slow_length), with explicit SMA or EMA. Each EMA is independently SMA-seeded from the first length observations and then uses EMA_n(t)=EMA_n(t-1)+2/(n+1)*(close(t)-EMA_n(t-1)); SMA is the trailing arithmetic mean. Exact finite binary64 observations are real-valued inputs. Emit from slow_length-1; an exactly zero slow mean remains invalid under the existing zero policy. Pinned native arithmetic remains comparison evidence, not a universal native-value parity promise.',
         'inputs': ['close'],
         'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                           'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                           'warmup; never substitute close, zero, prior price or peer=open.',
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentage_points'}},
         'parameters': {'fast_length': {'default': 12,
                                        'maximum': 4096,
                                        'minimum': 2,
                                        'type': 'exact_integer'},
                        'moving_average_type': {'default': 'EMA', 'type': 'enum', 'values': ['EMA', 'SMA']},
                        'slow_length': {'default': 26,
                                        'maximum': 4096,
                                        'minimum': 2,
                                        'type': 'exact_integer'}},
         'refusal': None,
         'seed': 'Explicit SMA or EMA; independent first-length SMA seeds for the fast and slow EMA, preserving pinned TA_PPO DEFAULT/unstable-zero start-at-zero alignment. Emit from slow_length-1. Do not substitute MACD-style aligned fast seeding or wrapper defaults. Mathematical arithmetic, not a native rounding-trajectory promise.',
         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                          'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                          'recursive math just because the civil date changes. Reset on discontinuity, '
                          'identity change or explicit reset.',
         'source': 'SPEC',
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb', 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482', 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925', 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994', 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3', 'sha256:dfac225a821e7d6ec9c1c53bbd534d481b8f5edd8c8bc4f1dcd54d6f6ab4fede', 'sha256:2ca3e31e074984d1545af8a0a98ea718fbaf2ad093552ec651672df8ae6213f1'),
         'threshold_class': 'RECURSIVE',
         'variant': 'ppo-mathematical-v2',
         'wave': 'multi-output',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                  'finite substitute.'},
 'STOCHASTIC': {'constraints': [],
                'decision': 'REPLACE_V2',
                'dependencies': [],
                'execution_form': 'ROLLING',
                'first_valid_index': 'k_length + k_smoothing + d_smoothing - 3',
                'formula': 'raw_k=100*(close-min(low,k_length))/(max(high,k_length)-min(low,k_length)); '
                           'k=SMA(raw_k,k_smoothing); d=SMA(k,d_smoothing). Pinned TA_STOCH common start.',
                'inputs': ['high', 'low', 'close'],
                'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                  'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                  'warmup; never substitute close, zero, prior price or peer=open.',
                'outputs': {'d': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'},
                            'k': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'}},
                'parameters': {'d_smoothing': {'default': 3,
                                               'maximum': 4096,
                                               'minimum': 1,
                                               'type': 'exact_integer'},
                               'k_length': {'default': 14,
                                            'maximum': 4096,
                                            'minimum': 2,
                                            'type': 'exact_integer'},
                               'k_smoothing': {'default': 3,
                                               'maximum': 4096,
                                               'minimum': 1,
                                               'type': 'exact_integer'}},
                'refusal': None,
                'seed': 'No recursive seed; trailing closed window only.',
                'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                 'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                 'recursive math just because the civil date changes. Reset on '
                                 'discontinuity, identity change or explicit reset.',
                'source': 'TA:STOCH',
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:772d667ede29289e03d72e5e5a92752528bb65c07e2e49063d83e28d58f6c9ce'),
                'threshold_class': 'NONRECURSIVE',
                'variant': 'stochastic-v2',
                'wave': 'multi-output',
                'zero_undefined_policy': 'Raw k=0 for valid zero high-low range, then smooth; missing rows '
                                         'remain invalid.'},
 'STOCH_RSI': {'constraints': [],
               'decision': 'REPLACE_V2',
               'dependencies': ['RSI', 'SMA'],
               'execution_form': 'RECURSIVE',
               'first_valid_index': 'rsi_length + stochastic_length + k_smoothing + d_smoothing - 3',
               'formula': 'Use seeded RSI(rsi_length); '
                          'raw_k=100*(RSI-min(RSI,stochastic_length))/(max(RSI,stochastic_length)-min(RSI,stochastic_length)); '
                          'k=SMA(raw_k,k_smoothing); d=SMA(k,d_smoothing).',
               'inputs': ['close'],
               'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                 'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                 'warmup; never substitute close, zero, prior price or peer=open.',
               'outputs': {'d': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'},
                           'k': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'}},
               'parameters': {'d_smoothing': {'default': 3,
                                              'maximum': 4096,
                                              'minimum': 1,
                                              'type': 'exact_integer'},
                              'k_smoothing': {'default': 3,
                                              'maximum': 4096,
                                              'minimum': 1,
                                              'type': 'exact_integer'},
                              'rsi_length': {'default': 14,
                                             'maximum': 4096,
                                             'minimum': 2,
                                             'type': 'exact_integer'},
                              'stochastic_length': {'default': 14,
                                                    'maximum': 4096,
                                                    'minimum': 2,
                                                    'type': 'exact_integer'}},
               'refusal': None,
               'seed': 'RSI state plus complete stochastic/smoothing windows.',
               'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                'recursive math just because the civil date changes. Reset on discontinuity, '
                                'identity change or explicit reset.',
               'source': 'TA:STOCHRSI',
               'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                    'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                    'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                    'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                    'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                    'sha256:d483ff9874e436b2499c10a8db3690491594588bdd9ed940dc327f7e375b079c'),
               'threshold_class': 'RECURSIVE',
               'variant': 'smoothed_stoch_rsi_k_d',
               'wave': 'multi-output',
               'zero_undefined_policy': 'Raw k=0 on valid constant RSI window; with k_smoothing=1 compare '
                                        'pinned TA_STOCHRSI, otherwise independent composed reference.'}})
NAMES = tuple(sorted(SPECS))
# END immutable accepted matrix facts.


def component_key(name):
    if name not in SPECS:
        raise node_contracts.NodeContractRefusal("MULTI_COMPONENT_UNAVAILABLE")
    return ("analytical." + name.lower(), 2)


def parameters_for(name, parameters=None):
    component_key(name)
    supplied = {} if parameters is None else parameters
    specs = SPECS[name]["parameters"]
    if not isinstance(supplied, abc.Mapping) or set(supplied) - set(specs):
        raise node_contracts.NodeContractRefusal("MULTI_PARAMETERS_UNKNOWN")
    result = {}
    for key, spec in specs.items():
        value = supplied.get(key, spec["default"])
        if spec["type"] == "enum":
            if type(value) is not str or value not in spec["values"]:
                raise node_contracts.NodeContractRefusal("MULTI_PARAMETER_ENUM")
        else:
            if (type(value) is not int if spec["type"] == "exact_integer" else
                    type(value) not in {int, float} or not math.isfinite(value)):
                raise node_contracts.NodeContractRefusal("MULTI_PARAMETER_TYPE")
            if not spec["minimum"] <= value <= spec["maximum"]:
                raise node_contracts.NodeContractRefusal("MULTI_PARAMETER_DOMAIN")
        result[key] = value  # Preserve the resolver's exact canonical int/float bytes.
    if name in {"MACD", "PPO"} and not result["fast_length"] < result["slow_length"]:
        raise node_contracts.NodeContractRefusal("MULTI_PARAMETER_RELATION")
    return node_contracts._freeze(result)


def fields_by_port(name, parameters=None):
    values = parameters_for(name, parameters)
    fields = SPECS[name]["inputs"]
    if name == "MACD":
        fields = {"hl2": ("high", "low"), "hlc3": ("high", "low", "close"),
                  "ohlc4": ("open", "high", "low", "close")}.get(values["source"], (values["source"],))
    return node_contracts._freeze({"frame": tuple(sorted(field.upper() for field in fields))})


def first_valid_index(name, parameters=None):
    p = parameters_for(name, parameters)
    if name in {"BOLLINGER_BANDS", "BOLLINGER_BANDWIDTH", "BOLLINGER_PERCENT_B", "DONCHIAN_CHANNELS"}:
        return p["window"] - 1
    if name == "KELTNER_CHANNELS":
        return max(p["window"] - 1, p["atr_length"])
    if name == "MACD":
        return p["slow_length"] + p["signal_length"] - 2
    if name == "PPO":
        return p["slow_length"] - 1
    if name == "STOCHASTIC":
        return p["k_length"] + p["k_smoothing"] + p["d_smoothing"] - 3
    return p["rsi_length"] + p["stochastic_length"] + p["k_smoothing"] + p["d_smoothing"] - 3


def _port(name, direction):
    result = {"port_id": name, "direction": direction, "semantic_flow": "value",
              "semantic_role": "market_frame" if direction == "input" else "analytical_value",
              "type_ref": {"type_id": "analytical.market_frame" if direction == "input" else "analytical.float64", "type_version": 2},
              "shape": "series"}
    if direction == "input":
        result["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return result


def descriptor(name):
    parameters = {}
    for key, spec in SPECS[name]["parameters"].items():
        enum = spec["type"] == "enum"
        kind = "str" if enum else "int" if spec["type"] == "exact_integer" else "float"
        parameters[key] = {"type": kind, "required": False, "default": spec["default"],
            "enum": list(spec["values"]) if enum else None,
            "domain": {"max_length": max(map(len, spec["values"]))} if enum else {"minimum": spec["minimum"], "maximum": spec["maximum"]},
            "units": "choice" if enum else "bars" if kind == "int" else "dimensionless", "serialization": "canonical-json"}
    return node_contracts._freeze({"component_id": component_key(name)[0], "component_version": 2,
        "domain_family": "indicator", "structural_role": "transform", "parameters": parameters,
        "ports": [_port("frame", "input")] + [_port(port, "output") for port in sorted(SPECS[name]["outputs"])]})


def _binding_rule(name):
    specs = tuple((key, spec["type"], spec.get("minimum"), spec.get("maximum"), tuple(spec.get("values", ())))
                  for key, spec in sorted(SPECS[name]["parameters"].items()))
    fixed_fields = tuple(sorted(field.upper() for field in SPECS[name]["inputs"]))
    output_ports = tuple(sorted(SPECS[name]["outputs"]))
    builder = contracts.binding_result

    def bind(parameters, inputs, _spec=(name, specs, fixed_fields, output_ports, builder)):
        name, specs, fields, outputs, builder = _spec
        if set(parameters) != {row[0] for row in specs}:
            raise ValueError("exact canonical parameters required")
        for key, kind, minimum, maximum, values in specs:
            value = parameters[key]
            if kind == "enum":
                if type(value) is not str or value not in values:
                    raise ValueError("declared enum required")
            else:
                if (type(value) is not int if kind == "exact_integer" else type(value) not in (int, float) or not math.isfinite(value)):
                    raise ValueError("canonical numeric parameter required")
                if not minimum <= value <= maximum:
                    raise ValueError("parameter bounds")
        if name in {"MACD", "PPO"} and not parameters["fast_length"] < parameters["slow_length"]:
            raise ValueError("fast must precede slow")
        if name == "MACD":
            source = parameters["source"]
            fields = {"hl2": ("HIGH", "LOW"), "hlc3": ("CLOSE", "HIGH", "LOW"),
                      "ohlc4": ("CLOSE", "HIGH", "LOW", "OPEN")}.get(source, (source.upper(),))
            first = parameters["slow_length"] + parameters["signal_length"] - 2
        elif name == "PPO":
            first = parameters["slow_length"] - 1
        elif name == "KELTNER_CHANNELS":
            first = max(parameters["window"] - 1, parameters["atr_length"])
        elif name == "STOCHASTIC":
            first = parameters["k_length"] + parameters["k_smoothing"] + parameters["d_smoothing"] - 3
        elif name == "STOCH_RSI":
            first = parameters["rsi_length"] + parameters["stochastic_length"] + parameters["k_smoothing"] + parameters["d_smoothing"] - 3
        else:
            first = parameters["window"] - 1
        return builder(inputs, fields_by_port={"frame": fields}, warmup_history=first,
                       output_warmup={port: first for port in outputs})
    return bind


def source_contract(name):
    key = component_key(name)
    rule = {"rule_id": key[0] + ".binding", "rule_version": 1}
    slots = 16384 if name == "STOCHASTIC" else 12288 if name == "STOCH_RSI" else 8192 if name in {"PPO", "DONCHIAN_CHANNELS"} else 4096
    # A scalar has at most 1560 serialized characters. Budget eight encoding,
    # parsing and retained transport copies, Decimal objects and list overhead.
    # The earlier 8192-byte allowance failed measured maximum RSI restart; its
    # raw failure is preserved. This bound includes restart, not just live state.
    profile = {"compute_microseconds_per_event": 200000, "memory_bytes_upper_bound": 8388608 + slots * 16384,
               "history_bytes_upper_bound": 65536 + slots * 2048, "state_bytes_upper_bound": 131072 + slots * 2048,
               "storage_bytes_per_day_upper_bound": 0, "subscription_count_upper_bound": 1, "fanout_upper_bound": 1}
    return node_contracts._freeze({"schema": "first-party-node-contract/2", "stable_node_id": key[0], "semantic_version": 2,
        "visible_family": "TYPE_2", "input_types": {"frame": "analytical.market_frame/series"},
        "output_types": {port: "analytical.float64/series" for port in SPECS[name]["outputs"]},
        "required_market_fields": ["close", "high", "low", "open"] if name == "MACD" else sorted(SPECS[name]["inputs"]),
        "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
        "warmup_history": rule, "execution_form": SPECS[name]["execution_form"],
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": ["DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE"]},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE", "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX", "evaluation_triggers": ["completed_bar"],
        "streaming_support": True, "batch_support": True, "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [], "resource_profile": profile,
        "reference_provenance": sorted(set(SPECS[name]["source_addresses"] + (hashing.content_address(node_contracts._plain(SPECS[name])),))),
        "parameter_binding": {"scheme": "analytical-contract-binding/1", **rule,
                              "parameter_names": sorted(SPECS[name]["parameters"]), "input_ports": ["frame"]}})


def _check_bound(name, parameters, bound):
    if not isinstance(bound, contracts.ResolvedNodeContract):
        raise node_contracts.NodeContractRefusal("MULTI_VERIFIED_BINDING_REQUIRED")
    doc = bound.document
    replay = contracts.materialize_node_contract(source_contract(name), _binding_registration(name), parameters, doc["input_binding"])
    if replay.bound_contract_address != bound.bound_contract_address:
        raise node_contracts.NodeContractRefusal("MULTI_BINDING_REPLAY_MISMATCH")
    key = component_key(name)
    if (dict(doc["component"]) != {"component_id": key[0], "component_version": 2}
            or hashing.content_address(dict(doc["parameters"])) != hashing.content_address(dict(parameters))
            or dict(doc["resolved_contract"]["output_warmup"]) != {port: first_valid_index(name, parameters) for port in SPECS[name]["outputs"]}):
        raise node_contracts.NodeContractRefusal("MULTI_BINDING_MISMATCH")
    _check_bound_inputs(name, parameters, doc["input_binding"]["ports"])


def _check_bound_inputs(name, parameters, ports):
    if set(ports) != {"frame"}:
        raise node_contracts.NodeContractRefusal("MULTI_INPUT_ROLES")
    fact = ports["frame"]["binding"]
    if (not set(fields_by_port(name, parameters)["frame"]) <= set(fact["fields"])
            or dict(fact["alignment"]) != {"kind": "EXACT", "maximum_skew_seconds": 0}):
        raise node_contracts.NodeContractRefusal("MULTI_ALIGNED_FIELDS_REQUIRED")


def _timestamp(value):
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError("timezone required")
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        raise node_contracts.NodeContractRefusal("MULTI_CANONICAL_TIME_REQUIRED") from exc


def _context():
    return _decimal.Context(prec=1536, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                           flags=[], traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow])


def _d(value):
    return decimal.Decimal.from_float(float(value))


def _fraction_decimal(value):
    return decimal.Decimal(value.numerator) / decimal.Decimal(value.denominator)


def _layout(name, p):
    if name.startswith("BOLLINGER_"):
        return {"close": p["window"]}, ()
    if name == "DONCHIAN_CHANNELS":
        return {"low": p["window"], "high": p["window"]}, ()
    if name == "KELTNER_CHANNELS":
        return ({"basis": p["window"]} if p["basis_type"] == "SMA" else {}), ("basis", "basis_seed", "atr", "atr_seed")
    if name == "MACD":
        return {"fast_seed": p["fast_length"]}, ("fast", "slow", "slow_seed", "signal", "signal_seed")
    if name == "PPO":
        return ({"fast": p["fast_length"], "slow": p["slow_length"]} if p["moving_average_type"] == "SMA" else {}), ("fast", "slow", "fast_seed", "slow_seed")
    if name == "STOCHASTIC":
        return {"low": p["k_length"], "high": p["k_length"], "raw_k": p["k_smoothing"], "k": p["d_smoothing"]}, ()
    return {"rsi": p["stochastic_length"], "raw_k": p["k_smoothing"], "k": p["d_smoothing"]}, ("gain", "loss")


class MultiOutputState:
    """Bounded completed-event state; source/parameter identities bind restoration."""
    def __init__(self, name, parameters, bound_contract):
        self.name = name
        self.parameters = parameters_for(name, parameters)
        _check_bound(name, self.parameters, bound_contract)
        self.bound_contract = bound_contract
        self.first = first_valid_index(name, self.parameters)
        self._limits, self._keys = _layout(name, self.parameters)
        self._last_time = None
        self._clear()

    def _clear(self):
        self._seen = 0
        self._previous = {}
        self._numbers = {key: decimal.Decimal(0) for key in self._keys}
        self._history = {key: [] for key in self._limits}
        self._sums = {key: decimal.Decimal(0) for key in self._limits}
        self._fraction_sum = fractions.Fraction(0)
        self._fraction_square = fractions.Fraction(0)

    def _push(self, key, value):
        history = self._history[key]
        old = history.pop(0) if len(history) == self._limits[key] else None
        history.append(value)
        self._sums[key] += value - (old if old is not None else 0)
        return old

    def _ema(self, key, value, period, n):
        s = self._numbers
        if n < period:
            s[key + "_seed"] += value
            if n == period - 1:
                s[key] = s[key + "_seed"] / period
                s[key + "_seed"] = decimal.Decimal(0)
        else:
            s[key] += decimal.Decimal(2) * (value - s[key]) / (period + 1)
        return s[key]

    def _advance(self, row):
        name, p, n, s = self.name, self.parameters, self._seen, self._numbers
        close = row.get("close")
        if name.startswith("BOLLINGER_"):
            old = self._push("close", close)
            value = fractions.Fraction(close)
            removed = fractions.Fraction(old) if old is not None else fractions.Fraction(0)
            self._fraction_sum += value - removed
            self._fraction_square += value * value - removed * removed
            if n < p["window"] - 1:
                return {}
            mean = self._fraction_sum / p["window"]
            variance = self._fraction_square / p["window"] - mean * mean
            middle = _fraction_decimal(mean)
            width = _fraction_decimal(variance).sqrt() * _d(p["deviations"])
            if name == "BOLLINGER_BANDS":
                return {"lower": middle - width, "middle": middle, "upper": middle + width}
            if name == "BOLLINGER_BANDWIDTH":
                return {"value": 200 * width / middle if mean else None}
            return {"value": (_fraction_decimal(value - mean) / width + 1) / 2 if width else None}
        if name == "DONCHIAN_CHANNELS":
            self._push("low", row["low"]); self._push("high", row["high"])
            low, high = min(self._history["low"]), max(self._history["high"])
            return {"lower": low, "middle": (low + high) / 2, "upper": high}
        if name == "KELTNER_CHANNELS":
            if p["basis_type"] == "SMA":
                self._push("basis", close)
                basis = self._sums["basis"] / p["window"]
            else:
                basis = self._ema("basis", close, p["window"], n)
            if n:
                previous = _d(self._previous["close"])
                tr = max(row["high"] - row["low"], abs(row["high"] - previous), abs(row["low"] - previous))
                length = p["atr_length"]
                if n <= length:
                    s["atr_seed"] += tr
                    if n == length:
                        s["atr"] = s["atr_seed"] / length
                        s["atr_seed"] = decimal.Decimal(0)
                else:
                    s["atr"] = (s["atr"] * (length - 1) + tr) / length
            width = _d(p["multiplier"]) * s["atr"]
            return {"lower": basis - width, "middle": basis, "upper": basis + width}
        if name == "MACD":
            fields = {"hl2": ("high", "low"), "hlc3": ("high", "low", "close"),
                      "ohlc4": ("open", "high", "low", "close")}.get(p["source"], (p["source"],))
            value = sum((row[field] for field in fields), decimal.Decimal(0)) / len(fields)
            self._push("fast_seed", value)
            fast, slow = p["fast_length"], p["slow_length"]
            if n < slow:
                s["slow_seed"] += value
                if n < slow - 1:
                    return {}
                # Both EMA seeds end at slow-1, as pinned TA_MACD requires.
                s["slow"] = s["slow_seed"] / slow
                s["slow_seed"] = decimal.Decimal(0)
                s["fast"] = self._sums["fast_seed"] / fast
            else:
                s["fast"] += decimal.Decimal(2) * (value - s["fast"]) / (fast + 1)
                s["slow"] += decimal.Decimal(2) * (value - s["slow"]) / (slow + 1)
            macd = s["fast"] - s["slow"]
            signal = self._ema("signal", macd, p["signal_length"], n - slow + 1)
            return {"macd": macd, "signal": signal, "histogram": macd - signal}
        if name == "PPO":
            means = {}
            for key in ("fast", "slow"):
                length = p[key + "_length"]
                if p["moving_average_type"] == "SMA":
                    self._push(key, close)
                    means[key] = self._sums[key] / length
                else:
                    means[key] = self._ema(key, close, length, n)
            return {"value": 100 * (means["fast"] - means["slow"]) / means["slow"] if means["slow"] else None}
        if name == "STOCH_RSI":
            w = p["rsi_length"]
            if n:
                delta = close - _d(self._previous["close"])
                gain, loss = max(delta, 0), max(-delta, 0)
                if n <= w:
                    s["gain"] += gain; s["loss"] += loss
                    if n == w:
                        s["gain"] /= w; s["loss"] /= w
                else:
                    s["gain"] = (s["gain"] * (w - 1) + gain) / w
                    s["loss"] = (s["loss"] * (w - 1) + loss) / w
            if n < w:
                return {}
            total = s["gain"] + s["loss"]
            # With zero price change both Wilder averages have the same decay.
            # Their ratio is invariant: reuse its retained value rather than
            # manufacture a stochastic range from independent rounding errors.
            value = (self._history["rsi"][-1] if n > w and delta == 0 else
                     100 * s["gain"] / total if total else decimal.Decimal(0))
            self._push("rsi", value)
            if len(self._history["rsi"]) < p["stochastic_length"]:
                return {}
            low, high = min(self._history["rsi"]), max(self._history["rsi"])
        else:
            self._push("low", row["low"]); self._push("high", row["high"])
            if len(self._history["low"]) < p["k_length"]:
                return {}
            value, low, high = close, min(self._history["low"]), max(self._history["high"])
        raw_k = 100 * (value - low) / (high - low) if high != low else decimal.Decimal(0)
        self._push("raw_k", raw_k)
        if len(self._history["raw_k"]) < p["k_smoothing"]:
            return {}
        k = self._sums["raw_k"] / p["k_smoothing"]
        self._push("k", k)
        return {"k": k, "d": self._sums["k"] / p["d_smoothing"]}

    def step(self, inputs, *, event_time, reset_reasons=(), event_kind="completed_bar"):
        if event_kind != "completed_bar":
            raise node_contracts.NodeContractRefusal("MULTI_COMPLETED_BAR_REQUIRED")
        timestamp = _timestamp(event_time)
        if self._last_time is not None and timestamp <= self._last_time:
            raise node_contracts.NodeContractRefusal("MULTI_EVENT_ORDER")
        reasons = common.contract_reset_reasons(self.bound_contract, reset_reasons)
        if not isinstance(inputs, abc.Mapping) or set(inputs) != {"frame"} or not isinstance(inputs["frame"], abc.Mapping):
            raise node_contracts.NodeContractRefusal("MULTI_NAMED_INPUT_PORTS")
        cells = {field.lower(): common.required_numeric_scalar(inputs["frame"], field.lower()) for field in fields_by_port(self.name, self.parameters)["frame"]}
        bad = validity.propagate(cells.values())
        if bad is None:
            raw = {key: value.value for key, value in cells.items()}
            if "high" in raw and "low" in raw and (raw["high"] < raw["low"] or "close" in raw and not raw["low"] <= raw["close"] <= raw["high"]):
                bad = validity.invalid(validity.ValidityState.INVALID)
        self._last_time = timestamp
        if reasons or bad is not None:
            self._clear()
        if bad is not None:
            return {port: bad for port in SPECS[self.name]["outputs"]}
        n = self._seen
        with decimal.localcontext(_context()):
            produced = self._advance({key: _d(value) for key, value in raw.items()})
        self._previous = raw
        self._seen = min(n + 1, self.first + 1)
        if n < self.first:
            return {port: validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY) for port in SPECS[self.name]["outputs"]}
        if set(produced) != set(SPECS[self.name]["outputs"]):
            raise node_contracts.NodeContractRefusal("MULTI_OUTPUT_CLOSURE")
        result = {}
        for port, value in produced.items():
            number = float(value) if value is not None else None
            result[port] = validity.valid(number) if number is not None and math.isfinite(number) else validity.invalid(validity.ValidityState.MATHEMATICALLY_UNDEFINED)
        return result

    def snapshot(self):
        # This checksum is payload integrity, not the existing transport's authority.
        body = {"schema": "analytical-multi-output-state/2", "component": list(component_key(self.name)),
                "bound_contract_address": self.bound_contract.bound_contract_address,
                "parameters": node_contracts._plain(self.parameters), "seen": self._seen,
                "last_time": self._last_time.isoformat() if self._last_time is not None else None,
                "previous": self._previous, "numbers": {key: str(value) for key, value in self._numbers.items()},
                "sums": {key: str(value) for key, value in self._sums.items()},
                "history": {key: [str(value) for value in values] for key, values in self._history.items()},
                "fractions": [[str(value.numerator), str(value.denominator)] for value in (self._fraction_sum, self._fraction_square)]}
        return {**body, "payload_address": hashing.content_address(body)}

    @classmethod
    def restore(cls, name, parameters, bound_contract, document):
        state = cls(name, parameters, bound_contract)
        fields = {"schema", "component", "bound_contract_address", "parameters", "seen", "last_time", "previous", "numbers", "sums", "history", "fractions", "payload_address"}
        if not isinstance(document, abc.Mapping) or set(document) != fields:
            raise node_contracts.NodeContractRefusal("MULTI_STATE_CLOSED_SCHEMA")
        if (document["schema"] != "analytical-multi-output-state/2" or document["component"] != list(component_key(name))
                or document["bound_contract_address"] != bound_contract.bound_contract_address
                or not isinstance(document["parameters"], abc.Mapping)
                or hashing.content_address(document["parameters"]) != hashing.content_address(dict(state.parameters))):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_IDENTITY")
        seen = document["seen"]
        if type(seen) is not int or not 0 <= seen <= state.first + 1:
            raise node_contracts.NodeContractRefusal("MULTI_STATE_COUNTER")
        previous = document["previous"]
        expected = {field.lower() for field in fields_by_port(name, parameters)["frame"]} if seen else set()
        if (not isinstance(previous, abc.Mapping) or set(previous) != expected or
                any(type(value) not in (int, float) or not math.isfinite(value) for value in previous.values())):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_PREVIOUS")
        if "high" in previous and "low" in previous and (previous["high"] < previous["low"] or "close" in previous and not previous["low"] <= previous["close"] <= previous["high"]):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_PREVIOUS")
        def decode(value):
            if not isinstance(value, str) or len(value) > 1560:
                raise node_contracts.NodeContractRefusal("MULTI_STATE_DECIMAL")
            try:
                result = decimal.Decimal(value)
                if not result.is_finite() or len(result.as_tuple().digits) > 1536 or abs(result.as_tuple().exponent) > 1001534 or str(result) != value:
                    raise ValueError("bounded canonical decimal required")
                # Finite binary64 bars, at most 4096 terms and at most a
                # two-price difference cannot produce a retained value >=1e313.
                # Check before any rational conversion of a decoded history.
                if result.copy_abs() > decimal.Decimal("1e313"):
                    raise ValueError("retained numeric magnitude is impossible")
            except (decimal.DecimalException, ValueError) as exc:
                raise node_contracts.NodeContractRefusal("MULTI_STATE_DECIMAL") from exc
            return result
        for key, expected_keys in [("numbers", set(state._numbers)), ("sums", set(state._sums)), ("history", set(state._history))]:
            if not isinstance(document[key], abc.Mapping) or set(document[key]) != expected_keys:
                raise node_contracts.NodeContractRefusal("MULTI_STATE_KEYS")
        p = state.parameters
        history = {}
        for key, limit in state._limits.items():
            count = seen
            if name == "STOCHASTIC" and key in {"raw_k", "k"}:
                count = max(0, seen - p["k_length"] + 1 - (p["k_smoothing"] - 1 if key == "k" else 0))
            if name == "STOCH_RSI":
                count = max(0, seen - p["rsi_length"] - (p["stochastic_length"] - 1 if key != "rsi" else 0) - (p["k_smoothing"] - 1 if key == "k" else 0))
            values = document["history"][key]
            if not isinstance(values, list) or len(values) != min(count, limit):
                raise node_contracts.NodeContractRefusal("MULTI_STATE_HISTORY")
            history[key] = [decode(value) for value in values]
            raw_prices = name not in {"MACD", "STOCH_RSI"} and key not in {"raw_k", "k"}
            if raw_prices and any(not math.isfinite(float(value)) or _d(float(value)) != value for value in history[key]):
                raise node_contracts.NodeContractRefusal("MULTI_STATE_RAW_HISTORY")
        if "high" in history and "low" in history and any(high < low for high, low in zip(history["high"], history["low"])):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_PRICE_RANGE")
        numbers = {key: decode(value) for key, value in document["numbers"].items()}
        nonnegative = ("gain", "loss") if name == "STOCH_RSI" else ("atr", "atr_seed") if name == "KELTNER_CHANNELS" else ()
        if any(numbers[key] < 0 for key in nonnegative):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_NONNEGATIVE")
        sums = {key: decode(value) for key, value in document["sums"].items()}
        rational = document["fractions"]
        if not isinstance(rational, list) or len(rational) != 2:
            raise node_contracts.NodeContractRefusal("MULTI_STATE_FRACTIONS")
        decoded_fractions = []
        for pair in rational:
            if not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(v, str) or len(v) > 1400 for v in pair):
                raise node_contracts.NodeContractRefusal("MULTI_STATE_FRACTIONS")
            try:
                value = fractions.Fraction(int(pair[0]), int(pair[1]))
                if pair != [str(value.numerator), str(value.denominator)]:
                    raise ValueError("noncanonical fraction")
            except (ValueError, ZeroDivisionError) as exc:
                raise node_contracts.NodeContractRefusal("MULTI_STATE_FRACTIONS") from exc
            decoded_fractions.append(value)
        if name.startswith("BOLLINGER_"):
            values = [fractions.Fraction(value) for value in history["close"]]
            if decoded_fractions != [sum(values, fractions.Fraction(0)), sum((value * value for value in values), fractions.Fraction(0))]:
                raise node_contracts.NodeContractRefusal("MULTI_STATE_MOMENTS")
        elif any(decoded_fractions):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_MOMENTS")
        if seen and document["last_time"] is None or not seen and (any(numbers.values()) or any(sums.values())):
            raise node_contracts.NodeContractRefusal("MULTI_STATE_EMPTY_OR_CLOCK")
        body = {key: value for key, value in document.items() if key != "payload_address"}
        if hashing.content_address(body) != document["payload_address"]:
            raise node_contracts.NodeContractRefusal("MULTI_STATE_DIGEST")
        state._last_time = _timestamp(document["last_time"]) if document["last_time"] is not None else None
        state._seen, state._previous = seen, dict(previous)
        state._numbers, state._sums, state._history = numbers, sums, history
        state._fraction_sum, state._fraction_square = decoded_fractions
        return state


def evaluate(name, parameters, inputs, *, bound_contract, resets=None):
    state = MultiOutputState(name, parameters, bound_contract)
    required = fields_by_port(name, parameters)["frame"]
    if not isinstance(inputs, abc.Mapping) or set(inputs) != {"frame"} or not isinstance(inputs["frame"], abc.Mapping):
        raise node_contracts.NodeContractRefusal("MULTI_NAMED_INPUT_PORTS")
    index, columns = None, {}
    for field in required:
        key = field.lower()
        series = inputs["frame"].get(key)
        if not isinstance(series, pd.Series):
            raise node_contracts.NodeContractRefusal("MULTI_INDEXED_FIELD_REQUIRED")
        if not isinstance(series.index, pd.DatetimeIndex) or series.index.tz is None or series.index.hasnans or not series.index.is_unique or not series.index.is_monotonic_increasing:
            raise node_contracts.NodeContractRefusal("MULTI_CANONICAL_INDEX_REQUIRED")
        if index is None:
            index = series.index
        if not series.index.equals(index):
            raise node_contracts.NodeContractRefusal("MULTI_EXACT_ALIGNMENT_REQUIRED")
        columns[key] = series.tolist()
    resets = ((),) * len(index) if resets is None else resets
    if not isinstance(resets, (list, tuple)) or len(resets) != len(index):
        raise node_contracts.NodeContractRefusal("MULTI_RESET_ARRAY_REQUIRED")
    results = {port: [] for port in sorted(SPECS[name]["outputs"])}
    for i, event_time in enumerate(index):
        produced = state.step({"frame": {key: values[i] for key, values in columns.items()}}, event_time=event_time, reset_reasons=resets[i])
        for port, value in produced.items():
            results[port].append(value)
    return {port: pd.Series(values, index=index, name=port, dtype=object) for port, values in results.items()}


def implementation_for(name):
    def implementation(parameters, inputs, *, evaluation_context=None, _name=name):
        if not isinstance(evaluation_context, abc.Mapping) or not {"bound_contract"} <= set(evaluation_context) or set(evaluation_context) - {"bound_contract", "resets"}:
            raise node_contracts.NodeContractRefusal("MULTI_VERIFIED_EVALUATION_CONTEXT_REQUIRED")
        return evaluate(_name, parameters, inputs, bound_contract=evaluation_context["bound_contract"], resets=evaluation_context.get("resets"))
    return implementation


def _binding_registration(name):
    return registry.registered_contract_binding(component=component_key(name), source_contract=source_contract(name),
        implementation=_binding_rule(name), dependency_boundary=registry.DependencyBoundary("defining_module", (contracts.binding_result, math)))


V2_TYPES = node_contracts._freeze({
    ("analytical.market_frame", 2): {"type_id": "analytical.market_frame", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "named indexed market fields"},
    ("analytical.float64", 2): {"type_id": "analytical.float64", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "indexed NumericValue float64 cells"},
})
V2_COMPONENTS = node_contracts._freeze({component_key(name): descriptor(name) for name in NAMES})
NODE_CONTRACTS = node_contracts._freeze({component_key(name): source_contract(name) for name in NAMES})
DATA_REQUIREMENTS = node_contracts._freeze({})
CONTRACT_BINDINGS = node_contracts._freeze({component_key(name): _binding_registration(name) for name in NAMES})
V2_IMPLEMENTATIONS = node_contracts._freeze({component_key(name): registry.registered_v2_implementation(
    component=component_key(name), implementation=implementation_for(name),
    dependency_boundary=registry.DependencyBoundary("defining_module", (abc, pd, math, decimal, _decimal, fractions, hashing, node_contracts, registry, validity, common, contracts)),
) for name in NAMES})
