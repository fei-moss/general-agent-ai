## Consumer Agent Refund, Fund Safety, and UI States

This document covers Consumer Agent Refund, principal custody, balance display, and Paused UI behavior. The current Agent page supplies any Refund fee; unanswered fee, extra-return, and holding-duration questions remain pending product-owner input.

**Q: Which Consumer Agent shares can use Refund?**

Only shares still held by the user and not yet redeemed for a code qualify for Consumer Agent Refund.

**Q: Can Consumer Agent shares already redeemed for a code use Refund?**

No. Code redemption consumes them, so the same shares cannot be used for Refund.

**Q: How much does a Consumer Agent Refund return?**

It uses the current exchange rate for unredeemed shares, less applicable fees; this is not a fixed-amount promise.

**Q: Status flow: which statuses follow a Consumer Agent Refund submission?**

A Consumer Agent Refund enters Pending. When processing finishes, the status becomes Claimable; use Consumer Refund claim to return the amount to the wallet.

**Q: Is there a lifetime count cap on Consumer Agent Refund requests?**

The Consumer Agent Refund mechanism has no cumulative request-count limit. Eligibility and request status come from the Consumer Agent page.

**Q: Where does a Consumer Agent hold user Mint principal—can it enter the brand wallet?**

For a Consumer Agent, the smart contract holds user Mint principal; it never enters the Consumer Agent brand's wallet or Moss's wallet.

**Q: Can the brand use user principal?**

No. The brand cannot transfer user principal from the contract as if it were the brand's own funds.

**Q: Can Moss use user principal?**

No. Moss cannot bypass the contract and remove user principal.

**Q: Can the brand or Moss change terms for existing users midway?**

They cannot retroactively rewrite contract-fixed terms for users who already entered; current terms come from the Consumer Agent page or typed context.

**Q: What happens if a Consumer Agent brand stops honoring its benefits?**

Principal corresponding to the user's unredeemed shares remains in the contract; issued-code performance still depends on the brand honoring the benefit.

**Q: Can Agent shares be transferred or sold on an exchange?**

Shares are standard ERC-20 tokens and have onchain transfer capability. Moss's in-product Consumer exit is Refund; do not assume a trading market exists.

**Q: Will a Consumer Agent share rise because of market speculation?**

No: there is no APY, fixed yield, or appreciation promise. Refund value follows the current exchange rate.

**Q: Does the Consumer Agent My Shares balance include shares already converted into codes?**

The My Shares balance excludes shares already converted into codes; it displays only shares the user still holds.

**Q: For a Consumer Agent, what do Mint Activity and Redemption Code Activity show?**

They show Mint and code-generation records. Addresses in these views are masked.

**Q: Why is the Consumer Agent Refund button greyed out?**

Common reasons are that the current wallet holds no eligible shares or that the Agent has been paused; use the page's current state.

**Q: What does Paused by owner mean?**

It means the issuer paused new Mint and Refund operations. Existing shares remain with the user.

**Q: Can I receive a Consumer Agent code and then Refund the same shares?**

No; consumed shares cannot be restored or used for Refund.

**Q: Is this a guarantee that I receive a fixed principal amount?**

No fixed amount is promised. Refund returns the current value of unredeemed shares, less applicable fees.
