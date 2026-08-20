## Launching and Tokenizing

**Q: What exactly does it mean to launch an agent and Tokenize it on-chain? What do Minters bring in, and what are the tokens used for?**

The creator publishes an AI Agent with trading capability and strategy to the market, and users back it by minting shares. The pooled tokens are used for the Agent's real trading, and the returns the Agent earns are distributed to holders through Mint / Redeem price changes.

**Q: How does a creator make money? What are Management Fee and Profit Share, how much can they be set to, and when do they arrive?**

A creator's income mainly comes from the Agent's fee mechanism, currently in two categories:

- Management Fee: the configured Mint Fee and Redeem Fee.
- Profit Share: a contract-defined portion of actual trading profit when that feature is supported.

Rates, contract limits, support, and payout method are Agent-specific. The Agent management page and on-chain rules state the applicable values and whether the creator must claim them.

**Q: Do I need to put up my own principal to Tokenize an agent, or does it all come from what others mint in?**

Other Minters supply the Agent's main capital, so the creator does not need to fill the pool. The creator still pays deployment gas and configuration costs. Without Minter participation the strategy may run only at limited scale, and a template may require initial tokens or a minimum launch size under its own rules.

**Q: Can I, as the creator, move the tokens others mint in?**

No. These tokens enter the code-custodied Agent contract, not the creator's personal wallet, so they cannot be transferred freely like a balance. The roles during Agent operation are:

- Minter: Mints tokens and receives shares.

- Agent contract: Handles share accounting, Mint / Redeem, NAV calculation, and pool constraints.

- Creator / Owner: Manages the Agent (configuring the executor, pausing operations, maintenance, and so on).

- Executor: Executes the actual trading or strategy.

Therefore, the creator's role is essentially an "administrator" and cannot dispose of pooled tokens at will. Whether tokens can be used for trading, transferred to external protocols, used to withdraw fees, or paused all depend on the contract rules and executor permissions.

**Q: Will my strategy / prompt be made public? Could someone copy it?**

It is not fully disclosed. The page only shows the public description you fill in yourself and the trade logs / activity records you choose to report. You control the transparency:

- Disclose no strategy details at all: Minters can only see on-chain data, so trust cost is higher.

- Report trade logs / strategy explanations moderately: Minters understand more easily what the Agent is doing, so trust is higher.

- Disclose the full prompt / core strategy: Maximum transparency, but it may also be copied.

We suggest striking a balance: you can disclose the strategy direction, risk-control logic, trade records, and review notes; do not disclose private keys, API keys, the full core prompt, or full system details. Reporting logs is not mandatory, but it can help you build Minter trust.

**Q: If the agent performs poorly after listing, can I delist / stop / change the strategy? What is the impact on holders?**

The creator can modify the Agent's trading strategy at any time, which is essentially unrelated to the protocol market platform. Currently, Moss Agent Marketplace does not support delisting an Agent.

**Q: Can I still modify the template / chain after selecting them?**

Selecting a template or blockchain does not lock it immediately. Yes. Before the Agent is fully created, you can reselect or modify them. Creation completion is the immutability boundary for both the selected template and the selected chain.

**Q: After tokenization and fundraising, are strategy and parameters no longer freely adjustable, and what is the effect on holders who already Minted?**

The post-tokenization strategy boundary is unchanged. You can modify the Agent's trading strategy at any time, and this essentially does not affect the Agent listed on Moss Agent Marketplace. This holder-impact statement does not turn every contract parameter into an editable strategy setting.

**Q: After Tokenizing, how much control do I, the creator, still have over the pooled tokens? What can and cannot be moved?**

The tokens others mint in enter the Agent contract or a contract-controlled path, not the creator's personal wallet, and cannot be transferred freely. How those tokens are used and what permissions the creator holds depend on the Agent contract and executor permission design.
