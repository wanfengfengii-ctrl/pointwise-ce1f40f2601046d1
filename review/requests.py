from dataclasses import dataclass
from fractions import Fraction

from bench.fractional import RationalInput, parse_rational
from exchange.envelope import valid_number


class InvalidComparisonRequest(ValueError):
    """The selected evidence or quality parameters are invalid."""


@dataclass(frozen=True)
class ComparisonRequest:
    left_receipt: int
    right_receipt: int
    lower: Fraction
    upper: Fraction
    tolerance: Fraction

    @property
    def receipt_ids(self) -> tuple[int, int]:
        return self.left_receipt, self.right_receipt


def validate_request(left_receipt: int, right_receipt: int, lower: RationalInput,
                     upper: RationalInput, tolerance: RationalInput) -> ComparisonRequest:
    if not valid_number(left_receipt) or not valid_number(right_receipt):
        raise InvalidComparisonRequest('two positive receipt IDs are required')
    try:
        lo, hi, allowed = (parse_rational(value) for value in (lower, upper, tolerance))
    except ValueError as error:
        raise InvalidComparisonRequest(str(error)) from error
    if lo > hi:
        raise InvalidComparisonRequest('reversed comparison window')
    if allowed < 0:
        raise InvalidComparisonRequest('negative tolerance')
    return ComparisonRequest(left_receipt, right_receipt, lo, hi, allowed)
