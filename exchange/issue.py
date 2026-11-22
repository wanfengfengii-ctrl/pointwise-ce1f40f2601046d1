from dataclasses import dataclass

from bench.fractional import FractionalMap, compose_maps
from bench.stages import CalibrationStage
from exchange.calibration_body import CalibrationBody, SupportInterval, encode_body
from exchange.envelope import PieceOrigin, encode_envelope
from station.revision_store import RevisionStore


@dataclass(frozen=True)
class IssuedPiece:
    origin: PieceOrigin
    wire: str


def _calibration_body(stages: tuple[CalibrationStage, ...]) -> CalibrationBody:
    terminal = FractionalMap(1, 0, 0, 1)
    try:
        for stage in stages:
            terminal = compose_maps(stage.conversion, terminal)
    except ZeroDivisionError:
        return CalibrationBody(None, ())

    limits = stages[0].input_range
    lower, upper = limits.lower, limits.upper
    pole = terminal.pole
    if pole is None or not limits.contains(pole):
        return CalibrationBody(terminal, (SupportInterval(lower, upper, lower is not None,
                                                          upper is not None),))

    support = []
    if lower is None or lower < pole:
        support.append(SupportInterval(lower, pole, lower is not None, False))
    if upper is None or pole < upper:
        support.append(SupportInterval(pole, upper, False, upper is not None))
    return CalibrationBody(terminal if support else None, tuple(support))


def issue(store: RevisionStore, revision_id: int) -> IssuedPiece:
    revision = store.get(revision_id)
    origin = PieceOrigin(revision.instrument.instrument_id, revision.instrument.unit,
                         revision.revision_id, revision.evidence.source)
    body = _calibration_body(revision.stages)
    return IssuedPiece(origin, encode_envelope(origin, encode_body(body)))
