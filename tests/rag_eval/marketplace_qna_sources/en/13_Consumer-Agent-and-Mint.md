## Consumer Agent and Mint

This `consumer` document covers first-time onboarding and Mint mechanics. Agent-specific Mint settings must come from the current Agent page or typed context.

**Q: What does a Consumer or Redemption Agent do?**

A Consumer Agent lets a user Mint standard shares for brand benefits, then choose code redemption or Consumer Agent Refund for shares not used for a code.

**Q: How is obtaining brand benefits here different from buying directly from the brand?**

A direct purchase delivers the benefit immediately; a Consumer Agent first gives the user shares, followed by benefit redemption or Refund. For principal custody, see Refund, Fund Safety, and UI States.

**Q: Is a Consumer Agent an investment product, and does it have APY?**

It is not an investment product and it has no APY or annual-yield promise. Its purpose is brand-benefit redemption.

**Q: Are the shares received from Mint NFTs?**

No. Consumer Agent shares are standard ERC-20 tokens, not NFTs. They are divisible.

**Q: What gives a share its value?**

Its value comes from the benefit it can redeem and its current Refund value while unused. It does not represent equity in the brand, company valuation, or an expectation of appreciation.

**Q: What is the first-time onboarding path from wallet connection to My Shares?**

Use `Connect Wallet -> Mint -> Claimable -> My Shares`: submit Mint, claim after the status becomes Claimable, and confirm the shares in My Shares.

**Q: After my first Consumer Agent Mint completes, where do I claim and find the shares?**

After Mint processing completes, the shares become Claimable. Claim them there, then confirm the Consumer shares in My Shares.

**Q: Does Mint give me a redemption code immediately?**

No. Mint first creates Agent shares. Code creation is a later user action covered by Redemption Code Creation and Use.

**Q: What is the minimum Mint amount?**

The minimum Mint amount is not a platform-wide constant. Read it from the current Agent page or typed context.

**Q: How much is the Mint fee?**

The page shows the applicable fee before confirmation. The fixed knowledge base stores no fee rate.

**Q: Which tokens can I use to Mint?**

Each Consumer Agent accepts one settlement token fixed at deployment. Read that token from the current Agent page or typed context.

**Q: Can the brand or Moss change the settlement token later?**

One settlement token is fixed when the Agent is deployed; an existing Agent cannot be switched to another token on demand.
