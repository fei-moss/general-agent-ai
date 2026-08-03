## Governance Voting and Yield Details

The Governance product domain uses Agent Type `ballot`. The answers below are stable platform mechanics: voting power comes from the holdings snapshot taken at proposal creation, voting is an on-chain action that costs gas, and rewards are claimed together with redemption. The specific project, token, fixed APY value, and lock-up length are dynamic facts of the current Agent and must be read from current Agent context; never fill them with sample values.

### Voting and Snapshots

**Q: How is my voting power calculated?**

From a snapshot of your holdings taken when the proposal went live, not from what you hold at the moment you vote.

The proposal page shows the snapshot time, for example `Your voting power: 0 votes (snapshot 2026-07-20 11:33)`. Whatever you held at that moment is what you can vote with.

**Q: A proposal is already open. Can I mint now and vote on it?**

No. The snapshot locks in when the proposal is created, and any later change to your holdings has no effect on that proposal.

You can take part in proposals created after you hold shares.

**Q: The page shows 0 votes and says the snapshot recorded no voting power for my wallet. What does that mean?**

Your shares arrived after the snapshot.

This usually happens when the proposal went live before you minted, or when you minted but had not yet claimed your shares. Compare the snapshot time on the proposal page with when you received your shares.

**Q: Can someone buy a large number of shares at the last minute and sway the outcome?**

No. Voting power comes from the snapshot taken at proposal creation, so shares acquired after a proposal goes live carry no voting power.

**Q: What voting options does a proposal have?**

For, Against, and Abstain. The page shows live counts and percentages for all three, along with total votes and the number of participating addresses.

Past proposals appear under Proposal History.

**Q: Does voting cost gas?**

Yes. Voting happens on chain and carries the standard network fee for whichever network the Agent runs on.

### Rewards and Redemption

**Q: Where do returns on a Governance Agent come from?**

Shares accrue at a fixed APY, and the project pays the rewards in its own token. The exact APY value and token come from current Agent context.

**Q: When do the rewards arrive?**

You claim them together with your redemption. Nothing pays out while you hold.

**Q: Is redemption the same as on a Trading Agent?**

The flow matches. Submit Request Redeem and it enters the processing queue. Some projects set a lock-up period. Once it ends, track the status under View history and claim once it becomes redeemable.

**Q: Does the share price of a Governance Agent fluctuate?**

Not with trading performance. It accrues at a fixed APY, which differs from a Trading Agent, where the share price follows the Agent's managed assets.

### For Projects

**Q: We want to launch a Governance Agent. How do we apply?**

Moss currently deploys Governance Agents for projects on a custom basis rather than through self-service. Contact us in our Telegram or Discord community:

- Telegram: https://t.me/mossai_official
- Discord: https://discord.com/invite/SdyYFbePUK

**Q: What can a Governance Agent do for us?**

It turns token holders into participants you can reach and who can vote. Holders mint their tokens into shares, hold at a fixed APY, receive your project's token rewards, and vote on on-chain proposals.
