from reports.lookup import get_report
from reports.record import encode_report
from reports.store import ReportStore


def export_report(store: ReportStore, report_id: int) -> str | None:
    report = get_report(store, report_id)
    return None if report is None else encode_report(report)
