from dataclasses import dataclass
from fractions import Fraction

from exchange.calibration_body import TerminalRelation
from review.endpoints import Endpoint, Polynomial, polynomial_sign, real_quadratic_roots


@dataclass(frozen=True)
class DifferencePredicate:
    numerator: Polynomial
    denominator: Polynomial
    tolerance: Fraction

    def thresholds(self) -> tuple[Polynomial, Polynomial]:
        below = tuple(a - self.tolerance * b for a, b in zip(self.numerator, self.denominator))
        above = tuple(a + self.tolerance * b for a, b in zip(self.numerator, self.denominator))
        return below, above


def _product(a: Fraction, b: Fraction, c: Fraction, d: Fraction) -> Polynomial:
    return a * c, a * d + b * c, b * d


def build_difference(left: TerminalRelation, right: TerminalRelation,
                     tolerance: Fraction) -> DifferencePredicate:
    left_term = _product(left.a, left.b, right.c, right.d)
    right_term = _product(right.a, right.b, left.c, left.d)
    numerator = tuple(a - b for a, b in zip(left_term, right_term))
    denominator = _product(left.c, left.d, right.c, right.d)
    return DifferencePredicate(numerator, denominator, tolerance)


def difference_cuts(predicate: DifferencePredicate) -> set[Endpoint]:
    return {root for polynomial in (predicate.denominator, *predicate.thresholds())
            for root in real_quadratic_roots(*polynomial)}


def within_tolerance(predicate: DifferencePredicate, point: Endpoint) -> bool:
    if polynomial_sign(predicate.denominator, point) == 0:
        raise ZeroDivisionError('cannot compare terminal values at a pole')
    below, above = predicate.thresholds()
    # (A - tB)(A + tB) <= 0 is equivalent to |A/B| <= t for B != 0.
    return polynomial_sign(below, point) * polynomial_sign(above, point) <= 0
