## Governance Agent (Ballot)

Governance is the product-domain label; Marketplace, Chat, and backend contracts use Agent Type `ballot`. The mechanisms below are stable platform knowledge. Project identity, tokens, rates, denominations, page locations, and concrete governance rules are dynamic facts that must come from the current Agent context. Missing data must be reported as unavailable, never filled with demo values.

**Q: What does a Governance Agent do?**

A Governance Agent combines Agent shares, fixed-yield accrual, airdrops claimed at Redeem, governance voting, and project updates in one entry point. The project, tokens, fixed APY, and governance parameters must come from the current Agent context.

**Q: What do I get for Minting a Governance Agent share?**

The platform mechanism has four benefit categories: yield accruing at the current Agent's fixed APY, airdrops accumulated while holding and claimed at Redeem, governance participation under snapshot rules, and project updates. The share is a standard onchain token in the holder's wallet; concrete values and rules come from the current Agent context.

**Q: How is holding through a Governance Agent different from holding the project token directly?**

Holding the project token directly mainly preserves exposure to that token. Holding Governance Agent shares can add contract-governed fixed yield, airdrop accrual, a governance entry point, and project updates. Whether and how a specific Agent provides them must follow its current contract and Agent context.

**Q: How does the fixed APY accrue?**

Fixed yield accrues from share size, holding duration, and the fixed APY disclosed for the current Agent. The exact rate, start time, calculation basis, and display location are current-Agent dynamic facts and must be read from Agent context or the page.

**Q: Where do fixed yield and airdrops come from, and are they sustainable?**

Fixed yield and airdrops are provided and honored by the relevant project under that Agent's disclosed rules. A contract can enforce amounts, schedules, and claim conditions, but it cannot prove that the project's funding source is sustainable forever. Check both current Agent context and the project's public materials.

**Q: When and how are airdrops claimed?**

The stable Governance Agent mechanism is that airdrops accrue while shares are held and are claimed when the current Agent's Redeem conditions are met. The exact steps, payout assets, and accrual display location are dynamic facts from current Agent context and must not be guessed.

**Q: How are proposals created and who can propose?**

Proposal rights are defined by the current Agent's governance configuration. A threshold holder or the project may be allowed to propose. The exact threshold, entry point, and active proposals must come from current Agent context or the proposal page.

**Q: How is voting power calculated?**

Voting eligibility and weight are based on share holdings at the proposal snapshot. The exact conversion rule belongs to the current Agent's governance configuration and must come from current Agent context; not every Agent may use one share equals one vote.

**Q: What is a governance snapshot and when is it taken?**

A snapshot records share holdings at a specific point and fixes eligibility and weight for that proposal. Its exact block or time is proposal-specific and should be shown in current Agent context or on the proposal page. Later balance changes must not be silently applied to that vote.

**Q: How do I vote, and can I change my vote?**

The user selects a position on the proposal page and signs under the product flow; the vote record is verifiable. Whether a vote can be changed, whether gas is required, and the exact cost are dynamic proposal or Agent rules that must come from current Agent context.

**Q: Are there extra rewards for governance participation?**

Extra voting rewards are not a platform-wide constant. They must come from current Agent context. When no reward configuration is returned, the answer must say the current data does not provide it rather than promising a reward.

**Q: Who executes a passed proposal?**

Execution depends on the current Agent's governance rules. Contract-executable actions may run onchain, while offchain actions may be handled by the project. The exact executor, status, and progress must come from current Agent context or the proposal page.

**Q: Can I exit, and does Redeem lose accrued rewards?**

Redeem availability, locks, and early-redemption effects are defined by the current Agent's redemption rules. Once those rules are met, the returned components must be described from current Agent context, including principal, accrued fixed yield, and accrued airdrops. Missing fields must not be invented.

**Q: How is principal held, and can the project use it?**

Principal Minted into the Agent does not enter the project's personal wallet. It follows a contract-custodied path, with shares and Redeem governed by contract rules. The project cannot freely transfer holder principal as if it were its own wallet balance; exact permissions still follow the current contract.

**Q: If I Redeem during a vote, does my vote still count?**

That depends on the current proposal's snapshot and Redeem interaction rules. A snapshot usually fixes eligibility and weight, but whether the vote remains counted after Redeem must come from current Agent context or proposal rules, not a demo assumption.

**Q: Can the fixed APY change later?**

The Governance Agent fixed APY is set and disclosed at launch and enforced by contract rules; it should not be rewritten retroactively during the holding period. A concrete Agent's actual rate must still come from current Agent context, never a demo number.

**Q: What tokens pay the yield and airdrops?**

The fixed-yield denomination and airdrop token are current Agent configuration and may differ. They must come from current Agent context. If a denomination is not returned, report it as unavailable rather than inferring it from the project name or an example.

**Q: Can a project dominate voting by holding many shares?**

Top Holders exposes share concentration so users can inspect the power distribution before voting. Project-wallet restrictions or other anti-concentration rules are current-Agent dynamic facts from Agent context; the assistant must not infer the project's intent.
