## Launching and Fundraising

**Q: What exactly does it mean to launch an agent and raise funds on-chain? Whose money am I raising, and what is it used for?**

The creator publishes an AI Agent with trading capability and strategy to the market, and users invest in it by minting shares. The raised funds are used for the Agent's real trading, and the returns the Agent earns are distributed to holders through Mint / Redeem price changes.

**Q: How does a creator make money? What are Management Fee and Profit Share, how much can they be set to, and when do they arrive?**

A creator's income mainly comes from the Agent's fee mechanism, currently in two categories:

Management Fee (a management fee, effectively the Mint / Redeem Fee)

- When users Mint to enter, a Mint Fee is charged per configuration; when users Redeem to exit, a Redeem Fee is charged per configuration.

- How much the fee rate can be set to depends on the Agent configuration at creation and on-chain contract limits. It is not necessarily the same across Agents.

Profit Share

- After the Agent actually earns money through the executor, the returns enter the contract, and the creator can share a portion of the returns per the contract terms.

- Whether it is supported, the ratio, and when it settles all depend on the contract rules set when the Agent is configured.

Settlement:

- Fees and shares such as the Mint Fee, Redeem Fee, and the returns from share unit price changes after the Agent profits are not paid out manually by the platform. They are determined by on-chain contracts and settlement logic.

- When exactly they can be claimed, whether settlement is automatic, and whether the creator must actively claim can be checked against the Agent's on-chain contract implementation and the Agent management page.

**Q: Do I need to put up my own principal to launch an agent, or does it all rely on money others mint in?**

You do not necessarily need to provide all the principal yourself. The Agent's main funds come from the Accept Token that investors mint in, so the creator does not need to fill the principal themselves.

However, as a creator, you at least need to bear these basic costs:

- Gas: The fees for deploying the contract and on-chain operations.

- Configuration costs: Filling in information, configuring parameters, and binding the executor / trading wallet when creating the Agent.

Two additional notes:

- If no one mints, the Agent will have very little manageable capital, and the strategy may not run properly or only at limited scale.

- Some templates may require initial capital or a minimum launch size in the future, subject to template rules.

In short, you do not have to put up all the principal yourself. The main funds come from investor minting, but you must bear the basic deployment and configuration costs yourself, and whether initial capital is needed depends on the specific template requirements.

**Q: Can I, as the creator, move the funds others mint in?**

No. These funds enter the code-custodied Agent contract, not the creator's personal wallet, so they cannot be transferred freely like a balance. The roles during Agent operation are:

- Investor: Mints funds and receives shares.

- Agent contract: Handles share accounting, Mint / Redeem, NAV calculation, and fund constraints.

- Creator / Owner: Manages the Agent (configuring the executor, pausing operations, maintenance, and so on).

- Executor: Executes the actual trading or strategy.

Therefore, the creator's role is essentially an "administrator" and cannot dispose of funds at will. Whether funds can be used for trading, transferred to external protocols, used to withdraw fees, or paused all depend on the contract rules and executor permissions.

**Q: Will my strategy / prompt be made public? Could someone copy it?**

It is not fully disclosed. The page only shows the public description you fill in yourself and the trade logs / activity records you choose to report. You control the transparency:

- Disclose no strategy details at all: Investors can only see on-chain data, so trust cost is higher.

- Report trade logs / strategy explanations moderately: Investors understand more easily what the Agent is doing, so trust is higher.

- Disclose the full prompt / core strategy: Maximum transparency, but it may also be copied.

We suggest striking a balance: you can disclose the strategy direction, risk-control logic, trade records, and review notes; do not disclose private keys, API keys, the full core prompt, or full system details. Reporting logs is not mandatory, but it can help you build investor trust.

**Q: If the agent performs poorly after listing, can I delist / stop / change the strategy? What is the impact on holders?**

The creator can modify the Agent's trading strategy at any time, which is essentially unrelated to the protocol market platform. Currently, Moss Agent Marketplace does not support delisting an Agent.

**Q: Can I still modify the template / chain after selecting them?**

Yes. Before the Agent is fully created, you can reselect or modify them.

**Q: After Tokenize fundraising, can I still change the strategy / adjust parameters anytime like in the Tool? What is the impact on holders who have already minted?**

You can modify the Agent's trading strategy at any time, and this essentially does not affect the Agent listed on Moss Agent Marketplace.

**Q: After listing for fundraising, how much control do I, the creator, still have over the funds? What can and cannot be moved?**

The funds others mint in enter the Agent contract or a contract-controlled fund path, not the creator's personal wallet, and cannot be transferred freely. The specific use of funds and the creator's permissions depend on the Agent contract and executor permission design.
