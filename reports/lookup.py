from reports.record import SignedReport
from reports.store import ReportStore


def get_report(store: ReportStore, report_id: int) -> SignedReport | None:
    return store.read(report_id)
