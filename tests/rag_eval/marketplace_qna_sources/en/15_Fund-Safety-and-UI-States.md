## Consumer Agent Fund Safety and UI States

This document covers Consumer Agent fund custody, balance display, and Paused UI behavior. Specific Agent information comes from the current page or typed context.

**Q: Do Consumer Agents support Refund?**

Consumer Agents do not support Refund. Please check all Agent information on the page before deciding whether to Mint.

**Q: Where does a Consumer Agent hold user Mint principal—can it enter the brand wallet?**

For a Consumer Agent, the smart contract holds user Mint principal; it never enters the Consumer Agent brand's wallet or Moss's wallet.

**Q: Can the brand use user principal?**

No. The brand cannot transfer user principal from the contract as if it were the brand's own funds.

**Q: Can Moss use user principal?**

No. Moss cannot bypass the contract and remove user principal.

**Q: Can the brand or Moss change terms for existing users midway?**

They cannot retroactively rewrite contract-fixed terms for users who already entered; current terms come from the Consumer Agent page or typed context.

**Q: What happens if a Consumer Agent brand stops honoring its benefits?**

Assets corresponding to unredeemed shares remain held by the contract; whether issued codes can be used depends on the brand honoring its obligations.

**Q: Can Agent shares be transferred or sold on an exchange?**

Shares are standard ERC-20 tokens and have onchain transfer capability; do not assume a trading market exists.

**Q: Will a Consumer Agent share rise because of market speculation?**

No: there is no APY, fixed yield, or appreciation promise.

**Q: Does the Consumer Agent My Shares balance include shares already converted into codes?**

The My Shares balance excludes shares already converted into codes; it displays only shares the user still holds.

**Q: For a Consumer Agent, what do Mint Activity and Redemption Code Activity show?**

They show Mint and code-generation records. Addresses in these views are masked.

**Q: What does Paused by owner mean?**

It means the issuer has paused operations. Refer to the page's current state for which Mint or other actions are paused; existing shares remain held by the user.
