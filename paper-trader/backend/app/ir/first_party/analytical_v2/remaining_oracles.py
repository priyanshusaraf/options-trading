"""Unpublished remaining-oracles v2 candidates and typed refusal facts.

The sealed matrix supplies immutable semantics and source identities. This module
uses the existing registry/compiler/validity authorities but is not composed into
the product registry and grants no paper, live, provider or deployment authority.
"""
from __future__ import annotations

import collections.abc as abc
import decimal
import _decimal
import math

import pandas as pd

from app.ir import hashing, node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import common, contracts

# BEGIN immutable accepted matrix facts; regenerate, do not hand-edit.
SPECS = node_contracts._freeze({'EWMA_VOLATILITY': {'constraints': [],
                     'decision': 'REPLACE_V2',
                     'dependencies': [],
                     'execution_form': 'RECURSIVE',
                     'first_valid_index': 'seed_window',
                     'formula': 'r=close[t]/close[t-1]-1. Seed variance=mean(r^2) over seed_window returns. '
                                'Thereafter variance=decay*previous_variance+(1-decay)*r^2. Return '
                                'sqrt(variance*periods_per_year). No pandas bias correction or implicit mean '
                                'subtraction.',
                     'inputs': ['close'],
                     'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                       'NaN/infinity/missing bar yields an invalid output and restarts '
                                       'contiguous warmup; never substitute close, zero, prior price or '
                                       'peer=open.',
                     'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
                     'parameters': {'decay': {'default': 0.94,
                                              'maximum': 0.999999,
                                              'minimum': 1e-06,
                                              'type': 'finite_number'},
                                    'periods_per_year': {'default': 1,
                                                         'maximum': 1000000,
                                                         'minimum': 1,
                                                         'type': 'finite_number'},
                                    'seed_window': {'default': 14,
                                                    'maximum': 4096,
                                                    'minimum': 2,
                                                    'type': 'exact_integer'}},
                     'refusal': None,
                     'seed': 'Mean squared simple returns over the first seed_window complete changes; '
                             'serialize previous variance and close.',
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
                     'variant': 'zero_mean_squared_return_ewma',
                     'wave': 'remaining-oracles',
                     'zero_undefined_policy': 'Valid zero returns yield 0; invalid/missing prices reset seed, '
                                              'never fill.'},
 'GARMAN_KLASS': {'constraints': [],
                  'decision': 'REFUSE',
                  'dependencies': [],
                  'execution_form': 'STATELESS',
                  'first_valid_index': 'never valid while refused',
                  'formula': 'Always refuse PRIMARY_GK_VARIANT_UNVERIFIED. Do not replace the intended '
                             'simplified no-opening-jump Garman-Klass estimator with a different opening-jump '
                             'benchmark merely because another paper is available.',
                  'inputs': ['open', 'high', 'low', 'close'],
                  'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                    'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                    'warmup; never substitute close, zero, prior price or peer=open.',
                  'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
                  'parameters': {'periods_per_year': {'default': 1,
                                                      'maximum': 1000000,
                                                      'minimum': 1,
                                                      'type': 'finite_number'},
                                 'window': {'default': 14,
                                            'maximum': 4096,
                                            'minimum': 2,
                                            'type': 'exact_integer'}},
                  'refusal': {'code': 'PRIMARY_GK_VARIANT_UNVERIFIED',
                              'future_requirement': 'Retrieve and inspect the original Garman-Klass 1980 '
                                                    'intended estimator equation and its exact '
                                                    'domain/annualization conventions, then assign independent '
                                                    'vectors. A different estimator cannot substitute for '
                                                    'missing source proof.',
                              'release_owner': 'post-phase5-indicator-accuracy-deferred-source-replan'},
                  'seed': 'No numeric initialization or result is authorized while refused.',
                  'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                   'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                   'recursive math just because the civil date changes. Reset on '
                                   'discontinuity, identity change or explicit reset.',
                  'source': 'REFUSAL',
                  'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                       'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                       'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                       'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                       'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                       'sha256:e83da220d7eb2416cc780504c346f7f5abd6dffecb54b3a01ea014d643bc9418'),
                  'threshold_class': 'REFUSAL_ONLY',
                  'variant': 'garman_klass-v2',
                  'wave': 'remaining-oracles',
                  'zero_undefined_policy': 'No numeric value is authorized while refused.'},
 'ICHIMOKU_COMPONENTS': {'constraints': [],
                         'decision': 'REFUSE',
                         'dependencies': [],
                         'execution_form': 'RECURSIVE',
                         'first_valid_index': 'never valid while refused',
                         'formula': 'Always refuse NUMERICAL_CONVENTION_UNVERIFIED. The required public '
                                    'parameters/output names are reserved for a later approved source '
                                    'contract, but no seed, displacement convention or numeric value is '
                                    'invented.',
                         'inputs': ['high', 'low', 'close'],
                         'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                           'call. NaN/infinity/missing bar yields an invalid output and '
                                           'restarts contiguous warmup; never substitute close, zero, prior '
                                           'price or peer=open.',
                         'outputs': {'chikou': {'dtype': 'float64_series', 'units': 'input_units'},
                                     'kijun': {'dtype': 'float64_series', 'units': 'input_units'},
                                     'senkou_a': {'dtype': 'float64_series', 'units': 'input_units'},
                                     'senkou_b': {'dtype': 'float64_series', 'units': 'input_units'},
                                     'tenkan': {'dtype': 'float64_series', 'units': 'input_units'}},
                         'parameters': {'base_length': {'default': 26,
                                                        'maximum': 4096,
                                                        'minimum': 2,
                                                        'type': 'exact_integer'},
                                        'conversion_length': {'default': 9,
                                                              'maximum': 4096,
                                                              'minimum': 2,
                                                              'type': 'exact_integer'},
                                        'displacement': {'default': 26,
                                                         'maximum': 4096,
                                                         'minimum': 0,
                                                         'type': 'exact_integer'},
                                        'span_b_length': {'default': 52,
                                                          'maximum': 4096,
                                                          'minimum': 2,
                                                          'type': 'exact_integer'}},
                         'refusal': {'code': 'NUMERICAL_CONVENTION_UNVERIFIED',
                                     'future_requirement': 'Separate owner-approved primary-source/convention '
                                                           'replan, then independent seed/state/displacement '
                                                           'vectors. No TradingView access or borrowed '
                                                           'library. Ichimoku must prove that chart shifts '
                                                           'never backfill future data into historical '
                                                           'decisions.',
                                     'release_owner': 'post-phase5-indicator-accuracy-deferred-source-replan'},
                         'seed': 'No numeric initialization is authorized while refused.',
                         'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                          'instrument/timeframe/adjustment identity; do not reset ordinary '
                                          'rolling or recursive math just because the civil date changes. '
                                          'Reset on discontinuity, identity change or explicit reset.',
                         'source': 'REFUSAL',
                         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                              'sha256:e83da220d7eb2416cc780504c346f7f5abd6dffecb54b3a01ea014d643bc9418'),
                         'threshold_class': 'REFUSAL_ONLY',
                         'variant': 'ichimoku_components-v2',
                         'wave': 'remaining-oracles',
                         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                  'never a finite substitute.'},
 'PARKINSON': {'constraints': ['all prices > 0', 'canonical high >= low'],
               'decision': 'REPLACE_V2',
               'dependencies': [],
               'execution_form': 'ROLLING',
               'first_valid_index': 'window - 1',
               'formula': 'sqrt(mean(log(high/low)^2)/(4*log(2))*periods_per_year), Yang-Zhang 2000 equation '
                          '(2).',
               'inputs': ['high', 'low'],
               'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                 'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                 'warmup; never substitute close, zero, prior price or peer=open.',
               'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
               'parameters': {'periods_per_year': {'default': 1,
                                                   'maximum': 1000000,
                                                   'minimum': 1,
                                                   'type': 'finite_number'},
                              'window': {'default': 14,
                                         'maximum': 4096,
                                         'minimum': 2,
                                         'type': 'exact_integer'}},
               'refusal': None,
               'seed': 'No recursive seed; trailing closed window only.',
               'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                'recursive math just because the civil date changes. Reset on discontinuity, '
                                'identity change or explicit reset.',
               'source': 'PAPER:YZ:2',
               'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                    'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                    'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                    'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                    'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                    'sha256:3cffec0643654ca22db333f6fdf4688ab6be836d53942b5cfd04643588e44911'),
               'threshold_class': 'NONRECURSIVE',
               'variant': 'parkinson-v2',
               'wave': 'remaining-oracles',
               'zero_undefined_policy': 'Equal finite positive high/low gives 0; negative radicand is '
                                        'invalid.'},
 'REALIZED_VOLATILITY': {'constraints': [],
                         'decision': 'KEEP',
                         'dependencies': [],
                         'execution_form': 'ROLLING',
                         'first_valid_index': 'window',
                         'formula': 'sqrt(sum((r-mean(r))^2)/window)*sqrt(periods_per_year), '
                                    'r=close[t]/close[t-1]-1. Explicit population standard deviation of simple '
                                    'returns; not realized quadratic variation.',
                         'inputs': ['close'],
                         'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                           'call. NaN/infinity/missing bar yields an invalid output and '
                                           'restarts contiguous warmup; never substitute close, zero, prior '
                                           'price or peer=open.',
                         'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
                         'parameters': {'periods_per_year': {'default': 1,
                                                             'maximum': 1000000,
                                                             'minimum': 1,
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
                         'source': 'STATISTICS',
                         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                              'sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe'),
                         'threshold_class': 'NONRECURSIVE',
                         'variant': 'population_simple_return_volatility',
                         'wave': 'remaining-oracles',
                         'zero_undefined_policy': 'Valid constant returns yield 0; zero/nonpositive price '
                                                  'inputs are invalid.'},
 'ROGERS_SATCHELL': {'constraints': ['all prices > 0', 'valid canonical OHLC envelope'],
                     'decision': 'REPLACE_V2',
                     'dependencies': [],
                     'execution_form': 'ROLLING',
                     'first_valid_index': 'window - 1',
                     'formula': 'sqrt(mean(log(high/open)*log(high/close)+log(low/open)*log(low/close))*periods_per_year).',
                     'inputs': ['open', 'high', 'low', 'close'],
                     'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                       'NaN/infinity/missing bar yields an invalid output and restarts '
                                       'contiguous warmup; never substitute close, zero, prior price or '
                                       'peer=open.',
                     'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
                     'parameters': {'periods_per_year': {'default': 1,
                                                         'maximum': 1000000,
                                                         'minimum': 1,
                                                         'type': 'finite_number'},
                                    'window': {'default': 14,
                                               'maximum': 4096,
                                               'minimum': 2,
                                               'type': 'exact_integer'}},
                     'refusal': None,
                     'seed': 'No recursive seed; trailing closed window only.',
                     'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                      'instrument/timeframe/adjustment identity; do not reset ordinary rolling '
                                      'or recursive math just because the civil date changes. Reset on '
                                      'discontinuity, identity change or explicit reset.',
                     'source': 'PAPER:RS',
                     'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                          'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                          'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                          'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                          'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                          'sha256:22d07345c6b50edfafe30cc0efd2d06b72e277957c0857a154e05d17fe2e678b'),
                     'threshold_class': 'NONRECURSIVE',
                     'variant': 'rogers_satchell-v2',
                     'wave': 'remaining-oracles',
                     'zero_undefined_policy': 'Negative radicand is invalid; no arbitrary clipping. Exact zero '
                                              'yields 0.'},
 'SUPERTREND': {'constraints': [],
                'decision': 'REFUSE',
                'dependencies': [],
                'execution_form': 'RECURSIVE',
                'first_valid_index': 'never valid while refused',
                'formula': 'Always refuse NUMERICAL_CONVENTION_UNVERIFIED. The required public '
                           'parameters/output names are reserved for a later approved source contract, but no '
                           'seed, displacement convention or numeric value is invented.',
                'inputs': ['high', 'low', 'close'],
                'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                  'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                  'warmup; never substitute close, zero, prior price or peer=open.',
                'outputs': {'direction': {'dtype': 'nullable_signed_direction_series',
                                          'units': 'direction_minus1_plus1'},
                            'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                'parameters': {'atr_length': {'default': 14,
                                              'maximum': 4096,
                                              'minimum': 2,
                                              'type': 'exact_integer'},
                               'factor': {'default': 3,
                                          'maximum': 20,
                                          'minimum': 1e-06,
                                          'type': 'finite_number'}},
                'refusal': {'code': 'NUMERICAL_CONVENTION_UNVERIFIED',
                            'future_requirement': 'Separate owner-approved primary-source/convention replan, '
                                                  'then independent seed/state/displacement vectors. No '
                                                  'TradingView access or borrowed library. Ichimoku must prove '
                                                  'that chart shifts never backfill future data into '
                                                  'historical decisions.',
                            'release_owner': 'post-phase5-indicator-accuracy-deferred-source-replan'},
                'seed': 'No numeric initialization is authorized while refused.',
                'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                 'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                 'recursive math just because the civil date changes. Reset on discontinuity, '
                                 'identity change or explicit reset.',
                'source': 'REFUSAL',
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:e83da220d7eb2416cc780504c346f7f5abd6dffecb54b3a01ea014d643bc9418'),
                'threshold_class': 'REFUSAL_ONLY',
                'variant': 'supertrend-v2',
                'wave': 'remaining-oracles',
                'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                         'finite substitute.'},
 'VOLATILITY_PERCENTILE': {'constraints': [],
                           'decision': 'REPLACE_V2',
                           'dependencies': ['REALIZED_VOLATILITY', 'PERCENTILE_RANK'],
                           'execution_form': 'ROLLING',
                           'first_valid_index': 'vol_window + rank_window - 1',
                           'formula': 'Compute REALIZED_VOLATILITY(vol_window,periods_per_year=1), then '
                                      'average-tie percentile rank of that volatility over rank_window '
                                      'complete volatility values. Never rank close.',
                           'inputs': ['close'],
                           'missing_policy': 'Missing declared field/role or unavailable binding refuses the '
                                             'call. NaN/infinity/missing bar yields an invalid output and '
                                             'restarts contiguous warmup; never substitute close, zero, prior '
                                             'price or peer=open.',
                           'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentile_0_to_100'}},
                           'parameters': {'rank_window': {'default': 14,
                                                          'maximum': 4096,
                                                          'minimum': 2,
                                                          'type': 'exact_integer'},
                                          'vol_window': {'default': 14,
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
                           'variant': 'volatility_percentile-v2',
                           'wave': 'remaining-oracles',
                           'zero_undefined_policy': 'Zero divisor or mathematically undefined result is '
                                                    'invalid, never a finite substitute.'},
 'VOLATILITY_RANK': {'constraints': [],
                     'decision': 'REPLACE_V2',
                     'dependencies': ['REALIZED_VOLATILITY'],
                     'execution_form': 'ROLLING',
                     'first_valid_index': 'vol_window + rank_window - 1',
                     'formula': 'Compute REALIZED_VOLATILITY(vol_window,periods_per_year=1); return '
                                '100*(vol-min(vol,rank_window))/(max(vol,rank_window)-min(vol,rank_window)). '
                                'This is range rank, distinct from percentile rank and never close-price rank.',
                     'inputs': ['close'],
                     'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                       'NaN/infinity/missing bar yields an invalid output and restarts '
                                       'contiguous warmup; never substitute close, zero, prior price or '
                                       'peer=open.',
                     'outputs': {'value': {'dtype': 'float64_series', 'units': 'range_rank_0_to_100'}},
                     'parameters': {'rank_window': {'default': 14,
                                                    'maximum': 4096,
                                                    'minimum': 2,
                                                    'type': 'exact_integer'},
                                    'vol_window': {'default': 14,
                                                   'maximum': 4096,
                                                   'minimum': 2,
                                                   'type': 'exact_integer'}},
                     'refusal': None,
                     'seed': 'No recursive seed; trailing closed window only.',
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
                     'threshold_class': 'NONRECURSIVE',
                     'variant': 'volatility_rank-v2',
                     'wave': 'remaining-oracles',
                     'zero_undefined_policy': 'A zero volatility range is undefined and invalid; do not label '
                                              'it as a zero percentile.'},
 'YANG_ZHANG': {'constraints': ['window >= 2', 'all prices > 0', 'valid canonical OHLC envelope'],
                'decision': 'REPLACE_V2',
                'dependencies': ['ROGERS_SATCHELL'],
                'execution_form': 'ROLLING',
                'first_valid_index': 'window',
                'formula': 'Let o=ln(open/previous_close), c=ln(close/open), '
                           'RS=mean(ln(high/open)*ln(high/close)+ln(low/open)*ln(low/close)). '
                           'k=0.34/(1.34+(window+1)/(window-1)). Return '
                           'sqrt((sample_variance(o)+k*sample_variance(c)+(1-k)*RS)*periods_per_year), using '
                           'ddof=1 for both sample variances.',
                'inputs': ['open', 'high', 'low', 'close'],
                'missing_policy': 'Missing declared field/role or unavailable binding refuses the call. '
                                  'NaN/infinity/missing bar yields an invalid output and restarts contiguous '
                                  'warmup; never substitute close, zero, prior price or peer=open.',
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_volatility'}},
                'parameters': {'periods_per_year': {'default': 1,
                                                    'maximum': 1000000,
                                                    'minimum': 1,
                                                    'type': 'finite_number'},
                               'window': {'default': 14,
                                          'maximum': 4096,
                                          'minimum': 2,
                                          'type': 'exact_integer'}},
                'refusal': None,
                'seed': 'No recursive seed; trailing closed window only.',
                'session_reset': 'Carry across verified adjacent sessions within the same canonical '
                                 'instrument/timeframe/adjustment identity; do not reset ordinary rolling or '
                                 'recursive math just because the civil date changes. Reset on discontinuity, '
                                 'identity change or explicit reset.',
                'source': 'PAPER:YZ:7,10',
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:3cffec0643654ca22db333f6fdf4688ab6be836d53942b5cfd04643588e44911'),
                'threshold_class': 'NONRECURSIVE',
                'variant': 'yang_zhang-v2',
                'wave': 'remaining-oracles',
                'zero_undefined_policy': 'Negative radicand is invalid; exact zero yields 0. The old fixed '
                                         '0.34/0.66 weights are rejected.'}})
