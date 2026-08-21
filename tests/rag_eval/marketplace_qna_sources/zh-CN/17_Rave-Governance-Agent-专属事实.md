## Rave Governance Agent 专属事实

本篇只收录 Rave 专属事实；通用的产品定位、资金托管、Mint／Redeem 流程、既有持有人条款和赎回后投票权规则仅见文档 04、10、11、12。

**Q：Rave Governance Agent 是做什么的？**

它把 $RAVE 铸造成 vRAVE 份额；持有人可参与 RaveDAO 治理，并累积以 $RAVE 计价的固定奖励。

**Q：vRAVE 是什么？**

vRAVE 是这个 Agent 的份额代币，由持有人存入的 $RAVE 支持。持有 vRAVE 代表相应的 RaveDAO 治理资格和累积中的 $RAVE 奖励。

**Q：直接持有 $RAVE 和持有 vRAVE 有什么区别？**

直接持有 $RAVE 不会通过这个 Agent 累积奖励或参加其治理；铸造成 vRAVE 后，资金进入合约机制，并获得治理资格与固定奖励累积。

**Q：Rave Governance Agent 由谁发行？**

它由 Moss Agent Marketplace 与 RaveDAO 合作发行。

**Q：Rave Governance Agent 的 Mint 门槛、账户上限和次数规则是什么？**

没有最低 Mint 门槛；单账户上限为 50,000 $RAVE，用于降低单一地址在治理中的权重集中。可以分多次 Mint，但累计不得超过该上限。

**Q：可以用 $RAVE 之外的代币 Mint vRAVE 吗？**

不可以。这个 Agent 只接受 $RAVE，这是合约固定的接受代币。

**Q：Mint 后什么时候取得 RaveDAO 投票资格？**

份额完成结算并由持有人 Claim 后，vRAVE 才进入持仓，投票资格也从这时开始。

**Q：RaveDAO 投票权重怎样计算，少量持仓能投票吗？**

投票权重等于持有人的 vRAVE 余额；任何持仓数量都可以投票，区别只在权重大小。

**Q：RaveDAO 提案达到什么票数才通过？**

赞成票占总票数的 50% 以上时，提案通过。

**Q：持有人必须投票吗，Agent 会代投吗？**

投票是权利而非义务，不投票不影响固定奖励累积；投票由持有人自己完成，Agent 不代替持有人投票。

**Q：固定 $RAVE 奖励怎样计算和领取？**

RaveDAO 提供 6% 固定年化奖励，以 $RAVE 计价，并按 vRAVE 持有数量乘以持有时长累积。奖励在 Redeem 时与存入的 $RAVE 一并发放，不能单独 Claim；统一结算可保持计算口径一致并避免频繁的小额发放。

**Q：在哪里确认 Mint／Redeem 费用、投票入口和投票截止时间？**

Mint fee 和 Redeem fee 的实际费率在当前 Agent 页面确认前显示；当前投票入口以该 Agent 页面或 typed context 为准；每个提案的截止时间以对应提案页为准。固定知识库不写入这些动态值。

**Q：中途赎回奖励、锁定期、赎回等待时长和部分赎回规则是什么？**

中途赎回时已累积奖励如何处理、是否有锁定期、赎回等待时长以及能否部分赎回，尚未由 owner 明确。回答时必须说明尚未指定，并引导用户查看当前 Agent 页面或 typed context，不能推测。

**Q：钻石是什么，和固定奖励有什么关系？**

钻石是 Moss 生态积分，可用于未来空投权益或平台内消费。钻石由 Moss 提供，固定 $RAVE 奖励由 RaveDAO 提供，两者相互独立。

**Q：vRAVE 可以转让吗，如何退出？**

vRAVE 不可转让；唯一退出方式是 Redeem。

**Q：vRAVE 会像价格型资产一样涨跌吗，本金安全边界是什么？**

vRAVE 不是价格波动型资产，其支持资产是持有人存入的 $RAVE 加上已累积奖励。按该机制 Redeem 会返还存入的 $RAVE 与累积奖励，但 $RAVE 自身的市场价格波动不在机制保障范围内。

**Q：如何验证 Rave Governance Agent 的记录？**

该 Agent 的合约和交易记录都可在链上验证；具体合约地址和网络必须从当前 Agent 页面或 typed context 获取，固定知识库不硬编码。
