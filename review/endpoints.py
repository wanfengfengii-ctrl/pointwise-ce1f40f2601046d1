from dataclasses import dataclass
from fractions import Fraction
from math import gcd, isqrt, lcm

from bench.fractional import parse_rational


@dataclass(frozen=True)
class QuadraticEndpoint:
    a: int
    b: int
    c: int
    branch: int

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in (self.a, self.b, self.c, self.branch)):
            raise ValueError('quadratic endpoint coefficients and branch must be integers')
        if self.a <= 0 or gcd(self.a, self.b, self.c) != 1 or self.branch not in (-1, 1):
            raise ValueError('quadratic endpoint must have a primitive positive-leading polynomial and a branch')
        discriminant = self.discriminant
        if discriminant <= 0 or isqrt(discriminant) ** 2 == discriminant:
            raise ValueError('quadratic endpoint must be a real irrational root')

    @property
    def discriminant(self) -> int:
        return self.b * self.b - 4 * self.a * self.c

    def bounds(self, bits: int) -> tuple[Fraction, Fraction]:
        scale = 1 << bits
        floor = isqrt(self.discriminant * scale * scale)
        denominator = 2 * self.a * scale
        center = -self.b * scale
        if self.branch == 1:
            return Fraction(center + floor, denominator), Fraction(center + floor + 1, denominator)
        return Fraction(center - floor - 1, denominator), Fraction(center - floor, denominator)


Endpoint = Fraction | QuadraticEndpoint
Polynomial = tuple[Fraction, Fraction, Fraction]


def real_quadratic_roots(a: Fraction, b: Fraction, c: Fraction) -> tuple[Endpoint, ...]:
    a, b, c = map(Fraction, (a, b, c))
    if not a:
        return (-c / b,) if b else ()
    scale = lcm(a.denominator, b.denominator, c.denominator)
    aa, bb, cc = (int(value * scale) for value in (a, b, c))
    factor = gcd(aa, bb, cc)
    if aa < 0:
        factor = -factor
    aa, bb, cc = aa // factor, bb // factor, cc // factor
    discriminant = bb * bb - 4 * aa * cc
    if discriminant < 0:
        return ()
    root = isqrt(discriminant)
    if root * root == discriminant:
        return tuple(sorted({Fraction(-bb - root, 2 * aa), Fraction(-bb + root, 2 * aa)}))
    return QuadraticEndpoint(aa, bb, cc, -1), QuadraticEndpoint(aa, bb, cc, 1)


def _bounds(point: Endpoint, bits: int) -> tuple[Fraction, Fraction]:
    if isinstance(point, QuadraticEndpoint):
        return point.bounds(bits)
    rational = Fraction(point)
    return rational, rational


def compare_endpoints(left: Endpoint, right: Endpoint) -> int:
    # Primitive irreducible polynomials and branch uniquely identify irrational endpoints.
    if left == right:
        return 0
    bits = 8
    while True:
        left_lo, left_hi = _bounds(left, bits)
        right_lo, right_hi = _bounds(right, bits)
        if left_hi <= right_lo:
            return -1
        if right_hi <= left_lo:
            return 1
        bits *= 2


def rational_between(left: Endpoint, right: Endpoint) -> Fraction:
    if compare_endpoints(left, right) >= 0:
        raise ValueError('a sample requires increasing endpoints')
    bits = 8
    while True:
        _, lower_bound = _bounds(left, bits)
        upper_bound, _ = _bounds(right, bits)
        if lower_bound < upper_bound:
            return (lower_bound + upper_bound) / 2
        bits *= 2


def polynomial_sign(polynomial: Polynomial, point: Endpoint) -> int:
    a, b, c = polynomial
    if isinstance(point, QuadraticEndpoint):
        # Reduce at the exact root to a linear polynomial in that root.
        scale = Fraction(a) / point.a
        slope = b - scale * point.b
        constant = c - scale * point.c
        if slope:
            orientation = 1 if slope > 0 else -1
            return orientation * compare_endpoints(point, -constant / slope)
        value = constant
    else:
        value = (a * point + b) * point + c
    return (value > 0) - (value < 0)


def encode_endpoint(point: Endpoint) -> str | dict:
    if isinstance(point, QuadraticEndpoint):
        return {'quadratic': [point.a, point.b, point.c], 'branch': point.branch}
    return str(point)


def decode_endpoint(raw: object) -> Endpoint:
    if isinstance(raw, str):
        return parse_rational(raw)
    if not isinstance(raw, dict) or set(raw) != {'quadratic', 'branch'}:
        raise ValueError('invalid decision endpoint')
    polynomial = raw['quadratic']
    if not isinstance(polynomial, list) or len(polynomial) != 3:
        raise ValueError('quadratic endpoint requires three coefficients')
    return QuadraticEndpoint(*polynomial, raw['branch'])
