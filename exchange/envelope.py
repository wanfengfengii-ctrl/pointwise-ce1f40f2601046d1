from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
import json
import re


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def _non_json_number(value: str) -> None:
    raise ValueError(f'invalid JSON number {value!r}')


def read_json(text: str) -> object:
    if not isinstance(text, str):
        raise ValueError('expected JSON text')
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_non_json_number)


def valid_number(value: object) -> bool:
    return type(value) is int and 1 <= value < 2**63


@dataclass(frozen=True)
class PieceOrigin:
    instrument_id: str
    unit: str
    revision_id: int
    source: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.instrument_id, self.unit, self.source)):
            raise ValueError('origin requires an instrument ID, unit and evidence source')
        if not valid_number(self.revision_id):
            raise ValueError('invalid origin revision ID')

    def as_data(self) -> dict:
        return {'instrument': self.instrument_id, 'unit': self.unit,
                'revision': self.revision_id, 'source': self.source}

    @classmethod
    def from_data(cls, data: object) -> 'PieceOrigin':
        if not isinstance(data, dict) or set(data) != {'instrument', 'unit', 'revision', 'source'}:
            raise ValueError('invalid origin fields')
        return cls(data['instrument'], data['unit'], data['revision'], data['source'])


@dataclass(frozen=True)
class V1Envelope:
    origin: PieceOrigin
    body: str
    digest: str


def _digest(payload: dict) -> str:
    return sha256(canonical_json(payload).encode('utf-8')).hexdigest()


def encode_envelope(origin: PieceOrigin, body: str) -> str:
    if not isinstance(body, str):
        raise ValueError('the V1 body must be JSON text')
    payload = {'version': 1, 'origin': origin.as_data(), 'body': body}
    return canonical_json({**payload, 'digest': _digest(payload)})


def verify_envelope(encoded: str) -> V1Envelope:
    raw = read_json(encoded)
    if not isinstance(raw, dict) or set(raw) != {'version', 'origin', 'body', 'digest'}:
        raise ValueError('invalid V1 envelope fields')
    version = raw['version']
    if type(version) is not int or version != 1:
        raise ValueError('unsupported envelope version')
    body, digest = raw['body'], raw['digest']
    if not isinstance(body, str) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('invalid envelope body or digest')
    payload = {'version': version, 'origin': raw['origin'], 'body': body}
    if not compare_digest(_digest(payload), digest):
        raise ValueError('envelope digest mismatch')
    return V1Envelope(PieceOrigin.from_data(raw['origin']), body, digest)
