from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class StageReading:
    stage: str
    input_value: Fraction
    output_value: Fraction
    evidence_ref: str


@dataclass(frozen=True)
class UnavailableStage:
    stage: str
    input_value: Fraction
    evidence_ref: str
    reason: Literal['out_of_range', 'pole']


@dataclass(frozen=True)
class TrialTrace:
    setting: Fraction
    readings: tuple[StageReading, ...]
    value: Fraction | None
    unavailable: UnavailableStage | None = None

    @property
    def completed(self) -> bool:
        return self.unavailable is None
