from dataclasses import dataclass
from fractions import Fraction

from bench.fractional import RationalInput, parse_rational


@dataclass(frozen=True)
class InputRange:
    lower: Fraction | None = None
    upper: Fraction | None = None

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            return
        if self.lower is None or self.upper is None:
            raise ValueError('a finite range requires both closed endpoints')
        lower = parse_rational(self.lower)
        upper = parse_rational(self.upper)
        if lower > upper:
            raise ValueError('reversed input range')
        object.__setattr__(self, 'lower', lower)
        object.__setattr__(self, 'upper', upper)

    def contains(self, value: RationalInput) -> bool:
        setting = parse_rational(value)
        return self.lower is None or self.lower <= setting <= self.upper


def parse_input_range(raw: object) -> InputRange:
    if raw is None:
        return InputRange()
    if not isinstance(raw, (list, tuple)) or len(raw) != 2 or None in raw:
        raise ValueError('input range requires a pair of finite endpoints or null')
    return InputRange(*raw)
