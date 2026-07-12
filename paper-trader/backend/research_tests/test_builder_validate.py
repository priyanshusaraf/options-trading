"""The static security boundary: an AST allow-list over emitted strategy source.

A generated strategy is real Python that will be exec'd, so validation is fail-closed —
it accepts ONLY the exact shape the emitter produces (a single `compute` function whose
body is block-call assignments combined with &/|/~ and a dict return) and rejects
everything else. These tests are adversarial: each attempted escape (import, dunder,
attribute, subscript, eval/exec/open, lambda, comprehension, an un-whitelisted call,
extra functions) MUST raise. If any of these regress, arbitrary code could run."""
import pytest

from research.strategy.builder.emit import emit_source
from research.strategy.builder.grammar import Composition
from research.strategy.builder.validate import UnsafeStrategyError, validate_source

_GOOD = emit_source(Composition.from_dict({
    "key": "g1",
    "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)"]},
    "longExit":   {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit":  {"any": ["zscore_gt(50,0.0)"]},
}))


def test_emitted_source_validates():
    validate_source(_GOOD)               # must not raise


def test_invert_and_negative_literal_allowed():
    src = ("def compute(df, **params):\n"
           "    longEntry = ~zscore_lt(df, 50, -1.0)\n"
           "    shortEntry = zscore_gt(df, 50, 1.0)\n"
           "    longExit = zscore_lt(df, 50, 0.0)\n"
           "    shortExit = zscore_gt(df, 50, 0.0)\n"
           "    return {'longEntry': longEntry, 'shortEntry': shortEntry,\n"
           "            'longExit': longExit, 'shortExit': shortExit}\n")
    validate_source(src)


@pytest.mark.parametrize("src", [
    # import in any form
    "import os\ndef compute(df, **params):\n    return {}\n",
    "def compute(df, **params):\n    import os\n    return {}\n",
    "from os import system\ndef compute(df, **params):\n    return {}\n",
    # dynamic execution / IO builtins
    "def compute(df, **params):\n    x = eval('1')\n    return {}\n",
    "def compute(df, **params):\n    x = exec('pass')\n    return {}\n",
    "def compute(df, **params):\n    x = open('/etc/passwd')\n    return {}\n",
    "def compute(df, **params):\n    x = __import__('os')\n    return {}\n",
    # attribute access (data exfiltration / breakout surface)
    "def compute(df, **params):\n    x = df.to_csv('/tmp/x')\n    return {}\n",
    "def compute(df, **params):\n    x = df.__class__\n    return {}\n",
    "def compute(df, **params):\n    x = ().__class__.__bases__\n    return {}\n",
    # subscript escape / writing back into df
    "def compute(df, **params):\n    df['x'] = 1\n    return {}\n",
    "def compute(df, **params):\n    x = df['close']\n    return {}\n",
    # lambda / comprehension / control flow
    "def compute(df, **params):\n    f = lambda: 1\n    return {}\n",
    "def compute(df, **params):\n    xs = [i for i in range(3)]\n    return {}\n",
    "def compute(df, **params):\n    for i in range(3):\n        pass\n    return {}\n",
    "def compute(df, **params):\n    while True:\n        pass\n    return {}\n",
    "def compute(df, **params):\n    if True:\n        pass\n    return {}\n",
    # calling something that is not a whitelisted block
    "def compute(df, **params):\n    x = print(df)\n    return {}\n",
    "def compute(df, **params):\n    x = os_system(1)\n    return {}\n",
    # structural: extra function, wrong name, nested def, module-level code
    "def helper():\n    return 1\ndef compute(df, **params):\n    return {}\n",
    "def not_compute(df, **params):\n    return {}\n",
    "def compute(df, **params):\n    def inner():\n        return 1\n    return {}\n",
    "y = 1\ndef compute(df, **params):\n    return {}\n",
    # return shape: not a dict, wrong keys
    "def compute(df, **params):\n    return df\n",
    "def compute(df, **params):\n    longEntry = zscore_gt(df, 50, 1.0)\n"
    "    return {'evil': longEntry}\n",
])
def test_rejects_unsafe_source(src):
    with pytest.raises(UnsafeStrategyError):
        validate_source(src)


def test_rejects_call_with_keyword_args():
    src = ("def compute(df, **params):\n"
           "    longEntry = zscore_gt(df, length=50, thr=1.0)\n"
           "    return {'longEntry': longEntry}\n")
    with pytest.raises(UnsafeStrategyError):
        validate_source(src)
