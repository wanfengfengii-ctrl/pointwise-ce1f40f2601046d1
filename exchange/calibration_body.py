from dataclasses import dataclass
from fractions import Fraction

from bench.fractional import FractionalMap, RationalInput, parse_map, parse_rational
from exchange.envelope import canonical_json, read_json


TerminalRelation = FractionalMap


@dataclass(frozen=True)
class SupportInterval:
    lower: Fraction | None
    upper: Fraction | None
    lower_closed: bool = False
    upper_closed: bool = False

    def __post_init__(self) -> None:
        if type(self.lower_closed) is not bool or type(self.upper_closed) is not bool:
            raise ValueError('support endpoint flags must be booleans')
        for name, closed in (('lower', self.lower_closed), ('upper', self.upper_closed)):
            value = getattr(self, name)
            if value is None:
                if closed:
                    raise ValueError('an unbounded endpoint must be open')
            else:
                object.__setattr__(self, name, parse_rational(value))
        if self.lower is not None and self.upper is not None:
            if self.lower > self.upper or (self.lower == self.upper and not (
                self.lower_closed and self.upper_closed
            )):
                raise ValueError('support interval is empty or reversed')

    def contains(self, value: Fraction) -> bool:
        left = self.lower is None or value > self.lower or (self.lower_closed and value == self.lower)
        right = self.upper is None or value < self.upper or (self.upper_closed and value == self.upper)
        return left and right


@dataclass(frozen=True)
class CalibrationBody:
    terminal: TerminalRelation | None
    support: tuple[SupportInterval, ...]

    def __post_init__(self) -> None:
        if bool(self.support) != (self.terminal is not None):
            raise ValueError('a terminal relation is required exactly for nonempty support')
        for previous, interval in zip(self.support, self.support[1:]):
            if previous.upper is None or interval.lower is None or previous.upper > interval.lower:
                raise ValueError('support components overlap or are out of order')
            if previous.upper == interval.lower and (previous.upper_closed or interval.lower_closed):
                raise ValueError('touching support components must be merged')
        if self.terminal is not None:
            pole = self.terminal.pole
            if pole is not None and any(interval.contains(pole) for interval in self.support):
                raise ValueError('support contains a terminal pole')

    def supports(self, setting: RationalInput) -> bool:
        value = parse_rational(setting)
        return any(interval.contains(value) for interval in self.support)


def encode_body(body: CalibrationBody) -> str:
    relation = None if body.terminal is None else [str(value) for value in body.terminal.coefficients]
    support = [
        [None if interval.lower is None else str(interval.lower),
         None if interval.upper is None else str(interval.upper),
         interval.lower_closed, interval.upper_closed]
        for interval in body.support
    ]
    return canonical_json({'terminal': relation, 'support': support})


def decode_body(encoded: str) -> CalibrationBody:
    raw = read_json(encoded)
    if not isinstance(raw, dict) or set(raw) != {'terminal', 'support'}:
        raise ValueError('invalid calibration body fields')
    terminal = raw['terminal']
    if terminal is not None:
        if not isinstance(terminal, list) or any(type(value) is not str for value in terminal):
            raise ValueError('terminal coefficients must be rational strings')
        terminal = parse_map(terminal)
    if not isinstance(raw['support'], list):
        raise ValueError('support must be a list')
    intervals = []
    for part in raw['support']:
        if not isinstance(part, list) or len(part) != 4:
            raise ValueError('each support component needs two endpoints and two flags')
        lower, upper, lower_closed, upper_closed = part
        if any(value is not None and type(value) is not str for value in (lower, upper)):
            raise ValueError('finite support endpoints must be rational strings')
        intervals.append(SupportInterval(lower, upper, lower_closed, upper_closed))
    return CalibrationBody(terminal, tuple(intervals))