# END immutable accepted matrix facts.

ALL_NAMES = tuple(sorted(SPECS))
NAMES = tuple(name for name in ALL_NAMES if SPECS[name]["decision"] != "REFUSE")
REFUSED_NAMES = tuple(name for name in ALL_NAMES if SPECS[name]["decision"] == "REFUSE")


def refusal_for(name):
    if name not in REFUSED_NAMES:
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_REFUSAL_UNKNOWN")
    refusal = SPECS[name]["refusal"]
    return node_contracts._freeze({
        "schema": "analytical-unavailable-component/1",
        "component_id": "analytical." + name.lower(),
        "semantic_version": 2,
        "decision": "REFUSE",
        "code": refusal["code"],
        "release_owner": refusal["release_owner"],
        "future_requirement": refusal["future_requirement"],
        "inputs": tuple(SPECS[name]["inputs"]),
        "outputs": SPECS[name]["outputs"],
        "parameters": SPECS[name]["parameters"],
        "source_addresses": SPECS[name]["source_addresses"],
        "executable": False,
    })


REFUSALS = node_contracts._freeze({name: refusal_for(name) for name in REFUSED_NAMES})


def refuse(name, *, inputs=None, parameters=None, capability_verified=False):
    """The advertised negative boundary is invariant to plausible caller facts."""
    record = refusal_for(name)
    raise node_contracts.NodeContractRefusal(record["code"])


