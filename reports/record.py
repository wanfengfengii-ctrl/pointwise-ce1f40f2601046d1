from dataclasses import dataclass
import re

from exchange.envelope import PieceOrigin, canonical_json, read_json, valid_number
from review.endpoints import decode_endpoint, encode_endpoint
from review.partition import DecisionInterval, DecisionPartition
from review.requests import ComparisonRequest, validate_request


@dataclass(frozen=True)
class ReportSnapshot:
    request: ComparisonRequest
    origins: tuple[PieceOrigin, PieceOrigin]
    partition: DecisionPartition


@dataclass(frozen=True)
class ReportReceipt:
    report_id: int
    token: str

    def __post_init__(self) -> None:
        if not valid_number(self.report_id) or not isinstance(self.token, str) or not re.fullmatch('[0-9a-f]{64}', self.token):
            raise ValueError('invalid report receipt')


@dataclass(frozen=True)
class SignedReport:
    snapshot: ReportSnapshot
    receipt: ReportReceipt

    @property
    def report_id(self) -> int:
        return self.receipt.report_id


def _interval_data(interval: DecisionInterval) -> list:
    return [encode_endpoint(interval.lower), encode_endpoint(interval.upper),
            interval.lower_closed, interval.upper_closed]


def _interval_from_data(raw: object) -> DecisionInterval:
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError('invalid interval in report snapshot')
    lower, upper, lower_closed, upper_closed = raw
    return DecisionInterval(decode_endpoint(lower), decode_endpoint(upper), lower_closed, upper_closed)


def snapshot_data(snapshot: ReportSnapshot) -> dict:
    request = snapshot.request
    partition = snapshot.partition
    return {
        'request': {'receipts': list(request.receipt_ids), 'window': [str(request.lower), str(request.upper)],
                    'tolerance': str(request.tolerance)},
        'origins': [origin.as_data() for origin in snapshot.origins],
        'partition': {
            'released': [_interval_data(interval) for interval in partition.released],
            'over_tolerance': [_interval_data(interval) for interval in partition.over_tolerance],
            'no_common_evidence': [_interval_data(interval) for interval in partition.no_common_evidence],
        },
    }


def _fields(raw: object, *names: str) -> dict:
    if not isinstance(raw, dict) or set(raw) != set(names):
        raise ValueError('invalid report snapshot fields')
    return raw


def _pair(raw: object) -> list:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError('expected an ordered pair in report snapshot')
    return raw


def _intervals(raw: object) -> tuple[DecisionInterval, ...]:
    if not isinstance(raw, list):
        raise ValueError('expected an interval group')
    return tuple(_interval_from_data(part) for part in raw)


def snapshot_from_data(data: object) -> ReportSnapshot:
    raw = _fields(data, 'request', 'origins', 'partition')
    requested = _fields(raw['request'], 'receipts', 'window', 'tolerance')
    left, right = _pair(requested['receipts'])
    lower, upper = _pair(requested['window'])
    request = validate_request(left, right, lower, upper, requested['tolerance'])
    first, second = _pair(raw['origins'])
    origins = (PieceOrigin.from_data(first), PieceOrigin.from_data(second))
    groups = _fields(raw['partition'], 'released', 'over_tolerance', 'no_common_evidence')
    partition = DecisionPartition(_intervals(groups['released']), _intervals(groups['over_tolerance']),
                                  _intervals(groups['no_common_evidence']))
    return ReportSnapshot(request, origins, partition)


def encode_report(report: SignedReport) -> str:
    data = snapshot_data(report.snapshot)
    data['receipt'] = {'report_id': report.report_id, 'token': report.receipt.token}
    return canonical_json(data)


def decode_report(text: str) -> SignedReport:
    data = _fields(read_json(text), 'request', 'origins', 'partition', 'receipt')
    receipt = _fields(data.pop('receipt'), 'report_id', 'token')
    return SignedReport(snapshot_from_data(data), ReportReceipt(receipt['report_id'], receipt['token']))
