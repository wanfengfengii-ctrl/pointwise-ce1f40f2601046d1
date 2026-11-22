from collections.abc import Iterator
from functools import cmp_to_key

from bench.fractional import RationalInput
from exchange.calibration_body import CalibrationBody, SupportInterval
from exchange.receipts import ReceiptStore
from reports.publish import publish_report
from reports.record import SignedReport
from reports.store import ReportStore
from review.difference import build_difference, difference_cuts, within_tolerance
from review.endpoints import Endpoint, compare_endpoints, polynomial_sign, rational_between
from review.partition import DecisionInterval, DecisionPartition, assemble_partition
from review.requests import ComparisonRequest, InvalidComparisonRequest, validate_request


def _coverage_span(body: CalibrationBody) -> SupportInterval:
    first, last = body.support[0], body.support[-1]
    return SupportInterval(first.lower, last.upper, first.lower_closed, last.upper_closed)


def _covers(span: SupportInterval, point: Endpoint) -> bool:
    if span.lower is not None:
        order = compare_endpoints(point, span.lower)
        if order < 0 or (order == 0 and not span.lower_closed):
            return False
    if span.upper is not None:
        order = compare_endpoints(point, span.upper)
        if order > 0 or (order == 0 and not span.upper_closed):
            return False
    return True


def evaluate_window(request: ComparisonRequest, left: CalibrationBody,
                    right: CalibrationBody) -> DecisionPartition:
    left_map, right_map = left.terminal, right.terminal
    if left_map is None or right_map is None:
        return DecisionPartition((), (), (DecisionInterval(request.lower, request.upper),))

    left_span, right_span = _coverage_span(left), _coverage_span(right)
    predicate = build_difference(left_map, right_map, request.tolerance)
    cuts = {request.lower, request.upper}
    candidates = (left_span.lower, left_span.upper, right_span.lower, right_span.upper,
                  *difference_cuts(predicate))
    for point in candidates:
        if point is not None and compare_endpoints(request.lower, point) <= 0 and compare_endpoints(point, request.upper) <= 0:
            cuts.add(point)
    ordered = sorted(cuts, key=cmp_to_key(compare_endpoints))

    def classify(point: Endpoint) -> str:
        if not (_covers(left_span, point) and _covers(right_span, point)):
            return "no_common_evidence"
        if polynomial_sign(predicate.denominator, point) == 0:
            return "no_common_evidence"
        if within_tolerance(predicate, point):
            return "released"
        return "over_tolerance"

    def atoms() -> Iterator[tuple[str, DecisionInterval]]:
        for index, point in enumerate(ordered):
            yield classify(point), DecisionInterval(point, point)
            if index + 1 < len(ordered):
                next_point = ordered[index + 1]
                sample = rational_between(point, next_point)
                yield classify(sample), DecisionInterval(point, next_point, False, False)

    return assemble_partition(atoms())


def sign(receipts: ReceiptStore, reports: ReportStore, left_receipt: int, right_receipt: int,
         lower: RationalInput, upper: RationalInput, tolerance: RationalInput) -> SignedReport:
    request = validate_request(left_receipt, right_receipt, lower, upper, tolerance)
    if receipts.path.resolve() != reports.path.resolve():
        raise InvalidComparisonRequest("receipt and report stores must use the same center database")
    try:
        left = receipts.get(request.left_receipt)
        right = receipts.get(request.right_receipt)
    except KeyError as error:
        raise InvalidComparisonRequest(f"unknown received piece {error.args[0]}") from error
    if left.origin.unit != right.origin.unit:
        raise InvalidComparisonRequest("received pieces must use the same unit")
    partition = evaluate_window(request, left.body, right.body)
    return publish_report(reports, request, partition, left, right)
