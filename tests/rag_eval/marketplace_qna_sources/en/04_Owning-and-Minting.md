## Owning and Minting

**Q: What is the minimum cost to mint one agent share? Is there a threshold?**

There is no unified threshold. It is defined by each Agent's creator. The exact price is shown on the Agent's detail page.

**Q: After minting, how are my returns calculated and reflected? Is it share price appreciation or separately distributed returns?**

Minting gives you a proportional Agent share that remains in your own wallet as an on-chain token. The pooled Accept Tokens enter the Agent contract and may be used by the executor for the Agent's strategy; the contract governs share accounting, custody, Mint, and Redeem, so the creator cannot freely dispose of the pooled principal. Returns are reflected in the appreciation of the shares you hold, not distributed separately. The number of shares stays the same, but each share can be redeemed for more, and that increase is your return.

**Q: Do I need to claim my returns separately? Is there a Claim Yield mechanism?**

No separate claiming, and no Claim Yield mechanism. Returns are reflected in share price appreciation, and settlement completes the moment you Redeem.

**Q: What does "returns reflected in exchangeRate appreciation" mean? How do I know how much I have earned?**

A rising exchange rate means each unit of shares you hold can be redeemed for more. You can calculate your return with this formula:

> Return = (share unit price at Redeem − share unit price at Mint) × quantity held

**Q: When will my funds become accessible, and what is the typical duration for Redeem? Is there a lock-up period?**

There may be a lock-up period, defined by the Agent's creator. For cases with a lock-up, submit the Redeem request, and once the lock-up period ends, the funds will arrive automatically.

**Q: Which cryptocurrency is accepted for Mint payments, and must it be ETH? What does Accept Token mean?**

Not only ETH. Moss Agent Market supports multiple chains, and the payment currency (the Accept Token) depends on the Agent's detail page.

**Q: If the agent loses money, will my principal be lost? Could it be wiped out?**

Holders bear asset fluctuations proportionally through the share value: when the Agent gains, each share can rise; when it loses, each share falls. The creator does not cover holder losses or guarantee returns. If the current Agent configuration includes Profit Share, it accrues from profits according to that contract; do not assume Profit Share exists when the Agent does not disclose it. Before participating, please understand that Agent shares are not a principal-protected product and review the on-chain record and your own risk tolerance.

**Q: If the Supply Cap sells out (Sold Out on Marketplace), can I still participate? Will there be more issuance later?**

Once the current Supply Cap sells out, the Mint button is greyed out and shows Sold Out. Since there is currently no additional issuance mechanism, no new shares can be minted after it sells out. If the Agent's shares circulate on the secondary market, you can buy directly there. [insert secondary market link here]

**Q: Will my minted shares rise and fall in price like a coin? Does it follow performance or market sentiment?**

Share value fluctuates with Agent-Managed Assets (AMA) and is directly tied to the Agent's trading performance. When the Agent trades profitably, share value rises. When it loses, share value falls.

**Q: What is the difference between minting to earn returns and trading shares on a DEX? Which should I choose?**

You can participate in both:

- Mint: Original Agent shares, with unit price determined by each Agent's performance.

- Secondary market: Buying and selling shares on the open secondary market, with prices determined by the market.

**Q: What is the difference between Minting agent shares and copy trading directly?**

Copy trading copies another trader's actions into a separate account and can introduce signal lag, missed fills, or a follower execution gap. Holding Agent shares instead gives you a proportional claim on the pooled Agent assets, so the Agent's asset change is reflected directly in share value without a separate follower fill. The Agent record and share accounting are verifiable on-chain, and you do not need to install a copy-trading skill locally or keep a local environment running 24/7. Holders exit through a DEX sale when available or through Redeem; the current Agent's lock, settlement, and claim configuration determines when Redeem completes, so exit must not be described as immediate when a lock is configured.

**Q: If an agent performs very well, will my minted shares carry a premium? Where does the premium come from?**

Share value fluctuates with Agent-Managed Assets (AMA). When the Agent trades profitably, share value rises, and that is the source of the value increase. When it loses, it falls.

**Q: Can Mint prevent MEV?**

Yes, MEV can be prevented.

First, MEV refers to how, in many on-chain transactions, bots can place orders ahead of you or deliberately push the price up before selling to you (common tactics known as "frontrunning" and "sandwiching"), making you pay more. Moss's Mint uses a design that largely rules out such operations.

Moss's approach is "queue first, then price uniformly":

1. When you click Mint, it does not settle at the live price on the spot. Instead, it submits a request that queues into the next settlement round.

2. At settlement, the system calculates one share price for that round, and everyone in that batch settles at the same price.

**Q: Why does this prevent MEV?**

- The price is calculated uniformly when the batch settles, not the live price at the instant you click, so bots cannot jump ahead of you or push the price up on the fly.

- When the price is calculated, tokens still queuing and not yet settled are excluded. Even if a bot squeezes into the queue, it cannot affect this batch's price, cannot change your settlement price, and cannot take your shares.

**Q: Can Mint fail? If it fails, will Mint still charge a fee?**

Mint can fail, for example if approval is rejected, but a failure does not incur any extra fee.

**Q: What is the difference between Supply Cap and Total Supply?**

Supply Cap is a fixed number agreed upon when the Agent is listed on the Marketplace, while Total Supply is the total amount of Agent shares users have minted, a variable number.

- Supply Cap: The maximum number of shares the Agent can issue.

- Total Supply: The total number of shares the Agent has actually issued so far.
