## 交易 Agent 角色与资金安全

下列机制适用于 Hyperliquid 交易类 Agent（Agent Type `hyperliquid`），属于稳定平台知识。具体费率、结算时间表等属于当前 Agent 动态配置，必须以当前 Agent context 或页面显示为准，不得用示例值补齐。

### Executor 与 Trading Wallet

**Q：Executor 和 Trading Wallet 是两个地址吗？**

可以是两个，默认是一个。

Executor 负责推动 Agent 运行，比如更新份额价格、在 Agent 不同平台交易账户之间划转资金。Trading Wallet 负责代表 Agent 下单。默认部署会让同一个地址兼任这两个角色，也可以分开配置。

**Q：为什么要求用没在 Hyperliquid 上用过的地址？**

这条要求针对的是 Trading Wallet。

Hyperliquid 不允许一个已经有自己账户的地址，再被登记为别人的交易钱包。如果你的 Trading Wallet 在 Hyperliquid/HyperCore 上交易过、收过款，登记就会失败。

默认配置下 Executor 兼任 Trading Wallet，所以这条要求会落到 Executor 地址上。如果你把两个角色分开，只有 Trading Wallet 需要满足，Executor 不受限制。

新建一个从未使用过的钱包地址相对来讲更安全且便捷。

**Q：这个地址在别的链上用过，有影响吗？**

没有。这条限制只看 Hyperliquid。地址在 HyperEVM、以太坊或任何其他链上的活动都不影响。

**Q：Trading Wallet 的授权会过期吗？**

会，有效期 90 天。

到期后它无法再代表 Agent 下单，交易会停止。重新授权一次即可恢复。建议在到期前主动检查，不要等交易停了才发现。

**Q：换了 Executor 之后，旧地址还有权限吗？**

在 Agent 合约上的权限可以关掉，但它在 Hyperliquid 上的交易钱包登记不会自动撤销。

如果旧地址的私钥可能已经泄露，在确认它已从 Agent 的交易钱包列表中移除之前，应当视为它仍能以 Agent 的名义下单。必要时先平掉风险仓位，并联系 Moss 技术团队协助确认。

**Q：Executor 每次划转多少钱，是怎么算出来的？**

划转不改变总量，只改变位置。钱从 HyperEVM 少了多少，就在 HyperCore 多了多少，持有人始终是 Agent 合约。所以划多划少不影响用户的资产总额，也不影响份额价格。

**Q：Executor 跑在发布者自己的电脑上，它会不会把钱转走？**

不会。Executor 能发起的划转，收款方固定是 Agent 合约在另一侧的账户，这个目的地写在合约里，改不了。Executor 只能决定划转多少钱、什么时候划转，但没有办法指定一个新地址。

### Owner

**Q：Owner 是做什么的？**

Owner 是 Agent 的创建者，拥有最高权限，但不参与日常运行。它的动作集中在创建 Agent 和后续修改配置，不参与任何一次结算或交易。

**Q：Owner 的私钥需要放到服务器上吗？**

不需要。

日常运行由 Executor 完成，Owner 只在少数几次配置操作时动用，私钥由用户自己保管，在自己的钱包里直接签名即可。

### Agent 合约与资金安全

**Q：Agent 合约地址在哪里看？**

详情页的 On-Chain Info 区块，Contract 那一行。

**Q：Contract 和 Share Token 显示的是同一个地址，是显示错误吗？**

不是。Agent 合约本身就是份额代币，两行指向同一个合约，这是 FAT Protocol 的核心设置。

**Q：Agent 完成 Tokenize 之后资金保存在哪里？**

在 Agent 合约名下。资金只会出现在两个位置：Agent 合约所在的 HyperEVM，以及 Agent 在 Hyperliquid 的账户。两个位置的持有主体都是 Agent 合约地址。

**Q：Mint 之后，我的钱到底存在哪里？**

在 Agent 合约名下。只会在两个位置：HyperEVM 上的合约里，或者 Agent 在 HyperCore 的交易账户里。两个位置用的都是 Agent 合约这一个地址。

**Q：我的资金由谁保管？**

始终由 Agent 合约持有。Owner、Executor、Trading Wallet 三个地址在任何阶段都不持有用户资金。

**Q：Executor 或 Trading Wallet 会不会转走我的钱？**

不会。Agent 合约只向 Executor 开放白名单内的受控函数，Trading Wallet 则只有签名权限。两者即使私钥泄露，攻击者能做的也仅限于提交错误的结算数据或以 Agent 名义下单，无法将资金转出。

**Q：这些地址的私钥泄露了，我的钱会被转走吗？**

不会。

Executor 只能调用 Agent 合约允许的少数几个操作，改不了配置，也无法把资金转到任意地址。Trading Wallet 只有下单的签名权限，订单和持仓全部归属 Agent 合约。

最坏情况是攻击者提交错误的结算数据，或者以 Agent 的名义乱下单造成交易亏损。资金本身转不出去。

**Q：交易亏损了，算不算钱被转走了？**

不算。亏损是交易的结果，钱通过订单簿成交流向了对手方，这是参与市场的正常后果，和「某个地址把资金转到自己名下」是两回事。发布者、Executor、Trading Wallet 都不会因为 Agent 亏损而拿到任何东西。

这套设计保证的是资金不被盗，不是资金不会亏。策略本身的盈亏风险始终存在。

**Q：我不小心往 Agent 合约地址转了一笔钱，能拿回来吗？**

不能。这笔钱会在下一次结算时被计入 Agent 的总资产，由全体份额持有人按份额分享。

### 结算、申购与赎回

**Q：为什么交易 Agent 的 Mint 提交后要等一段时间才发份额？**

对 Hyperliquid 交易 Agent，Mint 提交后要等一段时间，Executor 完成结算后才发放份额。份额数量取决于当期每份价格，价格由 Executor 的结算产生。未经结算，合约无法确定这笔资金应换取多少份额，交易 Agent 赎回同理。结算时间表属于当前 Agent 的配置，请以页面显示为准。

**Q：交易 Agent 多次申请赎回后，要不要每一笔单独领取？**

对 Hyperliquid 交易 Agent，多次赎回申请无需逐笔操作：所有已到期申请可一次领取，未到期申请留待后续结算。

**Q：Agent 长时间不结算怎么办？**

Hyperliquid 交易 Agent 长时间未结算时，资金仍由 Agent 合约持有；可在页面点击「退款」退回本金。

### 费用

**Q：Mint / Redeem 收取费用吗？费用是给谁的？还有其他费用吗？**

是否收取管理费、铸造费、赎回费或收益分成，以及具体费率，由当前 Agent 的费用配置决定，请以详情页和操作页面显示的当前费用为准，不要依赖任何固定示例数值。

除 Agent 费用外，你唯一需要支付的是 gas，也就是链上操作产生的网络手续费，这笔钱支付给区块链网络，不属于 Moss 或 Agent 的创建者。请每次操作之前确认页面显示的费用。
