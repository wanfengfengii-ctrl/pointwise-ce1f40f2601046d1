from exchange.receipts import ReceivedPiece
from reports.record import ReportSnapshot, SignedReport
from reports.store import ReportStore
from review.partition import DecisionPartition
from review.requests import ComparisonRequest


def publish_report(store: ReportStore, request: ComparisonRequest, partition: DecisionPartition,
                   left: ReceivedPiece, right: ReceivedPiece) -> SignedReport:
    if request.receipt_ids != (left.receipt_id, right.receipt_id):
        raise ValueError('report origins must follow the selected receipt order')
    snapshot = ReportSnapshot(request, (left.origin, right.origin), partition)
    return store.commit(snapshot)