def component_key(name):
    if name in REFUSED_NAMES:
        raise node_contracts.NodeContractRefusal(SPECS[name]["refusal"]["code"])
    if name not in NAMES:
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_COMPONENT_UNAVAILABLE")
    return ("analytical." + name.lower(), 2)


def parameters_for(name, parameters=None):
    component_key(name)
    supplied = {} if parameters is None else parameters
    specs = SPECS[name]["parameters"]
    if not isinstance(supplied, abc.Mapping) or set(supplied) - set(specs):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_PARAMETERS_UNKNOWN")
    result = {}
    for key, spec in specs.items():
        value = supplied.get(key, spec["default"])
        if spec["type"] == "exact_integer":
            if type(value) is not int:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_PARAMETER_NOT_EXACT_INTEGER")
        elif type(value) not in {int, float} or not math.isfinite(value):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_PARAMETER_NOT_FINITE")
        if not spec["minimum"] <= value <= spec["maximum"]:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_PARAMETER_OUT_OF_DOMAIN")
        result[key] = value
    return node_contracts._freeze(result)


def fields_by_port(name):
    component_key(name)
    return node_contracts._freeze({"frame": tuple(sorted(field.upper() for field in SPECS[name]["inputs"]))})


def first_valid_index(name, parameters=None):
    values = parameters_for(name, parameters)
    rule = SPECS[name]["first_valid_index"]
    if rule == "window":
        return values["window"]
    if rule == "window - 1":
        return values["window"] - 1
    if rule == "seed_window":
        return values["seed_window"]
    if rule == "vol_window + rank_window - 1":
        return values["vol_window"] + values["rank_window"] - 1
    raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_WARMUP_RULE_UNKNOWN")


