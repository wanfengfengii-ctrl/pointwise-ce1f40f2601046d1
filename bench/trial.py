from collections.abc import Iterable

from bench.fractional import RationalInput, parse_rational
from bench.stages import CalibrationStage, apply_stage
from bench.traces import TrialTrace, UnavailableStage
from station.revision_store import RevisionStore


def run_trial(stages: Iterable[CalibrationStage], setting: RationalInput) -> TrialTrace:
    original = parse_rational(setting)
    value = original
    readings = []
    for stage in stages:
        reading = apply_stage(stage, value)
        if isinstance(reading, UnavailableStage):
            return TrialTrace(original, tuple(readings), None, reading)
        readings.append(reading)
        value = reading.output_value
    return TrialTrace(original, tuple(readings), value)


def trial(store: RevisionStore, revision_id: int, setting: RationalInput) -> TrialTrace:
    revision = store.get(revision_id)
    return run_trial(revision.stages, setting)
