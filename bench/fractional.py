from dataclasses import dataclass
from fractions import Fraction
import re


RationalInput = Fraction | int | str
_RATIONAL = re.compile(r'[+-]?[0-9]+(?:/[0-9]+)?')


def parse_rational(value: object) -> Fraction:
    if isinstance(value, Fraction) or type(value) is int:
        return Fraction(value)
    if isinstance(value, str) and _RATIONAL.fullmatch(value):
        try:
            return Fraction(value)
        except ZeroDivisionError as error:
            raise ValueError('a rational denominator must be positive') from error
    raise ValueError(f'expected an exact rational, got {value!r}')


@dataclass(frozen=True)
class FractionalMap:
    a: Fraction
    b: Fraction
    c: Fraction
    d: Fraction

    def __post_init__(self) -> None:
        a, b, c, d = (parse_rational(value) for value in self.coefficients)
        scale = d or c
        if not scale:
            raise ValueError('identically zero denominator')
        for name, value in zip(('a', 'b', 'c', 'd'), (a, b, c, d)):
            object.__setattr__(self, name, value / scale)

    @property
    def coefficients(self) -> tuple[Fraction, Fraction, Fraction, Fraction]:
        return self.a, self.b, self.c, self.d

    @property
    def pole(self) -> Fraction | None:
        return -self.d / self.c if self.c else None

    def value_at(self, setting: RationalInput) -> Fraction:
        x = parse_rational(setting)
        denominator = self.c * x + self.d
        if not denominator:
            raise ZeroDivisionError('setting is a pole of the conversion')
        return (self.a * x + self.b) / denominator


def parse_map(raw: object) -> FractionalMap:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError('fractional map requires four coefficients')
    return FractionalMap(*raw)


def compose_maps(outer: FractionalMap, inner: FractionalMap) -> FractionalMap:
    """Compose value relations. The caller tracks where each conversion can run."""
    a = outer.a * inner.a + outer.b * inner.c
    b = outer.a * inner.b + outer.b * inner.d
    c = outer.c * inner.a + outer.d * inner.c
    d = outer.c * inner.b + outer.d * inner.d
    if not (c or d):
        raise ZeroDivisionError('the inner conversion is always at the outer pole')
    if a * d == b * c:
        value = b / d if d else a / c
        return FractionalMap(0, value, 0, 1)
    return FractionalMap(a, b, c, d)
