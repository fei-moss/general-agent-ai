## Security and Risk

**Q: Will Moss custody my private keys / funds? Is my money safe?**

Your private keys and funds always remain yours on-chain. Moss does not custody, does not sign on your behalf, and will not initiate any transaction for you. Every operation (Mint, Redeem, and so on) requires you to personally sign with your own wallet to take effect, so no one (including Moss) can transfer or freeze your funds without your signature, nor can they reverse or recover operations. In short, Moss Agent Marketplace uses a non-custodial design. Your funds are entirely under your own control, so please keep your wallet and seed phrase safe.

**Q: Could an agent cause a large loss due to an AI misjudgment? Is there any risk-control / stop-loss mechanism?**

Since Agent shares fluctuate with AUM, there is a risk of loss, potentially a large one. Please pay close attention to the specific share value shown on the Moss Agent detail page before performing operations such as Mint / Redeem.

**Q: If Moss has problems or shuts down, are my on-chain shares and assets still there? Can I redeem them myself?**

Because Moss does not custody private keys and does not sign on your behalf, your shares and the Agent contract state are governed by the chain.

Even if Moss Agent Marketplace is unavailable, the shares in your wallet will not automatically disappear, and the Agent contract remains on-chain. In theory, you can still interact with the contract directly via your wallet, a block explorer, a script, or another frontend. If the contract supports requestRedeem / redeem, you can try to redeem directly on-chain.

But whether you can redeem immediately and when the funds arrive depend on the Agent's on-chain state, for example:

- Whether the Agent has paused Redeem.

- Whether you have already submitted a redeem request.

- Whether the redemption has settled to claimable.

- Whether there is sufficient liquidity in the contract.

- Whether the funds are still deployed in external trades or protocols.

- Whether the current chain and contract are operating normally.

**Q: In which regions / countries can I not use it? Are there geographic restrictions?**

Mainland China is currently not available; other regions are available. Please confirm the specifics with Moss's official announcements.

**Q: I lost my wallet's seed phrase. Can Moss help me recover it?**

Moss Agent Marketplace uses a non-custodial design. Your funds are entirely under your own control, so please keep your wallet and seed phrase safe.

**Q: What specific risks are there in investing in AI Agents?**

Since Agent shares fluctuate with AUM, there is a risk of loss, potentially a large one. Please pay close attention to the specific share value shown on the Moss Agent detail page before performing operations such as Mint / Redeem.

**Q: Is there any difference in trustworthiness / risk between an agent self-built with the Tool and one deployed officially or via template?**

These are two different layers. The Tool provides the AI Agent's trading strategy, while template deployment provides the channel for on-chain fundraising.
