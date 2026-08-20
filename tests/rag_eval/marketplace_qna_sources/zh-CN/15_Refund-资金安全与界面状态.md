## Consumer Agent Refund、资金安全与界面状态

本篇说明 Consumer Agent Refund、本金保管、余额显示和 Paused 界面状态。具体 Refund 费读取当前 Agent 页面；尚无答案的费用、额外收益和持有时长问题保持待产品 owner 输入。

**Q：哪些 Consumer Agent 份额可以 Refund？**

只有仍由用户持有、尚未兑换成码的份额符合 Consumer Agent Refund 条件。

**Q：已经兑换成 Consumer Agent 码的份额还能 Refund 吗？**

不能。换码会消耗份额，因此不能再把同一部分用于 Refund。

**Q：Consumer Agent Refund 能拿回多少？**

按未换码份额的当前兑换率扣除适用费用计算；这不是固定金额承诺。

**Q：状态流程：Consumer Agent Refund 提交后会依次出现哪些状态？**

Consumer Agent Refund 先进入 Pending，处理完成后变为 Claimable；随后执行 Consumer Refund claim，金额回到钱包。

**Q：Consumer Agent Refund 的申请总次数有上限吗？**

Consumer Agent Refund 稳定机制不设置累计次数上限；资格和请求状态以 Consumer Agent 页面为准。

**Q：Consumer Agent 里用户 Mint 的本金由谁保管，会进入品牌方钱包吗？**

在 Consumer Agent 中，本金由智能合约保管，绝不会进入 Consumer Agent 品牌方或 Moss 的自有钱包。

**Q：品牌方能动用用户本金吗？**

不能。品牌方不能把合约中的用户本金当作自己的资金转走。

**Q：Moss 能动用用户本金吗？**

不能。Moss 不能绕过合约取走用户本金。

**Q：品牌方或 Moss 能中途修改既有用户的条款吗？**

不能为已经进入的用户追溯修改合约固定条款；当前条款读取 Consumer Agent 页面或 typed context。

**Q：如果 Consumer Agent 品牌停止兑付权益会怎样？**

用户未兑换份额对应的本金仍在合约中；已发码能否履约仍取决于品牌兑现权益。

**Q：Agent 份额可以转给别人或在交易所卖出吗？**

份额是标准 ERC-20，具备链上流通条件。Moss 产品内的 Consumer 退出方式是 Refund；不能假定存在交易市场。

**Q：Consumer Agent 份额会因为市场炒作而涨价吗？**

不提供 APY、固定收益或升值承诺。Refund 价值按当前兑换率计算。

**Q：Consumer Agent 中，用户在 My Shares 看到的余额是否包含已换码部分？**

我的份额余额不含已换码部分；My Shares 只显示用户仍持有的份额。

**Q：Consumer Agent 的铸造活动和兑换码活动分别显示什么？**

分别显示 Mint 与换码记录；界面中的地址会脱敏展示。

**Q：为什么 Consumer Agent Refund 按钮是灰色的？**

常见原因是当前钱包尚未持有可操作份额，或者该 Agent 已暂停；应以页面当前状态为准。

**Q：Paused by owner 是什么意思？**

表示发行方暂停了新的 Mint 和 Refund 操作；已有份额仍归用户持有。

**Q：可以先拿 Consumer Agent 码，再把同一笔份额 Refund 吗？**

不可以；被消耗的份额不能恢复或再次 Refund。

**Q：这是不是固定金额保本？**

不是固定金额承诺。Refund 返回未换码份额的当前价值并扣除适用费用。
