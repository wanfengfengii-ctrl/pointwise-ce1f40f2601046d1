from contextlib import closing
from hashlib import sha256
from pathlib import Path

from exchange.envelope import canonical_json, read_json, valid_number
from exchange.receipts import open_center
from reports.record import ReportReceipt, ReportSnapshot, SignedReport, snapshot_data, snapshot_from_data


class ReportStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        with closing(open_center(self.path, 'rwc')) as connection:
            connection.executescript('''
                BEGIN;
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY,
                    snapshot TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS report_receipts (
                    report_id INTEGER PRIMARY KEY REFERENCES reports(id),
                    token TEXT NOT NULL UNIQUE
                );
                COMMIT;
            ''')

    def commit(self, snapshot: ReportSnapshot) -> SignedReport:
        encoded = canonical_json(snapshot_data(snapshot))
        with closing(open_center(self.path, 'rw')) as connection, connection:
            report_id = connection.execute(
                'INSERT INTO reports (snapshot) VALUES (?)', (encoded,),
            ).lastrowid
            token = sha256(f'{report_id}:{encoded}'.encode('utf-8')).hexdigest()
            connection.execute(
                'INSERT INTO report_receipts (report_id, token) VALUES (?, ?)', (report_id, token),
            )
        return SignedReport(snapshot, ReportReceipt(report_id, token))

    def read(self, report_id: int) -> SignedReport | None:
        if not valid_number(report_id):
            return None
        with closing(open_center(self.path, 'ro')) as connection:
            row = connection.execute('''
                SELECT r.snapshot, c.token
                FROM reports AS r JOIN report_receipts AS c ON c.report_id = r.id
                WHERE r.id = ?
            ''', (report_id,)).fetchone()
        if row is None:
            return None
        encoded, token = row
        return SignedReport(snapshot_from_data(read_json(encoded)), ReportReceipt(report_id, token))
