from fractions import Fraction as Q
import json

from exchange.issue import issue
from exchange.receive import receive
from reports.lookup import get_report
from reports.record import snapshot_data
from review.compare import sign
from review.endpoints import QuadraticEndpoint
from review.partition import DecisionInterval as I, DecisionPartition as Partition
from review.requests import InvalidComparisonRequest
from station.instruments import register_instrument
from tests.support import HandoverCase, IDENTITY, RECIPROCAL, canceling_chain, ordinary_old, stage


class TestReview(HandoverCase):
    def test_exact_tolerance(self):
        _, pair = self.install_pair(ordinary_old(), [stage('new', (2, 3, 0, 1), [0, 2])])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, 0, 2, 1)
        self.assertEqual(report.snapshot.partition, Partition((I(Q(0), Q(2)),), (), ()))
        self.assertEqual(report.snapshot.request.receipt_ids, pair)
        self.assertEqual(self.signed_counts(), (1, 1))

    def test_quadratic_boundaries(self):
        _, pair = self.install_pair([stage('identity', IDENTITY)], [stage('inverse', RECIPROCAL)])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, '1/2', 2, 1)
        lower = QuadraticEndpoint(1, 1, -1, 1)
        upper = QuadraticEndpoint(1, -1, -1, 1)
        expected = Partition((I(lower, upper),), (I(Q(1, 2), lower, True, False),
                                                  I(upper, Q(2), False, True)), ())
        self.assertEqual(report.snapshot.partition, expected)
        self.assertEqual(get_report(self.reports, report.report_id).snapshot.partition, expected)
        self.assertTrue(report.snapshot.partition.released[0].contains(Q(619, 1000)))
        self.assertFalse(any(part.contains(Q(619, 1000)) for part in report.snapshot.partition.over_tolerance))
        single = sign(self.receipts, self.reports, *pair, '619/1000', '619/1000', 1)
        self.assertEqual(single.snapshot.partition, Partition((I(Q(619, 1000), Q(619, 1000)),), (), ()))

    def test_invalid_window(self):
        _, pair = self.install_pair(ordinary_old(), [stage('new', (2, 3, 0, 1))])
        self.detach_station()
        for window in ((2, 0, 1), (0, 2, -1), ('1/0', 2, 1), (0, 2, 0.5)):
            with self.subTest(window=window), self.assertRaises(InvalidComparisonRequest):
                sign(self.receipts, self.reports, *pair, *window)
            self.assertEqual(self.signed_counts(), (0, 0))
        with self.assertRaises(InvalidComparisonRequest):
            sign(self.receipts, self.reports, pair[0], 100, 0, 2, 1)
        self.assertEqual(self.signed_counts(), (0, 0))

    def test_mixed_units(self):
        register_instrument(self.station_path, 'THIRD', '异单位对照', 'psi')
        first = self.freeze('OLD-A', [stage('identity', IDENTITY)], 'bar')
        second = self.freeze('THIRD', [stage('identity', IDENTITY)], 'psi')
        pair = (self.accept(first, 'OLD-A'), self.accept(second, 'THIRD'))
        self.detach_station()
        with self.assertRaises(InvalidComparisonRequest):
            sign(self.receipts, self.reports, *pair, 0, 2, 0)
        self.assertEqual(self.signed_counts(), (0, 0))

    def test_constant_hits_pole(self):
        chain = [stage('constant', (0, 1, 0, 1), [0, 2]),
                 stage('ratio', (0, 1, 1, -1), [1, 3], 'secondary')]
        _, pair = self.install_pair(chain, [stage('identity', IDENTITY)])
        self.detach_station()
        body = self.receipts.get(pair[0]).body
        self.assertIsNone(body.terminal)
        self.assertFalse(body.support)
        report = sign(self.receipts, self.reports, *pair, 0, 2, 0)
        self.assertEqual(report.snapshot.partition, Partition((), (), (I(Q(0), Q(2)),)))

    def test_mid_chain_hole(self):
        _, pair = self.install_pair(canceling_chain(), [stage('identity', IDENTITY)])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, 0, 2, 0)
        partition = Partition((I(Q(0), Q(1), True, False), I(Q(1), Q(2), False, True)), (), (I(Q(1), Q(1)),))
        self.assertEqual(report.snapshot.partition, partition, '换表误放行：设定值 1 必须单列无共同证据')
        self.assertEqual(self.signed_counts(), (1, 1))
        loaded = get_report(self.reports, report.report_id)
        self.assertEqual(loaded, report)
        expected = {'released': [['0', '1', True, False], ['1', '2', False, True]],
                    'over_tolerance': [], 'no_common_evidence': [['1', '1', True, True]]}
        observed = snapshot_data(loaded.snapshot)['partition']
        self.assertEqual(observed, expected)
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v6.mid_chain_hole',
            'input': {'old': [[1, 0, 1, -1], [1, 0, 1, -1]], 'new': [1, 0, 0, 1],
                      'window': ['0', '2'], 'tolerance': '0'},
            'expected': expected, 'actual': snapshot_data(report.snapshot)['partition'],
            'downstream_expected': {'partition': expected, 'success_receipts': 1},
            'downstream_actual': {'partition': observed, 'success_receipts': self.signed_counts()[1]},
            'code_paths': ['exchange/issue.py', 'exchange/receive.py', 'review/compare.py', 'reports/store.py'],
            'oracle': '代入两级可得 x≠1 时末值为 x，x=1 在第一级分母为零。',
        }, ensure_ascii=False))

    def test_constant_after_hole(self):
        constant = stage('fixed', (0, 7, 0, 1), [0, 2])
        _, pair = self.install_pair([*canceling_chain(), constant], [constant])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, 0, 2, 0)
        expected = Partition((I(Q(0), Q(1), True, False), I(Q(1), Q(2), False, True)), (), (I(Q(1), Q(1)),))
        self.assertEqual(report.snapshot.partition, expected)
        for edge in (0, 2):
            self.assertEqual(self.receipts.get(pair[0]).body.terminal.value_at(edge), Q(7))
        self.assertFalse(self.receipts.get(pair[0]).body.supports(1))

    def test_point_range_and_terminal_pole(self):
        chain = [stage('fixed', (0, 7, 0, 1), [1, 1])]
        _, pair = self.install_pair(chain, [stage('fixed', (0, 7, 0, 1))])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, 0, 2, 0)
        self.assertEqual(report.snapshot.partition, Partition((I(Q(1), Q(1)),), (), (
            I(Q(0), Q(1), True, False), I(Q(1), Q(2), False, True))))

    def test_denominator_sign_and_pole(self):
        _, pair = self.install_pair([stage('zero', (0, 0, 0, 1))], [stage('inverse', RECIPROCAL)])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, -2, 2, 1)
        expected = Partition((I(Q(-2), Q(-1)), I(Q(1), Q(2))),
                             (I(Q(-1), Q(0), False, False), I(Q(0), Q(1), False, False)),
                             (I(Q(0), Q(0)),))
        self.assertEqual(report.snapshot.partition, expected)

    def test_center_uses_admitted_support(self):
        from exchange.envelope import PieceOrigin, encode_envelope

        origin = PieceOrigin('OLD-A', 'bar', 1, '独立校验件')
        body = '{"support":[[null,"1",false,false],["1",null,false,false]],"terminal":["1","0","0","1"]}'
        left = receive(self.receipts, encode_envelope(origin, body), 'OLD-A')
        revision = self.freeze('NEW-B', [stage('identity', IDENTITY)], '全域对照')
        right = receive(self.receipts, issue(self.station, revision).wire, 'NEW-B')
        self.detach_station()
        report = sign(self.receipts, self.reports, left, right, 1, 1, 0)
        self.assertEqual(report.snapshot.partition, Partition((), (), (I(Q(1), Q(1)),)))
