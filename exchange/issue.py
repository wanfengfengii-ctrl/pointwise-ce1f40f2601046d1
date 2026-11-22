from dataclasses import dataclass
from fractions import Fraction

from bench.fractional import FractionalMap, compose_maps
from bench.stages import CalibrationStage
from exchange.calibration_body import CalibrationBody, SupportInterval, encode_body
from exchange.envelope import PieceOrigin, encode_envelope
from station.revision_store import RevisionStore


@dataclass(frozen=True)
class IssuedPiece:
    origin: PieceOrigin
    wire: str


def _sample_inside(interval: SupportInterval) -> Fraction:
    if interval.lower is None:
        return Fraction(0) if interval.upper is None else interval.upper - 1
    if interval.upper is None:
        return interval.lower + 1
    return (interval.lower + interval.upper) / 2


def _denominator_sign(relation: FractionalMap, interval: SupportInterval) -> int:
    # The tracked domain never contains a pole of the partial composition, so the
    # denominator keeps one nonzero sign on each domain interval.
    value = relation.c * _sample_inside(interval) + relation.d
    return (value > 0) - (value < 0)


def _clip_to_range(interval: SupportInterval, relation: FractionalMap,
                   lower: Fraction, upper: Fraction) -> SupportInterval | None:
    """Keep the part of `interval` where lower <= relation(x) <= upper.

    The range is closed, so constraint boundaries are closed ends unless they
    meet an already open end of the domain interval.
    """
    lo, hi = interval.lower, interval.upper
    lo_closed, hi_closed = interval.lower_closed, interval.upper_closed
    sign = _denominator_sign(relation, interval)
    for bound, keep_above in ((lower, True), (upper, False)):
        alpha = relation.a - bound * relation.c
        beta = relation.b - bound * relation.d
        if not alpha:
            # relation(x) - bound is the constant beta / (c x + d); this also
            # covers constant compositions, which must still pass the range gate.
            if not beta:
                continue
            if (sign * beta > 0) != keep_above:
                return None
            continue
        threshold = -beta / alpha
        if (sign * alpha > 0) == keep_above:
            if lo is None or threshold > lo:
                lo, lo_closed = threshold, True
        else:
            if hi is None or threshold < hi:
                hi, hi_closed = threshold, True
        if lo is not None and hi is not None and (
                lo > hi or (lo == hi and not (lo_closed and hi_closed))):
            return None
    return SupportInterval(lo, hi, lo_closed, hi_closed)


def _remove_point(domain: list[SupportInterval], point: Fraction) -> list[SupportInterval]:
    kept = []
    for interval in domain:
        if not interval.contains(point):
            kept.append(interval)
            continue
        if interval.lower is None or interval.lower < point:
            kept.append(SupportInterval(interval.lower, point, interval.lower_closed, False))
        if interval.upper is None or point < interval.upper:
            kept.append(SupportInterval(point, interval.upper, False, interval.upper_closed))
    return kept


def _calibration_body(stages: tuple[CalibrationStage, ...]) -> CalibrationBody:
    # Track the exact set of original settings that can complete every stage so
    # far. Each later stage checks its closed range and its nonzero denominator
    # against the input that actually arrives, i.e. the partial composition.
    domain = [SupportInterval(None, None)]
    terminal = FractionalMap(1, 0, 0, 1)
    for stage in stages:
        conversion = stage.conversion
        limits = stage.input_range
        if limits.lower is not None:
            domain = [clipped for interval in domain
                      if (clipped := _clip_to_range(interval, terminal,
                                                    limits.lower, limits.upper)) is not None]
        pole = conversion.pole
        if pole is not None:
            if not terminal.a and not terminal.c:
                if terminal.b / terminal.d == pole:
                    domain = []  # a constant composition always lands on the pole
            elif not terminal.c or pole * terminal.c != terminal.a:
                hit = (terminal.d * pole - terminal.b) / (terminal.a - terminal.c * pole)
                domain = _remove_point(domain, hit)
        if not domain:
            return CalibrationBody(None, ())
        try:
            terminal = compose_maps(conversion, terminal)
        except ZeroDivisionError:
            return CalibrationBody(None, ())
    if not domain:
        return CalibrationBody(None, ())
    return CalibrationBody(terminal, tuple(domain))


def issue(store: RevisionStore, revision_id: int) -> IssuedPiece:
    revision = store.get(revision_id)
    origin = PieceOrigin(revision.instrument.instrument_id, revision.instrument.unit,
                         revision.revision_id, revision.evidence.source)
    body = _calibration_body(revision.stages)
    return IssuedPiece(origin, encode_envelope(origin, encode_body(body)))
