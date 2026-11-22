from dataclasses import dataclass
import json


@dataclass(frozen=True)
class CalibrationEvidence:
    source: str
    records: tuple[tuple[str, str], ...]

    def record(self, reference: str) -> str:
        return dict(self.records)[reference]


def validate_evidence(raw: object) -> CalibrationEvidence:
    if not isinstance(raw, dict) or set(raw) != {'source', 'records'}:
        raise ValueError('evidence requires source and records')
    source = raw['source']
    records = raw['records']
    if not isinstance(source, str) or not source.strip():
        raise ValueError('evidence source is required')
    if not isinstance(records, dict) or not records:
        raise ValueError('at least one named evidence record is required')
    for reference, detail in records.items():
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError('invalid evidence reference')
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError(f'empty record for {reference!r}')
    return CalibrationEvidence(source, tuple(sorted(records.items())))


def encode_evidence(evidence: CalibrationEvidence) -> str:
    return json.dumps({'source': evidence.source, 'records': dict(evidence.records)},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def decode_evidence(encoded: str) -> CalibrationEvidence:
    return validate_evidence(json.loads(encoded))