def _port(port_id, direction):
    result = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "market_frame" if direction == "input" else "analytical_value",
        "type_ref": {"type_id": "analytical.market_frame" if direction == "input" else "analytical.float64",
                     "type_version": 2},
        "shape": "series",
    }
    if direction == "input":
        result["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return result


def descriptor(name):
    key = component_key(name)
    parameters = {}
    for field, spec in SPECS[name]["parameters"].items():
        parameters[field] = {
            "type": "int" if spec["type"] == "exact_integer" else "float",
            "required": False,
            "default": spec["default"],
            "enum": None,
            "domain": {"minimum": spec["minimum"], "maximum": spec["maximum"]},
            "units": "bars" if field.endswith("window") or field == "window" else
                     "periods_per_year" if field == "periods_per_year" else "fraction",
            "serialization": "canonical-json",
        }
    return node_contracts._freeze({
        "component_id": key[0], "component_version": 2, "domain_family": "indicator",
        "structural_role": "transform", "parameters": parameters,
        "ports": [_port("frame", "input"), _port("value", "output")],
    })


def _binding_rule(name):
    parameter_specs = tuple((key, spec["type"], spec["minimum"], spec["maximum"])
                            for key, spec in sorted(SPECS[name]["parameters"].items()))
    fields = tuple(fields_by_port(name).items())
    rule = SPECS[name]["first_valid_index"]
    builder = contracts.binding_result

    def bind(parameters, inputs, _spec=(parameter_specs, fields, rule, builder)):
        parameter_specs, fields, rule, builder = _spec
        if set(parameters) != {row[0] for row in parameter_specs}:
            raise ValueError("exact canonical parameters required")
        for key, kind, minimum, maximum in parameter_specs:
            value = parameters[key]
            if kind == "exact_integer":
                if type(value) is not int:
                    raise ValueError("exact integer required")
            elif type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError("finite number required")
            if not minimum <= value <= maximum:
                raise ValueError("parameter bounds")
        if rule == "window":
            history = parameters["window"]
        elif rule == "window - 1":
            history = parameters["window"] - 1
        elif rule == "seed_window":
            history = parameters["seed_window"]
        elif rule == "vol_window + rank_window - 1":
            history = parameters["vol_window"] + parameters["rank_window"] - 1
        else:
            raise ValueError("unknown warmup rule")
        return builder(inputs, fields_by_port=dict(fields), warmup_history=history,
                       output_warmup={"value": history})

    return bind


def source_contract(name):
    key = component_key(name)
    rule = {"rule_id": key[0] + ".binding", "rule_version": 1}
    profile = {
        "compute_microseconds_per_event": 250000,
        "memory_bytes_upper_bound": 67108864,
        "history_bytes_upper_bound": 16777216,
        "state_bytes_upper_bound": 33554432,
        "storage_bytes_per_day_upper_bound": 0,
        "subscription_count_upper_bound": 1,
        "fanout_upper_bound": 1,
    }
    return node_contracts._freeze({
        "schema": "first-party-node-contract/2", "stable_node_id": key[0], "semantic_version": 2,
        "visible_family": "TYPE_2", "input_types": {"frame": "analytical.market_frame/series"},
        "output_types": {"value": "analytical.float64/series"},
        "required_market_fields": sorted(SPECS[name]["inputs"]),
        "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
        "warmup_history": rule, "execution_form": SPECS[name]["execution_form"],
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/2",
                               "reasons": ["DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE"]},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY", "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"], "streaming_support": True, "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [], "resource_profile": profile,
        "reference_provenance": sorted(set(SPECS[name]["source_addresses"] +
                                            (hashing.content_address(node_contracts._plain(SPECS[name])),))),
        "parameter_binding": {"scheme": "analytical-contract-binding/1", **rule,
                              "parameter_names": sorted(SPECS[name]["parameters"]), "input_ports": ["frame"]},
    })


