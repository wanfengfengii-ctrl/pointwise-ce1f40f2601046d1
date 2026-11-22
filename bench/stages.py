from dataclasses import dataclass

from bench.fractional import FractionalMap, RationalInput, parse_map, parse_rational
from bench.ranges import InputRange, parse_input_range
from bench.traces import StageReading, UnavailableStage


@dataclass(frozen=True)
class CalibrationStage:
    name: str
    conversion: FractionalMap
    input_range: InputRange
    evidence_ref: str


def parse_stage(raw: object) -> CalibrationStage:
    if not isinstance(raw, dict) or set(raw) != {'name', 'map', 'range', 'evidence'}:
        raise ValueError('stage requires name, map, range and evidence')
    name, reference = raw['name'], raw['evidence']
    if any(not isinstance(value, str) or not value.strip() for value in (name, reference)):
        raise ValueError('stage name and evidence reference are required')
    return CalibrationStage(name, parse_map(raw['map']), parse_input_range(raw['range']), reference)


def stage_data(stage: CalibrationStage) -> dict:
    limits = stage.input_range
    bounds = None if limits.lower is None else [str(limits.lower), str(limits.upper)]
    return {
        'name': stage.name,
        'map': [str(value) for value in stage.conversion.coefficients],
        'range': bounds,
        'evidence': stage.evidence_ref,
    }


def apply_stage(stage: CalibrationStage, value: RationalInput) -> StageReading | UnavailableStage:
    setting = parse_rational(value)
    if not stage.input_range.contains(setting):
        return UnavailableStage(stage.name, setting, stage.evidence_ref, 'out_of_range')
    try:
        result = stage.conversion.value_at(setting)
    except ZeroDivisionError:
        return UnavailableStage(stage.name, setting, stage.evidence_ref, 'pole')
    return StageReading(stage.name, setting, result, stage.evidence_ref)
