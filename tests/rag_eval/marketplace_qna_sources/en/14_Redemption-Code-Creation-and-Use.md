## Redemption Code Creation and Use

This document covers the user-initiated Consumer Agent code-redemption flow. Per-code threshold, value, and expiry come from the current Agent page or typed context; unapproved code recovery, transfer, and expiry questions remain pending product-owner input.

**Q: How do I turn shares into a redemption code?**

Open the current Consumer Agent and choose Redeem. Select a quantity and confirm; once the configured threshold is met, the shares are consumed and a code is generated.

**Q: How many shares are required for one code?**

Shares required per code are not a platform-wide constant. Read the current Agent configuration.

**Q: What happens to the shares after successful code redemption?**

Redemption consumes those shares; they cannot be restored or used for Refund.

**Q: During code redemption: If I redeem only some benefits, what happens to the Consumer shares I leave unused?**

Shares not included in that redemption remain held and may later use Consumer Agent Refund.

**Q: How do I consume the benefit after a code is generated?**

The success dialog provides a Go Consume jump button. Its current destination comes from the Agent page.

**Q: What if my shares were deducted but no code appeared?**

The system should record the exception and retry. If unresolved, use the support route on the current Agent page and provide the operation record.

**Q: Will holding long enough automatically redeem a code?**

A Consumer Agent does not auto-redeem. The user must start and confirm code redemption.

**Q: Where do I check the threshold, value, and expiry before redeeming a code?**

Those facts must come from the current Agent page or typed context. If code expiry is absent, keep it pending rather than inventing a duration.
