from fractions import Fraction as Q

from review.compare import sign
from review.partition import DecisionInterval as I, DecisionPartition
from tests.support import CANCELING_MAP, HandoverCase, IDENTITY, stage


class TestHandoverDomain(HandoverCase):
    def test_later_range_creates_gap(self):
        old = [stage("meter", CANCELING_MAP),
               stage("range_gate", IDENTITY, [0, 2], "secondary"),
               stage("converter", CANCELING_MAP, evidence="secondary")]
        _, pair = self.install_pair(old, [stage("identity", IDENTITY)])
        self.detach_station()
        report = sign(self.receipts, self.reports, *pair, -1, 3, 0)
        expected = DecisionPartition((I(Q(-1), Q(0)), I(Q(2), Q(3))), (),
                                     (I(Q(0), Q(2), False, False),))
        self.assertEqual(report.snapshot.partition, expected, "换表误放行：后级量程在原设定轴上留下断档")
