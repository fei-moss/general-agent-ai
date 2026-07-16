## What Is Moss Agent Marketplace

**Q: How are Moss Agent Marketplace and FAT Protocol related? Do I need to understand FAT to use Moss?**

No, you can start directly with Moss.

Moss Agent Marketplace is an Agent platform built on FAT Protocol and is part of the FAT Protocol ecosystem. For most users, Moss is simply your entry point to FAT Protocol. You can just use Moss normally without studying the underlying protocol first.

If you want to learn more about FAT Protocol, see: [insert FAT Protocol Gitbook link here]

**Q: When I own a share of an agent on Moss, what exactly do I own? Equity? A token? Profit rights?**

You own an Agent share, represented as a token. Holding this share means you participate in the Agent proportionally and share its on-chain performance in proportion to your shares.

Taking a Hyperliquid Agent as an example, here is how it works:

- Mint: You mint shares and receive a proportional share of the Agent.

- Earnings enter the pool: The money the Agent makes from trading goes into the Agent's assets, pushing up the unit price of each share.

- Redeem: Once the share price rises, you can redeem at a higher price, and the difference is your gain.

**Q: What do the Marketplace, Tokenize Agent, and Portfolio sections each do? Where should I start?**

The three sections map to "pick an Agent, publish an Agent, manage assets," depending on which type of user you are.

- Marketplace | For users who want to participate in Agents and share their performance. A market for acquiring Agent shares. Here you pick Agents you are interested in, buy shares via Mint, redeem to cash out via Redeem, and share the Agent's share performance. Most users start here.

- Tokenize Agent (Publish an Agent) | For users who want to publish their own Agent and let others back it on-chain. The flow for listing your own Agent on the Marketplace. Once listed, users can view, Mint, and Redeem it, and they can back your Agent directly on-chain.

- Portfolio (Personal Center) | For everyone who has participated. Your personal asset page, viewable after connecting your wallet. Here you can see your wallet balance, the Agent shares you hold, the returns you have earned, and more.

**Q: What does "on-chain Agent" mean? Does the AI run directly on-chain?**

No. The AI does not run on-chain. The chain only handles the asset standard:

- Agent (built by the creator): The actual AI trading service is built and maintained by the creator using Moss Agent Tool. It is not part of the protocol itself.

- FAT Protocol (on-chain): Handles only the asset standard, that is, the minting, redemption, and accounting of shares. It has no AI trading capability.

So an "on-chain Agent" refers to an Agent built on FAT Protocol, whose trading strategy is implemented via Moss Agent Tool, which can pool tokens on-chain, receive Minters' Accept Tokens, and use those pooled tokens to trade on Hyperliquid.

**Q: Are "building an agent with AI" and "an agent whose shares can be minted" the same thing at different stages, or two different things?**

They are the same Agent at different stages. The difference is whether it has gone through the "publish to Marketplace" step after being built.

- Build the Agent: The creator builds an Agent (which handles the AI trading strategy) using Moss Agent Tool or another Agent creation tool.

- Choose whether to publish to the Agent Marketplace (that is, Tokenize):

    - Publish: The Agent becomes an Agent whose shares can be minted. It goes live on Marketplace, and users can Mint, Redeem, and share in its returns.

    - Do not publish: The Agent can still be listed to the Agent List, keeping its strategy for copy trading but without opening for Minting on Marketplace, so there are no shares to Mint.

All Agents come from the same toolset. "Shares can be minted" is simply the form it takes after one extra step: publishing to the Marketplace.
