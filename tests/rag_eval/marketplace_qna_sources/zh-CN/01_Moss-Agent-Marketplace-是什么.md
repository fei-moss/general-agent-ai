## 一、Moss Agent Marketplace 是什么

**Q: Moss Agent Marketplace 、FAT Protocol 是什么关系？我用 Moss 需要了解 FAT 吗？**

**不需要，你可以直接从 Moss 上手。**

Moss Agent Marketplace 是基于 FAT Protocol 搭建的 Agent 平台，属于 FAT Protocol 生态的一部分。对绝大多数用户来说，Moss 就是你接触 FAT Protocol 的入口，你可以 Moss 上正常使用即可，不必先去研究底层协议。
如果你想要了解更多 FAT Protocol 的细节，可以参考：\[这里可以给出 FAT Protocol 在 Gitbook 里的 link\]

**Q: 我在 Moss 上拥有一个 agent 的份额，到底拥有的是什么？是股权？是代币？是收益权？**

拥有的是以代币形式的 Agent 投资份额。持有份额，相当于按比例参与这个 Agent 的链上运作，并按份额比例分享它的链上表现。

以 Hyperliquid Agent 为例，它帮你赚钱的流程是这样的：

- Mint：你 Mint 份额，获得了 Agent 一定比例投资份额。

- 收益进资金池：Agent 通过交易赚到的钱，会计入该 Agent 的资产，从而推高每份份额的单价。

- Redeem：份额单价涨上去之后，你就能以更高的价格赎回，赚到的差价就是你的收益。

**Q: Marketplace/ Tokenize Agent / Portfolio 三个板块分别是干嘛的，我该从哪个开始？**

**三个板块对应"挑 Agent、发 Agent、资产管理"三件事，看你是哪类用户。**

- **Marketplace（Launchpad 市场）｜面向想投资 Agent 赚收益的用户**
获取 Agent 份额的市场。你在这里挑选感兴趣的 Agent，通过 Mint 买入份额、Redeem 赎回变现，分享 Agent 的份额收益。

- **Tokenize Agent（发布 Agent）｜面向想发布自己的 Agent、募集用户投资的用户**
把你自己的 Agent 上架到 Marketplace 的操作流程。上架后用户就能查看、Mint 和 Redeem，你获得用户的链上资金支持。

- **Portfolio（个人中心）｜面向所有已参与的用户**
你的个人资产页，需连接钱包后查看。这里能看到你的钱包余额、已持有的 Agent 份额、已获得的收益等。

**Q: 链上 Agent 啥意思？AI 直接跑链上吗？**

不是。AI 不在链上跑，链上只负责资产标准这部分：

- Agent（创建者自建）：真正的 AI 交易服务由创建者自己借助 Moss Agent Tool 搭建和维护，不属于协议本身。

- FAT Protocol（链上）：只负责资产标准，也就是份额的铸造、赎回、记账，不涉及任何 AI 交易能力。

所以"链上 Agent"指的是：基于 FAT Protocol 构建的 Agent，其交易策略设置借由 Moss Agent Tool 实现，可以在链上汇总资金、吸引更多用户参与，再拿这笔资金去 Hyperliquid 上交易。

**Q: 「用 AI 建 agent」和「一个可被 mint 份额的 agent」，在产品里是同一个东西的不同阶段，还是两种东西？**

是同一个 Agent 的不同阶段。 区别在于建好之后有没有走**「发布到 Marketplace」**这一步。

- 建 Agent：创建者用 Moss Agent Tool 或其他 Agent 创建工具搭建出一个 Agent（负责 AI 交易策略）。

- 选择是否发布到 Agent Marketplace（也就是 Tokenize）：

    - 发布：Agent 变成可被 Mint 份额的 Agent，可以在链上汇集资金，用户能 Mint、Redeem，参与它的收益。

    - 不发布：Agent 仍然可以 list 到 Agent List，保存自己的策略可以用来跟单但不公开汇集资金，也就没有份额可以 Mint。

所有 Agent 都出自同一套工具，"可被 Mint 份额"只是它多走了一步、发布到 Marketplace 之后的形态。
