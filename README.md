# 换表校验交班台账

制造厂公用工程的计量班把旧表和换装表的原记录交给站端。技师登记仪表、冻结校准修订并逐级试算。中心质控员实收固定件后可以关站签发。下一班按报告号领取原判定，安排免复测、超差复测和补证。

## 运行

使用 Python 3.11 标准库，在项目根目录运行。

```sh
python3 -B check_project.py
python3 -B demo.py
```

核验入口由运行环境提供，运行 `tests` 包的完整回归。演示读取 `samples/calibrations.json`，在独立临时目录创建站库和中心库，移开站库后签发并在重开后导出。样例使用 bar。旧表先做 `x+1` 再做 `2t`，输入量程依次为 `[0,2]` 和 `[1,3]`。换装表初版是 `2x+3`。在闭窗 `[0,2]` 内以容差 `1` 核验，初版全窗放行。勘误 `2x+4` 全窗超差，复领初版仍得到原结论和原回执。

## 站端 API

- `station.revision_store.RevisionStore(path).initialize()` 创建缺失表。`station.instruments.register_instrument(path, instrument_id, label, unit)` 登记实体表号，`get_instrument(path, instrument_id)` 读取登记。重复登记相同信息可复用，冲突登记会拒绝。
- `station.revisions.import_revision(store, instrument_id, evidence, stages, supersedes=None)` 返回冻结修订号。原据形如 `{"source":"台架原单 A-01","records":{"r1":"原记录正文"}}`。每级形如 `{"name":"偏置","map":[1,1,0,1],"range":[0,2],"evidence":"r1"}`。级名在修订内唯一，原据引用必须存在。勘误指定同表前版。非法导入抛出 `InvalidRevision`，整次拒绝。
- `bench.trial.trial(store, revision_id, setting)` 返回 `TrialTrace`。可用时 `value` 为末值，`readings` 按顺序保留每级输入、输出和原据引用。不可用时 `unavailable` 指明首个失败级及 `out_of_range` 或 `pole`，末值为空。未知修订抛出 `KeyError`，非法数值抛出 `ValueError`。
- `exchange.issue.issue(store, revision_id)` 返回 `IssuedPiece`，其中 `wire` 可独立传递。未知修订抛出 `KeyError`。

每级关系为 `(ax+b)/(cx+d)`，四个系数按 `a,b,c,d` 传入。系数和设定值接受 `Fraction`、整数及整数字符串或 `p/q` 字符串。分母 `q` 为正整数，有限量程用两个有理端点，`null` 表示全实轴。拒绝浮点、布尔值、逆序量程和恒零分母的级。闭量程端点也必须满足该级分母非零。允许常值级和合法空有效域。

## 实收、签发和复领

- `exchange.receipts.ReceiptStore(path).initialize()` 和 `reports.store.ReportStore(path).initialize()` 在同一个中心库创建各自的表。三处初始化均可重复执行，保留原有用户数据、编号和快照。
- `exchange.receive.receive(receipts, wire, expected_instrument)` 返回实收号。错表、坏外层或非法正文抛出 `RejectedPiece`，无新增实收记录。每次成功验收有自己的实收号。
- `review.compare.sign(receipts, reports, left_receipt, right_receipt, lower, upper, tolerance)` 返回 `SignedReport`。两个实收号按调用顺序绑定到报告，单位必须相同。窗可为闭单点。非法窗口、容差、实收号或单位组合抛出 `InvalidComparisonRequest`。SQLite 签存失败向调用方传播，事务撤销报告和回执。
- `reports.lookup.get_report(reports, report_id)` 读回原签存快照。`reports.export.export_report(reports, report_id)` 以 JSON 导出同一快照。未知号均返回 `None`。领取和导出只读取中心签存账。

V1 外层有 `version`、`origin`、`body`、`digest` 四个字段。出处固定表号、单位、冻结修订号和原据来源。`body` 是 JSON 字符串，含 `support` 和 `terminal`。支持域使用有序互不相连的 `[lower, upper, lower_closed, upper_closed]`，有限端点用有理字符串，无界端用 `null` 且为开端。末级关系用四个有理系数，空支持域对应 `terminal: null`。SHA-256 摘要绑定外层版本、出处和正文，提供传送完整性校验。实收库保存正文与身份，站端原记录和逐级读数留站。

当两件在某设定点都可完成时，中心对绝对末值差作精确判定，等容差放行。其余有共同证据的点超差，缺少任一链资格的点列为无共同证据。区间结果按 `released`、`over_tolerance`、`no_common_evidence` 分组，各组升序。有限报告端点用有理字符串，或以 `{"quadratic":[a,b,c],"branch":1}` 表示本原整系数方程 `ax²+bx+c=0` 的大根，`branch` 为 `-1` 时取小根。回执始终绑定当次原顺序和原分区。
