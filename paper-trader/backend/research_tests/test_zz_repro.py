from research_tests import test_ir_search as t
from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.ir_components import BAR_INPUTS, groups
from research.strategy.builder.propose import Vocabulary


def mine_voc():
    return Vocabulary(blocks=tuple(sorted(BLOCKS)), bar_inputs=BAR_INPUTS,
                      defaults={n: dict(zip([p for p, _ in s.params], s.sample_args)) for n, s in BLOCKS.items()},
                      families=groups())


def test_repr():
    a, b = t.vocabulary.__wrapped__(), mine_voc()
    print("EQ", a == b)
    ra, rb = repr(a), repr(b)
    print("REPR EQ", ra == rb)
    if ra != rb:
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x != y:
                print(i, ra[max(0,i-120):i+120]); print(i, rb[max(0,i-120):i+120]); break
