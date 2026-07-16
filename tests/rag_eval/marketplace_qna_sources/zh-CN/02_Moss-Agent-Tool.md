## 二、Moss Agent Tool

**Q: 旧版 agent 的历史数据（交易记录、收益、运行时长）会完整保留吗？**

会，完整保留。 历史数据不做任何调整，会完整迁移到新页面中。

**Q: 我可以先用 Tool 自己跑一段时间验证策略，再决定要不要 Tokenize、上架到 Marketplace 吗？**

完全可以。 Tokenize 的时间点完全由你自己决定，平台侧没有任何额外限制。你可以先让 Agent 跑一段、观察策略表现，觉得合适了再 Tokenize 上架。

**Q: 把一个已有的 Agent Tool 创建的 Agent Tokenize 上架，会改变它原来的策略/ 表现/ 历史吗？**

不会。Tokenize 上架和交易策略是两件互不影响的事，是否 Tokenize 上架，不会改动 Agent 本身的交易策略。它原有的表现和历史数据也保持不变。

**Q: 用自然语言建的 agent，要满足什么条件才能 Tokenize 上架到 Marketplace（比如跑够多久、要有真实业绩）？**

没有任何前置条件。 是否 Tokenize、什么时候 Tokenize，完全由你自己决定，平台不设跑满多久、必须有多少业绩之类的门槛。

**Q: 用 Agent Tool 创建 Agent 有限制吗？一个人最多能创建多少个？**

一个账号最多创建 6 个 Agent，且不分 Agent 类型，六个名额通用。

**Q: 只有实盘 agent 才能上 Marketplace/ 才能被别人 mint 吗？模拟盘的能展示吗？**

只有实盘 Agent 可以上架 Marketplace，回测（模拟盘）不能上架。 也就是说，能被别人 Mint 的都是真实在跑的实盘 Agent。

**Q: 从「用 AI 建 agent」→「Tokenize 上架」→「别人 mint 份额」，完整链路走一遍是怎样的？入口怎么衔接？**

整条链路分三步：（之后这里需要补上对应的入口 url \+ 对应步骤的 gitbook 教程）

1. 建 Agent：用 Moss Agent Tool 自托管模式（或其他 AI 交易平台）搭建出交易 Agent，并为它生成 Hyperliquid 交易地址。

2. Tokenize 上架：在 Moss 协议市场，通过 Tokenize Agent 的配置流程，把 Agent 发布上架、开放 Mint。

3. 用户参与：Agent 在 Marketplace 上架完成后，其他用户就能在 Marketplace 查看、Mint、Redeem 这个 Agent。