def _binding_registration(name):
    return registry.registered_contract_binding(
        component=component_key(name), source_contract=source_contract(name), implementation=_binding_rule(name),
        dependency_boundary=registry.DependencyBoundary("defining_module", (contracts.binding_result, math)),
    )


def _check_bound(name, parameters, bound):
    if not isinstance(bound, contracts.ResolvedNodeContract):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_VERIFIED_BINDING_REQUIRED")
    replay = contracts.materialize_node_contract(source_contract(name), _binding_registration(name), parameters,
                                                 bound.document["input_binding"])
    if replay.bound_contract_address != bound.bound_contract_address:
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_BINDING_REPLAY_MISMATCH")
    key = component_key(name)
    document = bound.document
    if (dict(document["component"]) != {"component_id": key[0], "component_version": 2}
            or dict(document["parameters"]) != dict(parameters)
            or document["source_contract_address"] != hashing.content_address(node_contracts._plain(source_contract(name)))
            or document["resolved_contract"]["warmup_history"] != first_valid_index(name, parameters)
            or dict(document["resolved_contract"]["output_warmup"]) !=
            {"value": first_valid_index(name, parameters)}):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_BINDING_MISMATCH")
    _check_bound_inputs(name, document["input_binding"]["ports"])


def _check_bound_inputs(name, ports):
    if set(ports) != {"frame"}:
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_INPUT_ROLES")
    fact = ports["frame"]["binding"]
    if (not set(fields_by_port(name)["frame"]) <= set(fact["fields"])
            or dict(fact["alignment"]) != {"kind": "EXACT", "maximum_skew_seconds": 0}):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_CANONICAL_BINDING_REQUIRED")


