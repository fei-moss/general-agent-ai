## Consumer Agent 与 Mint

本篇 `consumer` 文档只说明首次上手与 Mint 机制。Agent 专属的 Mint 设置必须读取当前 Agent 页面或 typed context。

**Q：Consumer / Redemption Agent 是做什么的？**

Consumer Agent 让用户 Mint 标准份额以兑换品牌权益；未换码份额也可选择 Consumer Agent Refund。

**Q：通过这里获得品牌权益，和直接向品牌方购买有什么区别？**

直接购买会立即取得权益；Consumer Agent 先让用户获得份额，再选择兑换权益或 Refund。本金托管见《Refund、资金安全与界面状态》。

**Q：Consumer Agent 是投资产品吗？有 APY 吗？**

不是投资产品，也没有 APY 或年化收益承诺。用途是兑换品牌权益。

**Q：Mint 得到的份额是 NFT 吗？**

不是。Consumer Agent 份额是标准 ERC-20 代币，不是 NFT，并且可以分割。

**Q：份额本身值什么？**

价值来自可兑换的权益，以及未使用时的当前 Refund 价值。它不代表品牌公司的股权、估值或升值预期。

**Q：第一次使用时，从连接钱包到 My Shares 的上手路径是什么？**

按 `连接钱包 -> Mint -> Claimable -> My Shares` 操作：提交 Mint，状态变为 Claimable 后领取，再到 My Shares 确认份额。

**Q：第一次 Consumer Agent Mint 完成后，怎样领取并找到份额？**

Mint 处理完成后，份额变为 Claimable；领取后到 My Shares 确认 Consumer 份额。

**Q：Mint 会直接给我兑换码吗？**

不会。Mint 先产生 Agent 份额；生成兑换码是之后由用户主动执行的操作，见《兑换码生成与使用》。

**Q：最少要 Mint 多少？**

最低 Mint 金额不是平台统一常量，必须读取当前 Agent 页面或 typed context。

**Q：Mint 时会收多少费用？**

页面会在确认前显示本次 Mint 的适用费用；固定知识库不保存费率。

**Q：Mint 可以使用哪些代币？**

每个 Consumer Agent 只接受部署时设定的一种结算代币。具体代币读取当前 Agent 页面或 typed context。

**Q：品牌方或 Moss 能在之后更换结算代币吗？**

单一结算代币在 Agent 部署时固定；已有 Agent 不能按需切换成另一种代币。
