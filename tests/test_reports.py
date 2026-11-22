from contextlib import closing
from fractions import Fraction as Q
import json
import sqlite3

from exchange.receipts import ReceiptStore
from reports.export import export_report
from reports.lookup import get_report
from reports.record import decode_report
from reports.store import ReportStore
from review.compare import sign
from review.partition import DecisionInterval as I, DecisionPartition as Partition
from station.instruments import get_instrument
from station.revision_store import RevisionStore
from tests.support import HandoverCase, IDENTITY, RECIPROCAL, ordinary_old, stage, table_counts


class TestReports(HandoverCase):
    def _sign_before_and_after_correction(self):
        revisions, pair = self.install_pair(ordinary_old(), [stage('new', (2, 3, 0, 1), [0, 2])])
        self.detach_station()
        before = sign(self.receipts, self.reports, *pair, 0, 2, 1)
        self.archive.rename(self.station_path)
        corrected = self.freeze('NEW-B', [stage('new', (2, 4, 0, 1), [0, 2])], '换装表勘误', revisions[1])
        new_id = self.accept(corrected, 'NEW-B')
        self.detach_station()
        after = sign(self.receipts, self.reports, pair[0], new_id, 0, 2, 1)
        return before, after, revisions, corrected

    def test_old_report(self):
        before, after, revisions, corrected = self._sign_before_and_after_correction()
        reopened = ReportStore(self.center_path)
        self.assertNotEqual(before.report_id, after.report_id)
        self.assertEqual(get_report(reopened, before.report_id), before)
        self.assertEqual(get_report(reopened, after.report_id), after)
        self.assertEqual(before.snapshot.partition, Partition((I(Q(0), Q(2)),), (), ()))
        self.assertEqual(after.snapshot.partition, Partition((), (I(Q(0), Q(2)),), ()))
        self.assertEqual(tuple(origin.revision_id for origin in before.snapshot.origins), revisions)
        self.assertEqual(tuple(origin.revision_id for origin in after.snapshot.origins), (revisions[0], corrected))
        self.assertEqual(tuple(origin.instrument_id for origin in before.snapshot.origins), ('OLD-A', 'NEW-B'))
        self.assertIsNone(get_report(reopened, after.report_id + 1))
        self.assertFalse(self.station_path.exists())
        self.assertEqual(self.signed_counts(), (2, 2))

    def test_offline_export(self):
        revisions, pair = self.install_pair([stage('identity', IDENTITY)], [stage('inverse', RECIPROCAL)])
        self.detach_station()
        original = sign(self.receipts, self.reports, *pair, '1/2', 2, 1)
        self.archive.rename(self.station_path)
        corrected = self.freeze('NEW-B', [stage('identity', IDENTITY)], '换装表勘误', revisions[1])
        updated = self.accept(corrected, 'NEW-B')
        self.detach_station()
        sign(self.receipts, self.reports, pair[0], updated, '1/2', 2, 1)
        reopened = ReportStore(self.center_path)
        exported = export_report(reopened, original.report_id)
        self.assertEqual(decode_report(exported), original)
        doc = json.loads(exported)
        lo_root = {'quadratic': [1, 1, -1], 'branch': 1}
        hi_root = {'quadratic': [1, -1, -1], 'branch': 1}
        self.assertEqual(doc['partition'], {'released': [[lo_root, hi_root, True, True]],
                         'over_tolerance': [['1/2', lo_root, True, False], [hi_root, '2', False, True]],
                         'no_common_evidence': []})
        self.assertEqual(doc['request'], {'receipts': list(pair), 'window': ['1/2', '2'], 'tolerance': '1'})
        self.assertEqual([origin['revision'] for origin in doc['origins']], list(revisions))
        self.assertEqual([origin['instrument'] for origin in doc['origins']], ['OLD-A', 'NEW-B'])
        self.assertEqual(doc['receipt'], {'report_id': original.report_id, 'token': original.receipt.token})
        self.assertIsNone(export_report(reopened, original.report_id + 100))

    def test_reinitialize(self):
        before, after, revisions, corrected = self._sign_before_and_after_correction()
        received_ids = (*before.snapshot.request.receipt_ids, after.snapshot.request.right_receipt)
        previous_pieces = tuple(self.receipts.get(number) for number in received_ids)
        self.archive.rename(self.station_path)
        station = RevisionStore(self.station_path)
        names = ('instruments', 'revisions', 'calibration_evidence', 'revision_stages')
        station_counts = table_counts(self.station_path, *names)
        previous = tuple(station.get(number) for number in (*revisions, corrected))
        receipts, reports = ReceiptStore(self.center_path), ReportStore(self.center_path)
        for _ in range(2):
            station.initialize()
            receipts.initialize()
            reports.initialize()
        self.assertEqual(table_counts(self.station_path, *names), station_counts)
        self.assertEqual(get_instrument(self.station_path, 'NEW-B').label, '换装表 B')
        self.assertEqual(tuple(station.get(number) for number in (*revisions, corrected)), previous)
        self.detach_station()
        self.assertEqual(tuple(receipts.get(number) for number in received_ids), previous_pieces)
        self.assertEqual(self.receipt_count(), 3)
        self.assertEqual(self.signed_counts(), (2, 2))
        self.assertEqual(get_report(reports, before.report_id), before)
        self.assertEqual(get_report(reports, after.report_id), after)

    def test_receipt_failure(self):
        _, pair = self.install_pair(ordinary_old(), [stage('new', (2, 3, 0, 1), [0, 2])])
        self.detach_station()
        baseline = sign(self.receipts, self.reports, *pair, 0, 2, 1)
        with closing(sqlite3.connect(self.center_path)) as connection, connection:
            connection.execute('''
                CREATE TRIGGER refuse_report_receipt BEFORE INSERT ON report_receipts
                BEGIN SELECT RAISE(ABORT, 'receipt write blocked'); END
            ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'receipt write blocked'):
            sign(self.receipts, self.reports, *pair, 0, 2, 0)
        self.assertEqual(self.signed_counts(), (1, 1))
        reopened = ReportStore(self.center_path)
        self.assertIsNone(get_report(reopened, baseline.report_id + 1))
        self.assertEqual(get_report(reopened, baseline.report_id), baseline)
        self.assertEqual(self.receipt_count(), 2)
        with closing(sqlite3.connect(self.center_path)) as connection, connection:
            connection.execute('DROP TRIGGER refuse_report_receipt')
        retry = sign(self.receipts, reopened, *pair, 0, 2, 0)
        self.assertEqual(retry.snapshot.partition, Partition((), (I(Q(0), Q(2)),), ()))
        self.assertEqual(self.signed_counts(), (2, 2))