def _context():
    return _decimal.Context(prec=120, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
                            capitals=1, clamp=0, flags=[],
                            traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow])


def _d(value):
    return decimal.Decimal.from_float(float(value))


def _timestamp(value):
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError("timezone required")
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_CANONICAL_TIME_REQUIRED") from exc


def _layout(name, parameters):
    if name == "EWMA_VOLATILITY":
        return {"seed": parameters["seed_window"]}
    if name == "REALIZED_VOLATILITY":
        return {"returns": parameters["window"]}
    if name in {"PARKINSON", "ROGERS_SATCHELL"}:
        return {"terms": parameters["window"]}
    if name == "YANG_ZHANG":
        return {key: parameters["window"] for key in ("overnight", "intraday", "rs")}
    return {"returns": parameters["vol_window"], "volatility": parameters["rank_window"]}


class RemainingOracleState:
    """Bounded completed-bar state with closed restart identity."""

    def __init__(self, name, parameters, bound_contract):
        self.name = name
        self.parameters = parameters_for(name, parameters)
        _check_bound(name, self.parameters, bound_contract)
        self.bound_contract = bound_contract
        self.first = first_valid_index(name, self.parameters)
        self._limits = _layout(name, self.parameters)
        self._last_time = None
        self._clear()

    def _clear(self):
        self._seen = 0
        self._previous_close = None
        self._history = {key: [] for key in self._limits}
        self._sums = {key: decimal.Decimal(0) for key in self._limits}
        self._squares = {key: decimal.Decimal(0) for key in self._limits}
        self._variance = None

    def _push(self, key, value):
        values = self._history[key]
        old = values.pop(0) if len(values) == self._limits[key] else None
        values.append(value)
        self._sums[key] += value - (old if old is not None else 0)
        self._squares[key] += value * value - (old * old if old is not None else 0)

    def _population_volatility(self, key, length, periods_per_year=1):
        mean = self._sums[key] / length
        variance = self._squares[key] / length - mean * mean
        radicand = variance * _d(periods_per_year)
        return None if radicand < 0 else radicand.sqrt()

    def _advance(self, row):
        name, p = self.name, self.parameters
        if name == "PARKINSON":
            log_range = row["high"].ln() - row["low"].ln()
            self._push("terms", log_range * log_range)
            if len(self._history["terms"]) < p["window"]:
                return None
            radicand = self._sums["terms"] / p["window"] / (decimal.Decimal(4) * decimal.Decimal(2).ln()) * _d(p["periods_per_year"])
            return None if radicand < 0 else radicand.sqrt()
        if name == "ROGERS_SATCHELL":
            term = ((row["high"].ln() - row["open"].ln()) * (row["high"].ln() - row["close"].ln())
                    + (row["low"].ln() - row["open"].ln()) * (row["low"].ln() - row["close"].ln()))
            self._push("terms", term)
            if len(self._history["terms"]) < p["window"]:
                return None
            radicand = self._sums["terms"] / p["window"] * _d(p["periods_per_year"])
            return None if radicand < 0 else radicand.sqrt()
        close = row["close"]
        previous = self._previous_close
        self._previous_close = close
        if previous is None:
            return None
        if name == "EWMA_VOLATILITY":
            change = (close - previous) / previous
            squared = change * change
            if self._variance is None:
                self._push("seed", squared)
                if len(self._history["seed"]) < p["seed_window"]:
                    return None
                self._variance = self._sums["seed"] / p["seed_window"]
                self._history["seed"].clear()
                self._sums["seed"] = self._squares["seed"] = decimal.Decimal(0)
            else:
                decay = _d(p["decay"])
                self._variance = decay * self._variance + (decimal.Decimal(1) - decay) * squared
            return (self._variance * _d(p["periods_per_year"])).sqrt()
        change = (close - previous) / previous
        if name in {"REALIZED_VOLATILITY", "VOLATILITY_PERCENTILE", "VOLATILITY_RANK"}:
            self._push("returns", change)
            required = p.get("window", p.get("vol_window"))
            if len(self._history["returns"]) < required:
                return None
            volatility = self._population_volatility("returns", required, p.get("periods_per_year", 1))
            if name == "REALIZED_VOLATILITY" or volatility is None:
                return volatility
            self._push("volatility", volatility)
            if len(self._history["volatility"]) < p["rank_window"]:
                return None
            values = self._history["volatility"]
            current = values[-1]
            if name == "VOLATILITY_PERCENTILE":
                less = sum(value < current for value in values)
                equal = sum(value == current for value in values)
                return decimal.Decimal(100) * (decimal.Decimal(less) + (decimal.Decimal(equal) + 1) / 2) / len(values)
            low, high = min(values), max(values)
            return None if high == low else decimal.Decimal(100) * (current - low) / (high - low)
        overnight = row["open"].ln() - previous.ln()
        intraday = row["close"].ln() - row["open"].ln()
        rs = ((row["high"].ln() - row["open"].ln()) * (row["high"].ln() - row["close"].ln())
              + (row["low"].ln() - row["open"].ln()) * (row["low"].ln() - row["close"].ln()))
        for key, value in (("overnight", overnight), ("intraday", intraday), ("rs", rs)):
            self._push(key, value)
        window = p["window"]
        if len(self._history["overnight"]) < window:
            return None
        def sample_variance(key):
            return (self._squares[key] - self._sums[key] * self._sums[key] / window) / (window - 1)
        k = decimal.Decimal("0.34") / (decimal.Decimal("1.34") + decimal.Decimal(window + 1) / (window - 1))
        radicand = (sample_variance("overnight") + k * sample_variance("intraday")
                    + (1 - k) * self._sums["rs"] / window) * _d(p["periods_per_year"])
        return None if radicand < 0 else radicand.sqrt()

    def step(self, inputs, *, event_time, reset_reasons=(), event_kind="completed_bar"):
        if event_kind != "completed_bar":
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_COMPLETED_BAR_REQUIRED")
        timestamp = _timestamp(event_time)
        if self._last_time is not None and timestamp <= self._last_time:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_EVENT_ORDER")
        reasons = common.contract_reset_reasons(self.bound_contract, reset_reasons)
        if not isinstance(inputs, abc.Mapping) or set(inputs) != {"frame"} or not isinstance(inputs["frame"], abc.Mapping):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_NAMED_INPUT_PORTS")
        cells = {field.lower(): common.required_numeric_scalar(inputs["frame"], field.lower())
                 for field in fields_by_port(self.name)["frame"]}
        bad = validity.propagate(cells.values())
        if bad is None:
            raw = {key: cell.value for key, cell in cells.items()}
            if (any(value <= 0 for value in raw.values())
                    or "high" in raw and "low" in raw and raw["high"] < raw["low"]
                    or "open" in raw and not raw["low"] <= raw["open"] <= raw["high"]
                    or "close" in raw and "high" in raw and not raw["low"] <= raw["close"] <= raw["high"]):
                bad = validity.invalid(validity.ValidityState.INVALID)
        self._last_time = timestamp
        if reasons or bad is not None:
            self._clear()
        if bad is not None:
            return {"value": bad}
        n = self._seen
        with decimal.localcontext(_context()):
            number = self._advance({key: _d(value) for key, value in raw.items()})
        self._seen = min(n + 1, self.first + 1)
        if n < self.first:
            return {"value": validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY)}
        if number is None or not math.isfinite(float(number)):
            return {"value": validity.invalid(validity.ValidityState.MATHEMATICALLY_UNDEFINED)}
        return {"value": validity.valid(float(number))}

    def snapshot(self):
        body = {
            "schema": "analytical-remaining-oracle-state/2", "component": list(component_key(self.name)),
            "bound_contract_address": self.bound_contract.bound_contract_address,
            "parameters": node_contracts._plain(self.parameters), "seen": self._seen,
            "last_time": self._last_time.isoformat() if self._last_time is not None else None,
            "previous_close": str(self._previous_close) if self._previous_close is not None else None,
            "history": {key: [str(value) for value in values] for key, values in self._history.items()},
            "variance": str(self._variance) if self._variance is not None else None,
        }
        return {**body, "payload_address": hashing.content_address(body)}

    @classmethod
    def restore(cls, name, parameters, bound_contract, document):
        state = cls(name, parameters, bound_contract)
        fields = {"schema", "component", "bound_contract_address", "parameters", "seen", "last_time",
                  "previous_close", "history", "variance", "payload_address"}
        if not isinstance(document, abc.Mapping) or set(document) != fields:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_CLOSED_SCHEMA")
        if (document["schema"] != "analytical-remaining-oracle-state/2"
                or document["component"] != list(component_key(name))
                or document["bound_contract_address"] != bound_contract.bound_contract_address
                or not isinstance(document["parameters"], abc.Mapping)
                or hashing.content_address(document["parameters"]) != hashing.content_address(dict(state.parameters))):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_IDENTITY")
        seen = document["seen"]
        if type(seen) is not int or not 0 <= seen <= state.first + 1:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_COUNTER")
        def decode(value):
            if not isinstance(value, str) or len(value) > 256:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_DECIMAL")
            try:
                result = decimal.Decimal(value)
                if not result.is_finite() or str(result) != value or len(result.as_tuple().digits) > 220:
                    raise ValueError("bounded canonical decimal required")
                return result
            except (decimal.DecimalException, ValueError) as exc:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_DECIMAL") from exc
        history_doc = document["history"]
        if not isinstance(history_doc, abc.Mapping) or set(history_doc) != set(state._limits):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_HISTORY_KEYS")
        if name == "EWMA_VOLATILITY":
            expected = {"seed": 0 if seen == state.first + 1 else max(0, seen - 1)}
        elif name == "REALIZED_VOLATILITY":
            expected = {"returns": min(max(0, seen - 1), state.parameters["window"])}
        elif name in {"PARKINSON", "ROGERS_SATCHELL"}:
            expected = {"terms": min(seen, state.parameters["window"])}
        elif name == "YANG_ZHANG":
            expected = {key: min(max(0, seen - 1), state.parameters["window"])
                        for key in ("overnight", "intraday", "rs")}
        else:
            vol_count = max(0, seen - state.parameters["vol_window"])
            expected = {"returns": min(max(0, seen - 1), state.parameters["vol_window"]),
                        "volatility": min(vol_count, state.parameters["rank_window"])}
        history = {}
        for key, count in expected.items():
            values = history_doc[key]
            if not isinstance(values, list) or len(values) != count:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_HISTORY_LENGTH")
            history[key] = [decode(value) for value in values]
        nonnegative = {"seed", "terms", "volatility", "rs"}
        if any(value < 0 for key, values in history.items() if key in nonnegative for value in values):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_HISTORY_DOMAIN")
        if any(value <= -1 for key, values in history.items() if key == "returns" for value in values):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_HISTORY_DOMAIN")
        needs_previous = name not in {"PARKINSON", "ROGERS_SATCHELL"}
        previous = document["previous_close"]
        if needs_previous and seen:
            previous = decode(previous)
            if previous <= 0:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_PREVIOUS")
        elif previous is not None:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_PREVIOUS")
        variance = document["variance"]
        if name == "EWMA_VOLATILITY" and seen == state.first + 1:
            variance = decode(variance)
            if variance < 0:
                raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_VARIANCE")
        elif variance is not None:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_VARIANCE")
        body = {key: value for key, value in document.items() if key != "payload_address"}
        if hashing.content_address(body) != document["payload_address"]:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_DIGEST")
        if seen and document["last_time"] is None:
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_STATE_CLOCK")
        state._seen = seen
        state._last_time = _timestamp(document["last_time"]) if document["last_time"] is not None else None
        state._previous_close = previous
        state._history = history
        with decimal.localcontext(_context()):
            state._sums = {key: sum(values, decimal.Decimal(0)) for key, values in history.items()}
            state._squares = {key: sum((value * value for value in values), decimal.Decimal(0))
                              for key, values in history.items()}
        state._variance = variance
        return state


