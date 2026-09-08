"""Unpublished core-math v2 candidates.

These are contributors to the existing PlatformRegistry, not a registry or a
publication decision. No module in platform composition imports this module.
Every batch cell and streaming output uses the existing validity.NumericValue envelope.
The data compiler must supply a verified ResolvedNodeContract before evaluation;
this module does not authenticate data or certify provider/calendar authority.
"""
from __future__ import annotations

import math
import collections.abc as abc
import decimal
import _decimal  # Pin the native executor as well as decimal.py in identity.
import fractions

import pandas as pd

from app.ir import hashing, node_contracts, registry, validity
from app.ir.first_party.analytical_v2 import common, contracts


# Immutable source records are inserted below from the accepted, hashed matrix.
# This file never reads an evidence directory at runtime.
SPECS = node_contracts._freeze({'ALPHA': {'decision': 'REPLACE_V2',
           'execution_form': 'ROLLING',
           'first_valid_index': 'window',
           'formula': 'mean(primary simple returns,window) - BETA*mean(peer simple returns,window). This is a per-bar '
                      'return-regression intercept, not CAPM alpha or an annualized metric.',
           'inputs': ['close', 'peer'],
           'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_return'}},
           'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
           'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
           'threshold_class': 'NONRECURSIVE',
           'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                    'substitute.'},
 'BETA': {'decision': 'REPLACE_V2',
          'execution_form': 'ROLLING',
          'first_valid_index': 'window',
          'formula': 'Let x=peer[t]/peer[t-1]-1 and y=primary[t]/primary[t-1]-1. Return '
                     'sum((x-mean(x))*(y-mean(y)))/sum((x-mean(x))^2) over window returns.',
          'inputs': ['close', 'peer'],
          'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
          'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                               'sha256:b9cc2c51cd2eed59ff722b0223094260ed3449dc6cfbe0622245628d6976ba55'),
          'threshold_class': 'NONRECURSIVE',
          'zero_undefined_policy': 'Zero peer-return variance is invalid. TA_BETA receives peer first, primary second on '
                                   'nondegenerate vectors; never invert the roles.'},
 'BETA_ADJUSTED_SPREAD': {'decision': 'REPLACE_V2',
                          'execution_form': 'ROLLING',
                          'first_valid_index': 'window - 1',
                          'formula': 'primary[t] - ROLLING_HEDGE_RATIO*peer[t]; no intercept subtraction.',
                          'inputs': ['close', 'peer'],
                          'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                          'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                          'threshold_class': 'NONRECURSIVE',
                          'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                                   'finite substitute.'},
 'CCI': {'decision': 'KEEP',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window - 1',
         'formula': '(typical_price - rolling_mean(typical_price))/(0.015*mean_absolute_deviation(typical_price)); '
                    'typical_price=(high+low+close)/3.',
         'inputs': ['high', 'low', 'close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:4cb6da9516007df6473f0d135e9ba8ccc7b050487a6479bd0e935d3cb8353ded'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'Pinned TA_CCI returns 0 for a valid zero-deviation window.'},
 'CHAIKIN_MONEY_FLOW': {'decision': 'REPLACE_V2',
                        'execution_form': 'ROLLING',
                        'first_valid_index': 'window - 1',
                        'formula': 'sum(money_flow_multiplier*volume,window)/sum(volume,window); '
                                   'multiplier=(2*close-high-low)/(high-low), valid zero range contributes zero.',
                        'inputs': ['high', 'low', 'close', 'volume'],
                        'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
                        'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                        'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                             'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                             'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                             'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                             'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                        'threshold_class': 'NONRECURSIVE',
                        'zero_undefined_policy': 'Zero-range valid bars contribute zero; a zero total volume window is '
                                                 'invalid.'},
 'CORRELATION': {'decision': 'REPLACE_V2',
                 'execution_form': 'ROLLING',
                 'first_valid_index': 'window - 1',
                 'formula': 'Pearson correlation of aligned trailing primary and peer levels, using the same window for '
                            'both moments.',
                 'inputs': ['close', 'peer'],
                 'outputs': {'value': {'dtype': 'float64_series', 'units': 'correlation_minus1_to1'}},
                 'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                      'sha256:1c49cb42ddaadf9175dbf91bc21f533e2cf520fdf8c3edb30082e85bb6c03fad'),
                 'threshold_class': 'NONRECURSIVE',
                 'zero_undefined_policy': 'Either zero variance makes correlation invalid; this is an explicit '
                                          'undefined-case override, not a TA-Lib zero-result parity claim.'},
 'COVARIANCE': {'decision': 'REPLACE_V2',
                'execution_form': 'ROLLING',
                'first_valid_index': 'window - 1',
                'formula': 'sum((primary-mean(primary))*(peer-mean(peer)))/(window-ddof) over aligned trailing levels.',
                'inputs': ['close', 'peer'],
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'primary_units_times_peer_units'}},
                'parameters': {'ddof': {'default': 0, 'type': 'enum', 'values': [0, 1]},
                               'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:6646a579694dd7ebe304c8d281c46f60d6b038f1b4626691c4381742853edd98'),
                'threshold_class': 'NONRECURSIVE',
                'zero_undefined_policy': 'Constant finite inputs have covariance 0; no missing-data deletion.'},
 'CROSS_ABOVE': {'decision': 'REPLACE_V2',
                 'execution_form': 'STATELESS',
                 'first_valid_index': '1',
                 'formula': 'primary[t] > peer[t] and primary[t-1] <= peer[t-1].',
                 'inputs': ['close', 'peer'],
                 'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
                 'parameters': {},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                 'threshold_class': 'EXACT',
                 'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                          'Unknown, not False.'},
 'CROSS_BELOW': {'decision': 'REPLACE_V2',
                 'execution_form': 'STATELESS',
                 'first_valid_index': '1',
                 'formula': 'primary[t] < peer[t] and primary[t-1] >= peer[t-1].',
                 'inputs': ['close', 'peer'],
                 'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
                 'parameters': {},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                 'threshold_class': 'EXACT',
                 'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                          'Unknown, not False.'},
 'FALLING': {'decision': 'REPLACE_V2',
             'execution_form': 'ROLLING',
             'first_valid_index': 'window',
             'formula': 'Every one of the last window close-to-close differences is strictly negative.',
             'inputs': ['close'],
             'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
             'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
             'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                  'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                  'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                  'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                  'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
             'threshold_class': 'EXACT',
             'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                      'Unknown, not False.'},
 'GAP': {'decision': 'REPLACE_V2',
         'execution_form': 'STATELESS',
         'first_valid_index': '1',
         'formula': 'open[t] - close[t-1] for adjacent canonical bars; not an implicit previous-session lookup.',
         'inputs': ['open', 'close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
         'threshold_class': 'EXACT',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'GAP_DOWN': {'decision': 'REPLACE_V2',
              'execution_form': 'STATELESS',
              'first_valid_index': '1',
              'formula': 'open[t] < close[t-1] for adjacent canonical bars.',
              'inputs': ['open', 'close'],
              'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
              'parameters': {},
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
              'threshold_class': 'EXACT',
              'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                       'Unknown, not False.'},
 'GAP_UP': {'decision': 'REPLACE_V2',
            'execution_form': 'STATELESS',
            'first_valid_index': '1',
            'formula': 'open[t] > close[t-1] for adjacent canonical bars.',
            'inputs': ['open', 'close'],
            'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
            'parameters': {},
            'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
            'threshold_class': 'EXACT',
            'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                     'Unknown, not False.'},
 'HL2': {'decision': 'KEEP',
         'execution_form': 'STATELESS',
         'first_valid_index': '0',
         'formula': '(high + low) / 2; midpoint means bar high/low midpoint, not bid/ask mid.',
         'inputs': ['high', 'low'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:f49f07ae503b4db492f8231b5f300abde33d0eaa64a01907e8535aa5211be7b0'),
         'threshold_class': 'EXACT',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'HLC3': {'decision': 'KEEP',
          'execution_form': 'STATELESS',
          'first_valid_index': '0',
          'formula': '(high + low + close) / 3.',
          'inputs': ['high', 'low', 'close'],
          'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
          'parameters': {},
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                               'sha256:a1ae63259ac9c35718357afe36daa2e09a9216e991dae8a3259a4f9de85091cb'),
          'threshold_class': 'EXACT',
          'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'INSIDE_BAR': {'decision': 'REPLACE_V2',
                'execution_form': 'STATELESS',
                'first_valid_index': '1',
                'formula': 'high[t] < high[t-1] and low[t] > low[t-1]; equality is not inside.',
                'inputs': ['high', 'low'],
                'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
                'parameters': {},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                'threshold_class': 'EXACT',
                'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                         'Unknown, not False.'},
 'LINEAR_REGRESSION_INTERCEPT': {'decision': 'REPLACE_V2',
                                 'execution_form': 'ROLLING',
                                 'first_valid_index': 'window - 1',
                                 'formula': 'OLS intercept of trailing close values against x=0..window-1, evaluated at the '
                                            'oldest x=0.',
                                 'inputs': ['close'],
                                 'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                                 'parameters': {'window': {'default': 14,
                                                           'maximum': 4096,
                                                           'minimum': 2,
                                                           'type': 'exact_integer'}},
                                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                                      'sha256:507fa74f0b7f843198f20d36deb5630a88f97f370392b959dbc651a3995c2357'),
                                 'threshold_class': 'NONRECURSIVE',
                                 'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, '
                                                          'never a finite substitute.'},
 'LINEAR_REGRESSION_SLOPE': {'decision': 'REPLACE_V2',
                             'execution_form': 'ROLLING',
                             'first_valid_index': 'window - 1',
                             'formula': 'OLS slope of trailing close values against x=0..window-1, oldest to newest. No '
                                        'peer input.',
                             'inputs': ['close'],
                             'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units_per_bar'}},
                             'parameters': {'window': {'default': 14,
                                                       'maximum': 4096,
                                                       'minimum': 2,
                                                       'type': 'exact_integer'}},
                             'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                                  'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                                  'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                                  'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                                  'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                                  'sha256:22536abd4e9b31b9296546ce2937ee3481efbdf6c251fa8380aab14262ed7a90'),
                             'threshold_class': 'NONRECURSIVE',
                             'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                                      'finite substitute.'},
 'LOG_RETURN': {'decision': 'REPLACE_V2',
                'execution_form': 'ROLLING',
                'first_valid_index': 'window',
                'formula': 'ln(close[t]/close[t-window]); both endpoint prices must be strictly positive.',
                'inputs': ['close'],
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'log_return'}},
                'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                'threshold_class': 'NONRECURSIVE',
                'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                         'substitute.'},
 'MAD': {'decision': 'REPLACE_V2',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window - 1',
         'formula': 'Arithmetic mean of abs(x - mean(x)) over the trailing window; mean absolute deviation, not median '
                    'absolute deviation.',
         'inputs': ['close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'A constant finite window has mean absolute deviation 0.'},
 'MFI': {'decision': 'REPLACE_V2',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window',
         'formula': 'Pinned TA_MFI: typical-price direction assigns signed money flow to positive/negative sums over window '
                    'periods; ties contribute neither.',
         'inputs': ['high', 'low', 'close', 'volume'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'oscillator_0_to_100'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:d13e838df7bbbe37820bf033384521bea4d5b02a16fc459642b7557fe3d66805'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'Use the pinned TA_MFI small-total-flow/zero-negative-flow convention, with exact masks; '
                                  'no unlabelled ratio division or close fallback.'},
 'MIDPOINT': {'decision': 'KEEP',
              'execution_form': 'STATELESS',
              'first_valid_index': '0',
              'formula': '(high + low) / 2; midpoint means bar high/low midpoint, not bid/ask mid.',
              'inputs': ['high', 'low'],
              'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
              'parameters': {},
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                   'sha256:f49f07ae503b4db492f8231b5f300abde33d0eaa64a01907e8535aa5211be7b0'),
              'threshold_class': 'EXACT',
              'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                       'substitute.'},
 'MOMENTUM': {'decision': 'KEEP',
              'execution_form': 'ROLLING',
              'first_valid_index': 'window',
              'formula': 'close[t] - close[t-window].',
              'inputs': ['close'],
              'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
              'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                   'sha256:e8cead934756816c1ac11da8c8116c559b30cad4f954abcc2d7c332017af6e0c'),
              'threshold_class': 'NONRECURSIVE',
              'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                       'substitute.'},
 'OHLC4': {'decision': 'KEEP',
           'execution_form': 'STATELESS',
           'first_valid_index': '0',
           'formula': '(open + high + low + close) / 4.',
           'inputs': ['open', 'high', 'low', 'close'],
           'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
           'parameters': {},
           'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                'sha256:bfa28cdfa6f15ee7f3b403d1af2f3c1ff03de9cce940661176ac53a0eed6acd5'),
           'threshold_class': 'EXACT',
           'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                    'substitute.'},
 'OUTSIDE_BAR': {'decision': 'REPLACE_V2',
                 'execution_form': 'STATELESS',
                 'first_valid_index': '1',
                 'formula': 'high[t] > high[t-1] and low[t] < low[t-1]; equality is not outside.',
                 'inputs': ['high', 'low'],
                 'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
                 'parameters': {},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                 'threshold_class': 'EXACT',
                 'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                          'Unknown, not False.'},
 'PERCENTILE': {'decision': 'REPLACE_V2',
                'execution_form': 'ROLLING',
                'first_valid_index': 'window - 1',
                'formula': 'Trailing value quantile at q percent using linear interpolation: sort x; h=(window-1)*q/100; '
                           'interpolate between floor(h) and ceil(h). This is a value quantile, not percentile rank.',
                'inputs': ['close'],
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                'parameters': {'q': {'default': 50, 'maximum': 100, 'minimum': 0, 'type': 'finite_number'},
                               'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:c9da6dc7224868b9bd40f241503f28698168be09e8b0555ff65659753042a802'),
                'threshold_class': 'NONRECURSIVE',
                'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                         'substitute.'},
 'PERCENTILE_RANK': {'decision': 'REPLACE_V2',
                     'execution_form': 'ROLLING',
                     'first_valid_index': 'window - 1',
                     'formula': 'For the current value in the trailing window, rank = count(values < current) + '
                                '(count(values == current)+1)/2; ties use average rank including the current observation. '
                                'Return 100*rank/window.',
                     'inputs': ['close'],
                     'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentile_0_to_100'}},
                     'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                     'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                          'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                          'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                          'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                          'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                     'threshold_class': 'NONRECURSIVE',
                     'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                              'substitute.'},
 'PERCENT_RETURN': {'decision': 'KEEP',
                    'execution_form': 'ROLLING',
                    'first_valid_index': 'window',
                    'formula': 'close[t]/close[t-window] - 1; decimal fraction, not percentage points. ROC remains an '
                               'explicitly labelled ROCP-compatible variant.',
                    'inputs': ['close'],
                    'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_return'}},
                    'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
                    'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                         'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                         'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                         'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                         'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                         'sha256:ca513529cb17af56621698d58903cf245cbf84d2860c3eba2be4e2c81649d7d0'),
                    'threshold_class': 'NONRECURSIVE',
                    'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                             'substitute.'},
 'POINT_CHANGE': {'decision': 'KEEP',
                  'execution_form': 'ROLLING',
                  'first_valid_index': 'window',
                  'formula': 'close[t] - close[t-window].',
                  'inputs': ['close'],
                  'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                  'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
                  'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                       'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                       'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                       'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                       'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                       'sha256:e8cead934756816c1ac11da8c8116c559b30cad4f954abcc2d7c332017af6e0c'),
                  'threshold_class': 'NONRECURSIVE',
                  'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                           'substitute.'},
 'RATIO': {'decision': 'REPLACE_V2',
           'execution_form': 'STATELESS',
           'first_valid_index': '0',
           'formula': 'primary[t]/peer[t]; same exact availability timestamp and typed instrument roles.',
           'inputs': ['close', 'peer'],
           'outputs': {'value': {'dtype': 'float64_series', 'units': 'primary_units_per_peer_unit'}},
           'parameters': {},
           'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
           'threshold_class': 'EXACT',
           'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                    'substitute.'},
 'RELATIVE_VOLUME': {'decision': 'REPLACE_V2',
                     'execution_form': 'ROLLING',
                     'first_valid_index': 'window - 1',
                     'formula': 'volume[t]/mean(volume,window), including the current completed bar. Not a time-of-day '
                                'seasonal relative-volume claim.',
                     'inputs': ['volume'],
                     'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
                     'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                     'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                          'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                          'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                          'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                          'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                     'threshold_class': 'NONRECURSIVE',
                     'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                              'substitute.'},
 'RESIDUAL': {'decision': 'REPLACE_V2',
              'execution_form': 'ROLLING',
              'first_valid_index': 'window - 1',
              'formula': 'primary[t] - (intercept + slope*peer[t]); slope=ROLLING_HEDGE_RATIO; '
                         'intercept=mean(primary)-slope*mean(peer).',
              'inputs': ['close', 'peer'],
              'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
              'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
              'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                   'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                   'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                   'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                   'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
              'threshold_class': 'NONRECURSIVE',
              'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                       'substitute.'},
 'RISING': {'decision': 'REPLACE_V2',
            'execution_form': 'ROLLING',
            'first_valid_index': 'window',
            'formula': 'Every one of the last window close-to-close differences is strictly positive.',
            'inputs': ['close'],
            'outputs': {'value': {'dtype': 'nullable_boolean_series', 'units': 'boolean'}},
            'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
            'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
            'threshold_class': 'EXACT',
            'zero_undefined_policy': 'Equality follows the explicitly stated predicate. Missing/invalid inputs yield '
                                     'Unknown, not False.'},
 'ROC': {'decision': 'KEEP',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window',
         'formula': 'close[t]/close[t-window] - 1; decimal fraction, not percentage points. ROC remains an explicitly '
                    'labelled ROCP-compatible variant.',
         'inputs': ['close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_return'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:ca513529cb17af56621698d58903cf245cbf84d2860c3eba2be4e2c81649d7d0'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'ROLLING_HEDGE_RATIO': {'decision': 'REPLACE_V2',
                         'execution_form': 'ROLLING',
                         'first_valid_index': 'window - 1',
                         'formula': 'sum((peer-mean(peer))*(primary-mean(primary)))/sum((peer-mean(peer))^2) over trailing '
                                    'aligned price levels. This is level OLS, distinct from return BETA.',
                         'inputs': ['close', 'peer'],
                         'outputs': {'value': {'dtype': 'float64_series', 'units': 'primary_units_per_peer_unit'}},
                         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                              'sha256:6646a579694dd7ebe304c8d281c46f60d6b038f1b4626691c4381742853edd98'),
                         'threshold_class': 'NONRECURSIVE',
                         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                                  'finite substitute.'},
 'ROLLING_HIGH': {'decision': 'KEEP',
                  'execution_form': 'ROLLING',
                  'first_valid_index': 'window - 1',
                  'formula': 'Maximum of the last window close values; these are value-series maxima, not the high field.',
                  'inputs': ['close'],
                  'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                  'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                  'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                       'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                       'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                       'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                       'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                       'sha256:34130d95f31f3374bc6a2a0270d3a8df834c568ec81cb372cc7fb0f91e026a03'),
                  'threshold_class': 'NONRECURSIVE',
                  'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                           'substitute.'},
 'ROLLING_LOW': {'decision': 'KEEP',
                 'execution_form': 'ROLLING',
                 'first_valid_index': 'window - 1',
                 'formula': 'Minimum of the last window close values; these are value-series minima, not the low field.',
                 'inputs': ['close'],
                 'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                 'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                      'sha256:81358779e0696431b17dad0b2cc5d3e3fad22f3e8615b1ea2122a7b8a9ae7b81'),
                 'threshold_class': 'NONRECURSIVE',
                 'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                          'substitute.'},
 'ROLLING_MAX': {'decision': 'KEEP',
                 'execution_form': 'ROLLING',
                 'first_valid_index': 'window - 1',
                 'formula': 'Maximum of the last window close values; these are value-series maxima, not the high field.',
                 'inputs': ['close'],
                 'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                 'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                      'sha256:34130d95f31f3374bc6a2a0270d3a8df834c568ec81cb372cc7fb0f91e026a03'),
                 'threshold_class': 'NONRECURSIVE',
                 'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                          'substitute.'},
 'ROLLING_MEAN': {'decision': 'KEEP',
                  'execution_form': 'ROLLING',
                  'first_valid_index': 'window - 1',
                  'formula': 'Arithmetic mean of the last window input values, including the current completed bar.',
                  'inputs': ['close'],
                  'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                  'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                  'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                       'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                       'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                       'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                       'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                       'sha256:7110c2fe33f4b8a1d109282ab4d9ece1cf3440ef0bd529c8f73f59a3d1ab53e8'),
                  'threshold_class': 'NONRECURSIVE',
                  'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                           'substitute.'},
 'ROLLING_MEDIAN': {'decision': 'REPLACE_V2',
                    'execution_form': 'ROLLING',
                    'first_valid_index': 'window - 1',
                    'formula': 'Median of the trailing window; even lengths use the arithmetic mean of the two central '
                               'order statistics.',
                    'inputs': ['close'],
                    'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                    'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                    'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                         'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                         'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                         'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                         'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                    'threshold_class': 'NONRECURSIVE',
                    'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                             'substitute.'},
 'ROLLING_MIN': {'decision': 'KEEP',
                 'execution_form': 'ROLLING',
                 'first_valid_index': 'window - 1',
                 'formula': 'Minimum of the last window close values; these are value-series minima, not the low field.',
                 'inputs': ['close'],
                 'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                 'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                 'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                      'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                      'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                      'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                      'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                      'sha256:81358779e0696431b17dad0b2cc5d3e3fad22f3e8615b1ea2122a7b8a9ae7b81'),
                 'threshold_class': 'NONRECURSIVE',
                 'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                          'substitute.'},
 'ROLLING_RANK': {'decision': 'REPLACE_V2',
                  'execution_form': 'ROLLING',
                  'first_valid_index': 'window - 1',
                  'formula': 'For the current value in the trailing window, rank = count(values < current) + (count(values '
                             '== current)+1)/2; ties use average rank including the current observation.',
                  'inputs': ['close'],
                  'outputs': {'value': {'dtype': 'float64_series', 'units': 'rank_1_to_window'}},
                  'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                  'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                       'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                       'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                       'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                       'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                  'threshold_class': 'NONRECURSIVE',
                  'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                           'substitute.'},
 'ROLLING_REGRESSION': {'decision': 'REPLACE_V2',
                        'execution_form': 'ROLLING',
                        'first_valid_index': 'window - 1',
                        'formula': 'Fit primary = intercept + slope*peer on the trailing window. Emit slope, intercept and '
                                   'current-bar residual; no return-regression substitution.',
                        'inputs': ['close', 'peer'],
                        'outputs': {'intercept': {'dtype': 'float64_series', 'units': 'input_units'},
                                    'residual': {'dtype': 'float64_series', 'units': 'input_units'},
                                    'slope': {'dtype': 'float64_series', 'units': 'primary_units_per_peer_unit'}},
                        'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                        'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                             'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                             'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                             'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                             'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                        'threshold_class': 'NONRECURSIVE',
                        'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a '
                                                 'finite substitute.'},
 'ROLLING_RETURN': {'decision': 'KEEP',
                    'execution_form': 'ROLLING',
                    'first_valid_index': 'window',
                    'formula': 'close[t]/close[t-window] - 1; decimal fraction, not percentage points. ROC remains an '
                               'explicitly labelled ROCP-compatible variant.',
                    'inputs': ['close'],
                    'outputs': {'value': {'dtype': 'float64_series', 'units': 'decimal_return'}},
                    'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
                    'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                         'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                         'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                         'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                         'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                         'sha256:ca513529cb17af56621698d58903cf245cbf84d2860c3eba2be4e2c81649d7d0'),
                    'threshold_class': 'NONRECURSIVE',
                    'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                             'substitute.'},
 'ROLLING_STDDEV': {'decision': 'REPLACE_V2',
                    'execution_form': 'ROLLING',
                    'first_valid_index': 'window - 1',
                    'formula': 'Square root of ROLLING_VARIANCE using the same window and ddof, on input values.',
                    'inputs': ['close'],
                    'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                    'parameters': {'ddof': {'default': 0, 'type': 'enum', 'values': [0, 1]},
                                   'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                    'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                         'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                         'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                         'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                         'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                         'sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe'),
                    'threshold_class': 'NONRECURSIVE',
                    'zero_undefined_policy': 'A constant finite window has standard deviation 0.'},
 'ROLLING_VARIANCE': {'decision': 'REPLACE_V2',
                      'execution_form': 'ROLLING',
                      'first_valid_index': 'window - 1',
                      'formula': 'Sum((x-mean(x))^2)/(window-ddof) on input values, not returns.',
                      'inputs': ['close'],
                      'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units_squared'}},
                      'parameters': {'ddof': {'default': 0, 'type': 'enum', 'values': [0, 1]},
                                     'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                      'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                           'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                           'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                           'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                           'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                           'sha256:bad33742f059fe2dfee9b2d26139b525dbedf7a6d702d8a1e7ccabc6c71eccfe'),
                      'threshold_class': 'NONRECURSIVE',
                      'zero_undefined_policy': 'A constant finite window has variance 0; missing values invalidate the full '
                                               'window.'},
 'ROLLING_VOLUME_PERCENTILE': {'decision': 'REPLACE_V2',
                               'execution_form': 'ROLLING',
                               'first_valid_index': 'window - 1',
                               'formula': 'For the current volume in the trailing window, rank = count(volumes < current) + '
                                          '(count(volumes == current)+1)/2; ties use average rank including the current '
                                          'observation. Return 100*rank/window.',
                               'inputs': ['volume'],
                               'outputs': {'value': {'dtype': 'float64_series', 'units': 'percentile_0_to_100'}},
                               'parameters': {'window': {'default': 14,
                                                         'maximum': 4096,
                                                         'minimum': 2,
                                                         'type': 'exact_integer'}},
                               'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                                    'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                                    'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                                    'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                                    'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                               'threshold_class': 'NONRECURSIVE',
                               'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never '
                                                        'a finite substitute.'},
 'R_SQUARED': {'decision': 'REPLACE_V2',
               'execution_form': 'ROLLING',
               'first_valid_index': 'window - 1',
               'formula': 'Squared Pearson correlation of primary and peer levels in the same trailing window; either '
                          'constant series is invalid.',
               'inputs': ['close', 'peer'],
               'outputs': {'value': {'dtype': 'float64_series', 'units': 'fraction_0_to_1'}},
               'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
               'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                    'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                    'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                    'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                    'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
               'threshold_class': 'NONRECURSIVE',
               'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                        'substitute.'},
 'SMA': {'decision': 'KEEP',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window - 1',
         'formula': 'Arithmetic mean of the last window input values, including the current completed bar.',
         'inputs': ['close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:7110c2fe33f4b8a1d109282ab4d9ece1cf3440ef0bd529c8f73f59a3d1ab53e8'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'TREND_PERSISTENCE': {'decision': 'REPLACE_V2',
                       'execution_form': 'ROLLING',
                       'first_valid_index': 'window',
                       'formula': 'abs(sum(sign(close[i]-close[i-1]), last window changes))/window. Equal prices contribute '
                                  'zero; missing changes invalidate the window.',
                       'inputs': ['close'],
                       'outputs': {'value': {'dtype': 'float64_series', 'units': 'fraction_0_to_1'}},
                       'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 1, 'type': 'exact_integer'}},
                       'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                            'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                            'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                            'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                            'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                       'threshold_class': 'NONRECURSIVE',
                       'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                                'substitute.'},
 'TRUE_RANGE': {'decision': 'REPLACE_V2',
                'execution_form': 'STATELESS',
                'first_valid_index': '1',
                'formula': 'max(high-low,abs(high-previous_close),abs(low-previous_close)); no value exists before a '
                           'previous close.',
                'inputs': ['high', 'low', 'close'],
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                'parameters': {},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:b8f31b1a93d9809da4588c567030a831c4df7c16d468f1af385e4ddefc3bc580'),
                'threshold_class': 'EXACT',
                'zero_undefined_policy': 'A finite unchanged bar has true range 0.'},
 'TYPICAL_PRICE': {'decision': 'KEEP',
                   'execution_form': 'STATELESS',
                   'first_valid_index': '0',
                   'formula': '(high + low + close) / 3.',
                   'inputs': ['high', 'low', 'close'],
                   'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                   'parameters': {},
                   'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                        'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                        'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                        'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                        'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                        'sha256:a1ae63259ac9c35718357afe36daa2e09a9216e991dae8a3259a4f9de85091cb'),
                   'threshold_class': 'EXACT',
                   'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                            'substitute.'},
 'VOLUME_ZSCORE': {'decision': 'REPLACE_V2',
                   'execution_form': 'ROLLING',
                   'first_valid_index': 'window - 1',
                   'formula': '(volume - mean(volume,window))/population_std(volume,window).',
                   'inputs': ['volume'],
                   'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
                   'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                   'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                        'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                        'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                        'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                        'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
                   'threshold_class': 'NONRECURSIVE',
                   'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                            'substitute.'},
 'VWMA': {'decision': 'REPLACE_V2',
          'execution_form': 'ROLLING',
          'first_valid_index': 'window - 1',
          'formula': 'sum(close*volume,window)/sum(volume,window).',
          'inputs': ['close', 'volume'],
          'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
          'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
          'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                               'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                               'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                               'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                               'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
          'threshold_class': 'NONRECURSIVE',
          'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'WEIGHTED_CLOSE': {'decision': 'KEEP',
                    'execution_form': 'STATELESS',
                    'first_valid_index': '0',
                    'formula': '(high + low + 2*close) / 4.',
                    'inputs': ['high', 'low', 'close'],
                    'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
                    'parameters': {},
                    'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                         'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                         'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                         'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                         'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                         'sha256:4ab4cecfa2ffad4a22eb1536a5e6ee78329a5ef0583d77759cfad6fd071ca44f'),
                    'threshold_class': 'EXACT',
                    'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                             'substitute.'},
 'WILLIAMS_R': {'decision': 'KEEP',
                'execution_form': 'ROLLING',
                'first_valid_index': 'window - 1',
                'formula': '-100*(rolling_high(high)-close)/(rolling_high(high)-rolling_low(low)).',
                'inputs': ['high', 'low', 'close'],
                'outputs': {'value': {'dtype': 'float64_series', 'units': 'oscillator_minus100_to0'}},
                'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
                'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                     'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                     'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                     'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                     'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                                     'sha256:dd8684edbf0e86df54dd95457ae00445887998f3e4481cc49fd2b1eb467f6571'),
                'threshold_class': 'NONRECURSIVE',
                'zero_undefined_policy': 'Pinned TA_WILLR returns 0 for a valid zero-range window.'},
 'WMA': {'decision': 'KEEP',
         'execution_form': 'ROLLING',
         'first_valid_index': 'window - 1',
         'formula': 'Sum((i+1)*x[i], i=0..window-1) / (window*(window+1)/2); oldest has weight 1.',
         'inputs': ['close'],
         'outputs': {'value': {'dtype': 'float64_series', 'units': 'input_units'}},
         'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
         'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                              'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                              'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                              'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                              'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3',
                              'sha256:01bcc74a5ac4ce27c2e058928cadcd04d3b7d0fd47662ac0d98da181fd238f90'),
         'threshold_class': 'NONRECURSIVE',
         'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite substitute.'},
 'ZSCORE': {'decision': 'REPLACE_V2',
            'execution_form': 'ROLLING',
            'first_valid_index': 'window - 1',
            'formula': '(close - mean(close,window))/population_std(close,window).',
            'inputs': ['close'],
            'outputs': {'value': {'dtype': 'float64_series', 'units': 'dimensionless'}},
            'parameters': {'window': {'default': 14, 'maximum': 4096, 'minimum': 2, 'type': 'exact_integer'}},
            'source_addresses': ('sha256:09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb',
                                 'sha256:54aef745882dc8c5e2394f29ebb963a2d164d8779c26595022fe96173c525482',
                                 'sha256:20be62fd2d0ab8f5af6009712c1b98bcb903cecb5bae97673645cdc244a45925',
                                 'sha256:c248e7cf9bb290d2a8aacb0bc7e000027ba461f77ccf97f65e526cf8baf86994',
                                 'sha256:5642ea3231ab5ee55b491c8b875b91ac5ea821e1b7247d84c06e3188a6039bd3'),
            'threshold_class': 'NONRECURSIVE',
            'zero_undefined_policy': 'Zero divisor or mathematically undefined result is invalid, never a finite '
                                     'substitute.'}})

NAMES = tuple(sorted(SPECS))


def component_key(name):
    if name not in SPECS:
        raise node_contracts.NodeContractRefusal("CORE_COMPONENT_UNAVAILABLE")
    return ("analytical." + name.lower(), 2)


def parameters_for(name, parameters=None):
    """Validate before defaults: no bool-as-int, ignored knobs or fallback source."""
    component_key(name)
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, abc.Mapping) or set(parameters) - set(SPECS[name]["parameters"]):
        raise node_contracts.NodeContractRefusal("CORE_PARAMETERS_UNKNOWN")
    result = {}
    for key, spec in SPECS[name]["parameters"].items():
        value = parameters.get(key, spec["default"])
        if spec["type"] in {"exact_integer", "enum"}:
            if type(value) is not int:
                raise node_contracts.NodeContractRefusal("CORE_PARAMETER_NOT_EXACT_INTEGER")
        elif type(value) not in {int, float} or not math.isfinite(value):
            raise node_contracts.NodeContractRefusal("CORE_PARAMETER_NOT_FINITE")
        if spec["type"] == "enum":
            if value not in spec["values"]:
                raise node_contracts.NodeContractRefusal("CORE_PARAMETER_OUT_OF_DOMAIN")
        elif not spec["minimum"] <= value <= spec["maximum"]:
            raise node_contracts.NodeContractRefusal("CORE_PARAMETER_OUT_OF_DOMAIN")
        # Canonical parameter bytes belong to the resolver. Numerically equal
        # integers/floats can have different receipt identities; preserve them.
        result[key] = value
    return node_contracts._freeze(result)


def first_valid_index(name, parameters=None):
    values = parameters_for(name, parameters)
    rule = SPECS[name]["first_valid_index"]
    if rule == "window":
        return values["window"]
    if rule == "window - 1":
        return values["window"] - 1
    return int(rule)


def fields_by_port(name):
    fields = SPECS[name]["inputs"]
    result = {"frame": tuple(sorted(field.upper() for field in fields if field != "peer"))}
    if "peer" in fields:
        result["peer"] = ("CLOSE",)
    return node_contracts._freeze(result)


def _binding_rule(name):
    # Only primitive immutable closures and the already audited pure builder.
    # Keep validation local: the canonical resolver normally fills defaults, but
    # calling the rule directly cannot bypass bounds or add unknown parameters.
    specs = tuple((key, spec["type"], spec["default"], spec.get("minimum"),
                   spec.get("maximum"), tuple(spec.get("values", ())))
                  for key, spec in sorted(SPECS[name]["parameters"].items()))
    fields = tuple(fields_by_port(name).items())
    outputs = tuple(sorted(SPECS[name]["outputs"]))
    history_rule = SPECS[name]["first_valid_index"]
    builder = contracts.binding_result

    def bind(parameters, inputs, _spec=(specs, fields, outputs, history_rule, builder)):
        specs, fields, outputs, history_rule, builder = _spec
        if set(parameters) != {row[0] for row in specs}:
            raise ValueError("exact canonical parameters required")
        for key, kind, default, minimum, maximum, values in specs:
            value = parameters[key]
            if kind in ("exact_integer", "enum"):
                if type(value) is not int:
                    raise ValueError("exact integer required")
            elif type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("finite number required")
            if kind == "enum":
                if value not in values:
                    raise ValueError("enum domain")
            elif not minimum <= value <= maximum:
                raise ValueError("parameter bounds")
        history = (parameters["window"] if history_rule == "window" else
                   parameters["window"] - 1 if history_rule == "window - 1" else int(history_rule))
        return builder(inputs, fields_by_port=dict(fields), warmup_history=history,
                       output_warmup={output: history for output in outputs})

    return bind


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
            "units": "percent" if field == "q" else "bars" if field == "window" else "degrees_of_freedom",
            "serialization": "canonical-json",
        }
    return node_contracts._freeze({"component_id": key[0], "component_version": 2,
                    "domain_family": "indicator", "structural_role": "transform",
                    "ports": [_port(port, "input", "analytical.market_frame") for port in fields_by_port(name)] +
                             [_port(port, "output", _type_id(name, port)) for port in sorted(SPECS[name]["outputs"])],
                    "parameters": parameters})


def source_contract(name):
    key = component_key(name)
    rule = {"rule_id": key[0] + ".binding", "rule_version": 1}
    fields = fields_by_port(name)
    # The envelope covers maximum window + lag, Python objects and encoding
    # workspace. The wave's measured resource receipt verifies these ceilings.
    slots = 4097 if "window" in SPECS[name]["parameters"] else first_valid_index(name) + 1
    field_count = sum(map(len, fields.values()))
    profile = {"compute_microseconds_per_event": 500000 if name in {"ALPHA", "BETA"} else 200000,
               "memory_bytes_upper_bound": 1048576 + slots * field_count * 512,
               "history_bytes_upper_bound": 16384 + slots * field_count * 128,
               "state_bytes_upper_bound": 16384 + slots * field_count * 128,
               "storage_bytes_per_day_upper_bound": 0,
               "subscription_count_upper_bound": len(fields), "fanout_upper_bound": 1}
    return node_contracts._freeze({
        "schema": "first-party-node-contract/2", "stable_node_id": key[0], "semantic_version": 2,
        "visible_family": "TYPE_2", "input_types": {port: "analytical.market_frame/series" for port in fields},
        "output_types": {port: _type_id(name, port) + "/series" for port in sorted(SPECS[name]["outputs"])},
        "required_market_fields": sorted(field.lower() if port == "frame" else port + "." + field.lower()
                                         for port, columns in fields.items() for field in columns),
        "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
        "warmup_history": rule, "execution_form": SPECS[name]["execution_form"],
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
                              "parameter_names": sorted(SPECS[name]["parameters"]), "input_ports": sorted(fields)},
    })


def _check_bound(name, parameters, bound):
    if not isinstance(bound, contracts.ResolvedNodeContract):
        raise node_contracts.NodeContractRefusal("CORE_VERIFIED_BINDING_REQUIRED")
    doc = bound.document
    replayed = contracts.materialize_node_contract(source_contract(name), _binding_registration(name),
                                                  parameters, doc["input_binding"])
    if replayed.bound_contract_address != bound.bound_contract_address:
        raise node_contracts.NodeContractRefusal("CORE_BINDING_REPLAY_MISMATCH")
    key = component_key(name)
    if (dict(doc["component"]) != {"component_id": key[0], "component_version": 2}
            or dict(doc["parameters"]) != dict(parameters)
            or doc["source_contract_address"] != hashing.content_address(node_contracts._plain(source_contract(name)))
            or doc["resolved_contract"]["warmup_history"] != first_valid_index(name, parameters)
            or dict(doc["resolved_contract"]["output_warmup"]) !=
            {port: first_valid_index(name, parameters) for port in SPECS[name]["outputs"]}):
        raise node_contracts.NodeContractRefusal("CORE_BINDING_MISMATCH")
    _check_bound_inputs(name, doc["input_binding"]["ports"])


def _check_bound_inputs(name, ports):
    if set(ports) != set(fields_by_port(name)):
        raise node_contracts.NodeContractRefusal("CORE_ROLE_MISMATCH")
    primary = ports["frame"]["binding"]
    for port, fields in fields_by_port(name).items():
        fact = ports[port]["binding"]
        if (port != "frame" and fact["instrument"]["role"] != port
                or not set(fields) <= set(fact["fields"])
                or fact["timeframe"] != primary["timeframe"]
                or dict(fact["alignment"]) != {"kind": "EXACT", "maximum_skew_seconds": 0}):
            raise node_contracts.NodeContractRefusal("CORE_ALIGNED_FIELDS_REQUIRED")


def _mean(values):
    return math.fsum(values) / len(values)


def _level_moments(x, y, *, include_y_variance=False):
    """Exact binary64 level moments; n-scaled sums avoid rounded means."""
    x = [fractions.Fraction(v) for v in x]
    y = [fractions.Fraction(v) for v in y]
    count = len(x)
    sx, sy = sum(x), sum(y)
    xx = count * sum(v * v for v in x) - sx * sx
    xy = count * sum(a * b for a, b in zip(x, y)) - sx * sy
    yy = count * sum(v * v for v in y) - sy * sy if include_y_variance else None
    return count, sx, sy, xx, yy, xy, x[-1], y[-1]


def _level_correlation(peer, close, *, squared):
    _, _, _, xx, yy, xy, _, _ = _level_moments(peer, close, include_y_variance=True)
    ratio = xy * xy / (xx * yy)
    if squared:
        return float(ratio)
    with _precision_context():
        root = (decimal.Decimal(ratio.numerator) / decimal.Decimal(ratio.denominator)).sqrt()
        return float(-root if xy < 0 else root)


def _precision_context():
    # Never inherit a caller's precision, rounding, exponent limits or traps.
    # This is temporary arithmetic workspace; persisted state stays float64.
    return decimal.localcontext(_decimal.Context(
        prec=120, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
        capitals=1, clamp=0, flags=[],
        traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow],
    ))


def _simple_return(previous, current):
    change = current - previous
    # Opposite-sign finite endpoints can overflow their difference even when
    # the return is representable. Both branches implement the same formula.
    return change / previous if math.isfinite(change) else current / previous - 1


def _log_return(previous, current):
    if previous <= 0 or current <= 0:
        raise ValueError("log endpoints must be positive")
    ratio = current / previous
    if 0.5 <= ratio <= 2:
        return math.log1p((current - previous) / previous)
    if 0 < ratio < math.inf:
        return math.log(ratio)
    # A finite logarithm can exist when the intermediate ratio cannot fit.
    return math.log(current) - math.log(previous)


def _precise_regression(x, y):
    """Centered regression of Decimal inputs within the caller's fixed context."""
    # Center on an observed value before taking a mean. A constant repeating
    # ratio then has exactly zero variance, even after Decimal division.
    shifted_x, shifted_y = [v - x[0] for v in x], [v - y[0] for v in y]
    mx, my = sum(shifted_x) / len(x), sum(shifted_y) / len(y)
    dx, dy = [v - mx for v in shifted_x], [v - my for v in shifted_y]
    slope = sum(a * b for a, b in zip(dx, dy)) / sum(a * a for a in dx)
    return x[0] + mx, y[0] + my, slope


def _return_regression(peer, close, *, alpha):
    with _precision_context():
        x = [decimal.Decimal(b) / decimal.Decimal(a) for a, b in zip(peer, peer[1:])]
        y = [decimal.Decimal(b) / decimal.Decimal(a) for a, b in zip(close, close[1:])]
        # Subtracting one does not change covariance or variance. Retaining
        # ratios avoids erasing distinctions between returns close to -1.
        mx, my, slope = _precise_regression(x, y)
        return float((slope - 1) + (my - slope * mx) if alpha else slope)


def _level_regression(peer, close):
    # Float levels are exact binary rationals: aggregate denominators remain
    # powers of two. Exact moments avoid a spurious huge residual when a
    # perfectly fitted line has very large finite coordinates.
    count, sx, sy, xx, _, xy, last_x, last_y = _level_moments(peer, close)
    slope = xy / xx
    intercept = (sy - slope * sx) / count
    return {"intercept": intercept, "residual": last_y - intercept - slope * last_x, "slope": slope}


def _cci(high, low, close):
    with _precision_context():
        # The factor of three in typical price cancels from numerator and MAD.
        h0, l0, c0 = decimal.Decimal(high[0]), decimal.Decimal(low[0]), decimal.Decimal(close[0])
        typical = [(decimal.Decimal(h) - h0) + (decimal.Decimal(l) - l0) + (decimal.Decimal(c) - c0)
                   for h, l, c in zip(high, low, close)]
        mean = sum(typical) / len(typical)
        deviation = sum(abs(v - mean) for v in typical) / len(typical)
        return 0.0 if deviation == 0 else float((typical[-1] - mean) / (decimal.Decimal('0.015') * deviation))


def _zscore(values):
    with _precision_context():
        origin = decimal.Decimal(values[0])
        exact = [decimal.Decimal(v) - origin for v in values]
        mean = sum(exact) / len(exact)
        variance = sum((v - mean) ** 2 for v in exact) / len(exact)
        return float((exact[-1] - mean) / variance.sqrt())


def _number(name, rows, parameters):
    """Evaluate one complete finite contiguous window; no missing-data deletion."""
    fields = SPECS[name]["inputs"]
    columns = {key: [row[i] for row in rows] for i, key in enumerate(fields)}
    close = columns.get("close")
    volume = columns.get("volume")
    high, low, peer = columns.get("high"), columns.get("low"), columns.get("peer")
    window = parameters.get("window", 1)
    if name in {"HL2", "MIDPOINT"}:
        result = (high[-1] + low[-1]) / 2
    elif name in {"HLC3", "TYPICAL_PRICE"}:
        result = (high[-1] + low[-1] + close[-1]) / 3
    elif name == "OHLC4":
        result = (columns["open"][-1] + high[-1] + low[-1] + close[-1]) / 4
    elif name == "WEIGHTED_CLOSE":
        result = (high[-1] + low[-1] + 2 * close[-1]) / 4
    elif name == "RATIO":
        result = close[-1] / peer[-1]
    elif name in {"MOMENTUM", "POINT_CHANGE"}:
        result = close[-1] - close[0]
    elif name in {"ROC", "PERCENT_RETURN", "ROLLING_RETURN"}:
        result = _simple_return(close[0], close[-1])
    elif name == "LOG_RETURN":
        result = _log_return(close[0], close[-1])
    elif name in {"GAP", "GAP_UP", "GAP_DOWN"}:
        opening = columns["open"][-1]
        result = opening - close[-2] if name == "GAP" else opening > close[-2] if name == "GAP_UP" else opening < close[-2]
    elif name in {"CROSS_ABOVE", "CROSS_BELOW"}:
        result = (close[-1] > peer[-1] and close[-2] <= peer[-2]) if name == "CROSS_ABOVE" else (close[-1] < peer[-1] and close[-2] >= peer[-2])
    elif name in {"INSIDE_BAR", "OUTSIDE_BAR"}:
        result = (high[-1] < high[-2] and low[-1] > low[-2]) if name == "INSIDE_BAR" else (high[-1] > high[-2] and low[-1] < low[-2])
    elif name == "TRUE_RANGE":
        result = max(high[-1] - low[-1], abs(high[-1] - close[-2]), abs(low[-1] - close[-2]))
    elif name in {"FALLING", "RISING", "TREND_PERSISTENCE"}:
        changes = [b - a for a, b in zip(close, close[1:])]
        result = (all(v < 0 for v in changes) if name == "FALLING" else
                  all(v > 0 for v in changes) if name == "RISING" else
                  abs(sum((v > 0) - (v < 0) for v in changes)) / window)
    elif name in {"BETA", "ALPHA"}:
        result = _return_regression(peer, close, alpha=name == "ALPHA")
    elif name in {"ROLLING_REGRESSION", "RESIDUAL"}:
        regression = _level_regression(peer, close)
        if name == "ROLLING_REGRESSION":
            return {port: float(value) for port, value in regression.items()}
        result = float(regression["residual"])
    elif name in {"COVARIANCE", "CORRELATION", "R_SQUARED", "ROLLING_HEDGE_RATIO", "BETA_ADJUSTED_SPREAD"}:
        if name == "COVARIANCE":
            count, _, _, _, _, xy, _, _ = _level_moments(peer, close)
            result = float(xy / (count * (count - parameters["ddof"])))
        elif name in {"CORRELATION", "R_SQUARED"}:
            result = _level_correlation(peer, close, squared=name == "R_SQUARED")
        else:
            _, _, _, xx, _, xy, last_x, last_y = _level_moments(peer, close)
            slope = xy / xx
            result = float(slope if name == "ROLLING_HEDGE_RATIO" else last_y - slope * last_x)
    elif name in {"LINEAR_REGRESSION_INTERCEPT", "LINEAR_REGRESSION_SLOPE"}:
        count, sx, sy, xx, _, xy, _, _ = _level_moments(tuple(range(window)), close)
        slope = xy / xx
        result = float(slope if name == "LINEAR_REGRESSION_SLOPE" else (sy - slope * sx) / count)
    elif name == "CCI":
        result = _cci(high, low, close)
    elif name == "MFI":
        typical = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
        positive = math.fsum(t * v for a, t, v in zip(typical, typical[1:], volume[1:]) if t > a)
        negative = math.fsum(t * v for a, t, v in zip(typical, typical[1:], volume[1:]) if t < a)
        total = positive + negative
        result = 0.0 if total < 1.0 else 100 * positive / total
    elif name == "CHAIKIN_MONEY_FLOW":
        flow = [0.0 if h == l else (2 * c - h - l) / (h - l) * v for h, l, c, v in zip(high, low, close, volume)]
        result = math.fsum(flow) / math.fsum(volume)
    elif name == "VWMA":
        result = math.fsum(c * v for c, v in zip(close, volume)) / math.fsum(volume)
    elif name == "WILLIAMS_R":
        highest, lowest = max(high), min(low)
        result = 0.0 if highest == lowest else -100 * (highest - close[-1]) / (highest - lowest)
    else:
        values = volume if name in {"RELATIVE_VOLUME", "VOLUME_ZSCORE", "ROLLING_VOLUME_PERCENTILE"} else close
        if name in {"ROLLING_HIGH", "ROLLING_MAX"}:
            result = max(values)
        elif name in {"ROLLING_LOW", "ROLLING_MIN"}:
            result = min(values)
        elif name in {"SMA", "ROLLING_MEAN"}:
            result = _mean(values)
        elif name == "WMA":
            result = math.fsum((i + 1) * v for i, v in enumerate(values)) / (window * (window + 1) / 2)
        elif name in {"ROLLING_MEDIAN", "PERCENTILE"}:
            ordered = sorted(values)
            h = (window - 1) * parameters.get("q", 50) / 100
            lo, hi = math.floor(h), math.ceil(h)
            result = ordered[lo] * (1 - (h - lo)) + ordered[hi] * (h - lo)
        elif name in {"ROLLING_RANK", "PERCENTILE_RANK", "ROLLING_VOLUME_PERCENTILE"}:
            rank = sum(v < values[-1] for v in values) + (sum(v == values[-1] for v in values) + 1) / 2
            result = rank if name == "ROLLING_RANK" else 100 * rank / window
        elif name in {"ZSCORE", "VOLUME_ZSCORE"}:
            result = _zscore(values)
        else:
            mean = _mean(values)
            if name == "RELATIVE_VOLUME":
                result = values[-1] / mean
            elif name == "MAD":
                result = _mean([abs(v - mean) for v in values])
            else:
                variance = math.fsum((v - mean) ** 2 for v in values) / (window - parameters.get("ddof", 0))
                if name == "ROLLING_VARIANCE":
                    result = variance
                elif name == "ROLLING_STDDEV":
                    result = math.sqrt(variance)
                else:
                    raise node_contracts.NodeContractRefusal("CORE_FORMULA_NOT_IMPLEMENTED")
    return {"value": result}


class CoreMathState:
    """Bounded rolling window for one component and one verified data context.

    No provider calls, calendar inference or index compression. Missing bars clear
    the contiguous window. Verified adjacent sessions carry it. The existing data
    producer must supply DATA_GAP for absent bars (as opposed to a session closure).
    """

    def __init__(self, name, parameters, bound_contract):
        self.name = name
        self.parameters = parameters_for(name, parameters)
        _check_bound(name, self.parameters, bound_contract)
        self.bound_contract = bound_contract
        self.capacity = first_valid_index(name, self.parameters) + 1
        self._rows = []
        self._last_time = None

    def step(self, inputs, *, event_time, reset_reasons=(), event_kind="completed_bar"):
        if event_kind != "completed_bar":
            raise node_contracts.NodeContractRefusal("CORE_COMPLETED_BAR_REQUIRED")
        timestamp = _timestamp(event_time)
        if self._last_time is not None and timestamp <= self._last_time:
            raise node_contracts.NodeContractRefusal("CORE_EVENT_ORDER")
        reasons = common.contract_reset_reasons(self.bound_contract, reset_reasons)
        expected = fields_by_port(self.name)
        if not isinstance(inputs, abc.Mapping) or set(inputs) != set(expected):
            raise node_contracts.NodeContractRefusal("CORE_INPUT_PORTS")
        cells = {}
        for port, fields in expected.items():
            if not isinstance(inputs[port], abc.Mapping):
                raise node_contracts.NodeContractRefusal("CORE_NAMED_FIELDS_REQUIRED")
            for field in fields:
                cells["peer" if port == "peer" else field.lower()] = common.required_numeric_scalar(inputs[port], field.lower())
        bad = validity.propagate(cells.values())
        if bad is None:
            # Invalid market bars are not a licence to manufacture oscillator
            # extrema or negative traded volume. Zero range/volume remain valid.
            raw = {key: cell.value for key, cell in cells.items()}
            if ("volume" in raw and raw["volume"] < 0 or
                    "high" in raw and "low" in raw and (raw["high"] < raw["low"] or
                    "close" in raw and not raw["low"] <= raw["close"] <= raw["high"])):
                bad = validity.invalid(validity.ValidityState.INVALID)
        self._last_time = timestamp
        if reasons or bad is not None:
            self._rows.clear()
        if bad is not None:
            return {port: bad for port in sorted(SPECS[self.name]["outputs"])}
        self._rows.append(tuple(cells[key].value for key in SPECS[self.name]["inputs"]))
        if len(self._rows) > self.capacity:
            del self._rows[0]
        if len(self._rows) < self.capacity:
            return {port: validity.invalid(validity.ValidityState.INSUFFICIENT_HISTORY) for port in sorted(SPECS[self.name]["outputs"])}
        try:
            result = _number(self.name, self._rows, self.parameters)
            if any(not math.isfinite(value) for value in result.values()):
                raise ValueError("nonfinite result")
            return {port: validity.valid(value) for port, value in result.items()}
        except (ArithmeticError, ValueError):
            return {port: validity.invalid(validity.ValidityState.MATHEMATICALLY_UNDEFINED) for port in sorted(SPECS[self.name]["outputs"])}

    def snapshot(self):
        # A payload for the existing bound-state snapshot transport at integration,
        # not an alternate persisted authority receipt. Identity is checked again
        # against the caller's compiler-verified bound contract on restore.
        body = {"schema": "analytical-core-window/2", "component": list(component_key(self.name)),
                "bound_contract_address": self.bound_contract.bound_contract_address,
                "parameters": node_contracts._plain(self.parameters), "last_time": self._last_time.isoformat() if self._last_time is not None else None,
                "rows": [list(row) for row in self._rows]}
        return {**body, "payload_address": hashing.content_address(body)}

    @classmethod
    def restore(cls, name, parameters, bound_contract, document):
        state = cls(name, parameters, bound_contract)
        fields = {"schema", "component", "bound_contract_address", "parameters", "last_time", "rows", "payload_address"}
        if not isinstance(document, abc.Mapping) or set(document) != fields:
            raise node_contracts.NodeContractRefusal("CORE_STATE_CLOSED_SCHEMA")
        body = {key: value for key, value in document.items() if key != "payload_address"}
        if (document["schema"] != "analytical-core-window/2" or
                document["component"] != list(component_key(name)) or
                document["bound_contract_address"] != bound_contract.bound_contract_address or
                document["parameters"] != dict(state.parameters)):
            raise node_contracts.NodeContractRefusal("CORE_STATE_IDENTITY")
        rows = document["rows"]
        if not isinstance(rows, (tuple, list)) or len(rows) > state.capacity:
            raise node_contracts.NodeContractRefusal("CORE_STATE_BOUND")
        width = len(SPECS[name]["inputs"])
        if any(not isinstance(row, (tuple, list)) or len(row) != width or
               any(type(value) not in {int, float} or not math.isfinite(value) for value in row) for row in rows):
            raise node_contracts.NodeContractRefusal("CORE_STATE_ROWS")
        if rows and document["last_time"] is None:
            raise node_contracts.NodeContractRefusal("CORE_STATE_CLOCK")
        try:
            if document["payload_address"] != hashing.content_address(body):
                raise node_contracts.NodeContractRefusal("CORE_STATE_DIGEST")
        except (TypeError, ValueError) as exc:
            raise node_contracts.NodeContractRefusal("CORE_STATE_DIGEST") from exc
        state._last_time = _timestamp(document["last_time"]) if document["last_time"] is not None else None
        state._rows = [tuple(row) for row in rows]
        return state


def _timestamp(value):
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError("timezone required")
        return timestamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError) as exc:
        raise node_contracts.NodeContractRefusal("CORE_CANONICAL_TIME_REQUIRED") from exc


def evaluate(name, parameters, inputs, *, bound_contract, resets=None):
    """Complete named arrays; supplied indexes denote completed-bar availability."""
    state = CoreMathState(name, parameters, bound_contract)
    fields = fields_by_port(name)
    if not isinstance(inputs, abc.Mapping) or set(inputs) != set(fields):
        raise node_contracts.NodeContractRefusal("CORE_INPUT_PORTS")
    index = None
    columns = {}
    for port, required in fields.items():
        frame = inputs[port]
        if not isinstance(frame, abc.Mapping):
            raise node_contracts.NodeContractRefusal("CORE_NAMED_FIELDS_REQUIRED")
        for field in required:
            key = field.lower()
            if key not in frame or not isinstance(frame[key], pd.Series):
                raise node_contracts.NodeContractRefusal("CORE_INDEXED_FIELD_REQUIRED")
            series = frame[key]
            if not isinstance(series.index, pd.DatetimeIndex) or series.index.tz is None or series.index.hasnans or not series.index.is_unique or not series.index.is_monotonic_increasing:
                raise node_contracts.NodeContractRefusal("CORE_CANONICAL_INDEX_REQUIRED")
            if index is None:
                index = series.index
            if not series.index.equals(index):
                raise node_contracts.NodeContractRefusal("CORE_EXACT_ALIGNMENT_REQUIRED")
            columns[(port, key)] = series.tolist()
    if resets is None:
        resets = ((),) * len(index)
    if not isinstance(resets, (tuple, list)) or len(resets) != len(index):
        raise node_contracts.NodeContractRefusal("CORE_RESET_ARRAY_REQUIRED")
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
            raise node_contracts.NodeContractRefusal("CORE_VERIFIED_EVALUATION_CONTEXT_REQUIRED")
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
    dependency_boundary=registry.DependencyBoundary("defining_module", (abc, pd, math, decimal, _decimal, fractions, hashing, node_contracts, registry, validity, common, contracts)),
) for name in NAMES})
