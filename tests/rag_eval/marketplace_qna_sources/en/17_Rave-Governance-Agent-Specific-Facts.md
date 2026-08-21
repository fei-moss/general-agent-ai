## Rave Governance Agent Specific Facts

This page contains only Rave-specific facts; the shared product framing, custody, Mint/Redeem flow, existing-holder terms, and post-redemption voting-power rules live only in documents 04, 10, 11, and 12.

**Q: What does the Rave Governance Agent do?**

It Mints $RAVE into vRAVE shares. Holders can participate in RaveDAO governance while accruing a fixed reward denominated in $RAVE.

**Q: What is vRAVE?**

vRAVE is this Agent's share token, backed by the $RAVE deposited by holders. Holding vRAVE represents the corresponding RaveDAO governance eligibility and accruing $RAVE rewards.

**Q: How does holding $RAVE directly differ from holding vRAVE?**

Holding $RAVE directly does not accrue rewards through this Agent or participate in its governance. Minting vRAVE places the funds into the contract mechanism and adds governance eligibility plus fixed-reward accrual.

**Q: Who issues the Rave Governance Agent?**

It is issued by Moss Agent Marketplace in partnership with RaveDAO.

**Q: What are the Rave Governance Agent's Mint minimum, account cap, and repeat-Mint rules?**

There is no minimum Mint amount. Each account is capped at 50,000 $RAVE to reduce governance-weight concentration in a single address. A holder may Mint multiple times as long as the cumulative amount stays within that cap.

**Q: Can I Mint vRAVE with a token other than $RAVE?**

No. This Agent accepts only $RAVE, and that accepted token is fixed by contract.

**Q: When does voting eligibility begin after I Mint?**

Voting eligibility begins only after settlement completes and the holder Claims the vRAVE into their holdings.

**Q: How is RaveDAO voting weight calculated, and can a small holder vote?**

Voting weight equals the holder's vRAVE balance. Any holding size can vote; only the weight differs.

**Q: What vote total makes a RaveDAO proposal pass?**

A proposal passes when votes in favor are more than 50% of total votes.

**Q: Must holders vote, and can the Agent vote for them?**

Voting is a right, not an obligation, and abstaining does not affect fixed-reward accrual. Holders cast their own votes; the Agent never votes on a holder's behalf.

**Q: How is the fixed $RAVE reward calculated and paid?**

RaveDAO provides a 6% fixed APY denominated in $RAVE, accruing from vRAVE holding amount multiplied by holding duration. At Redeem it is paid together with the deposited $RAVE and cannot be Claimed separately; unified settlement keeps one calculation basis and avoids frequent micro-payouts.

**Q: Where do I confirm Mint/Redeem fees, the voting entry point, and a proposal deadline?**

The current Agent page shows the actual Mint fee and Redeem fee rates before confirmation. Use the current Agent page or typed context for the voting entry point, and the applicable proposal page for its deadline. The fixed corpus stores none of these dynamic values.

**Q: What are the early-redemption reward, lock period, redemption wait time, and partial-redemption rules?**

The treatment of accrued rewards on early redemption, whether a lock period applies, the redemption wait time, and whether partial redemption is supported are not yet specified by the owner. State that they are unspecified and direct the user to the current Agent page or typed context; never infer them.

**Q: What are Diamonds, and how do they relate to the fixed reward?**

Diamonds are Moss-ecosystem points for future airdrop rights or in-platform spending. Moss provides Diamonds, while RaveDAO provides the fixed $RAVE reward; the two are independent.

**Q: Is vRAVE transferable, and how can a holder exit?**

vRAVE is non-transferable; the only exit is Redeem.

**Q: Does vRAVE fluctuate like a price asset, and what is the principal-safety boundary?**

vRAVE is not a price-volatile asset; it is backed by the holder's deposited $RAVE plus accrued rewards. Under this mechanism, Redeem returns the deposited $RAVE and accrued rewards, but the market-price volatility of $RAVE itself is outside the mechanism's guarantee.

**Q: How can I verify the Rave Governance Agent's records?**

The Agent contract and its transactions can be verified onchain. Obtain the actual contract address and network from the current Agent page or typed context; the fixed corpus hardcodes neither.