def evaluate(name, parameters, inputs, *, bound_contract, resets=None):
    state = RemainingOracleState(name, parameters, bound_contract)
    required = fields_by_port(name)["frame"]
    if not isinstance(inputs, abc.Mapping) or set(inputs) != {"frame"} or not isinstance(inputs["frame"], abc.Mapping):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_NAMED_INPUT_PORTS")
    index, columns = None, {}
    for field in required:
        key = field.lower()
        series = inputs["frame"].get(key)
        if not isinstance(series, pd.Series):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_INDEXED_FIELD_REQUIRED")
        if (not isinstance(series.index, pd.DatetimeIndex) or series.index.tz is None or series.index.hasnans
                or not series.index.is_unique or not series.index.is_monotonic_increasing):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_CANONICAL_INDEX_REQUIRED")
        if index is None:
            index = series.index
        if not series.index.equals(index):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_EXACT_ALIGNMENT_REQUIRED")
        columns[key] = series.tolist()
    resets = ((),) * len(index) if resets is None else resets
    if not isinstance(resets, (list, tuple)) or len(resets) != len(index):
        raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_RESET_ARRAY_REQUIRED")
    result = []
    for i, event_time in enumerate(index):
        row = {"frame": {key: values[i] for key, values in columns.items()}}
        result.append(state.step(row, event_time=event_time, reset_reasons=resets[i])["value"])
    return {"value": pd.Series(result, index=index, name="value", dtype=object)}


def implementation_for(name):
    def implementation(parameters, inputs, *, evaluation_context=None, _name=name):
        if (not isinstance(evaluation_context, abc.Mapping) or "bound_contract" not in evaluation_context
                or set(evaluation_context) - {"bound_contract", "resets"}):
            raise node_contracts.NodeContractRefusal("REMAINING_ORACLE_VERIFIED_EVALUATION_CONTEXT_REQUIRED")
        return evaluate(_name, parameters, inputs, bound_contract=evaluation_context["bound_contract"],
                        resets=evaluation_context.get("resets"))
    return implementation


# Explicit unpublished contributor exports. Shared registry composition is unchanged.
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
    dependency_boundary=registry.DependencyBoundary(
        "defining_module", (abc, decimal, _decimal, math, pd, hashing, node_contracts, registry, validity, common, contracts)
    ),
) for name in NAMES})
