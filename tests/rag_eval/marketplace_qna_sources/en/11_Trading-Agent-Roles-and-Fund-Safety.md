## Trading Agent Roles and Fund Safety

The mechanics below apply to Hyperliquid trading Agents (Agent Type `hyperliquid`) and are stable platform knowledge. Exact fee rates and the settlement schedule are dynamic configuration of the current Agent and must be read from current Agent context or the page; never fill them with sample values.

### Executor and Trading Wallet

**Q: Are the Executor and the Trading Wallet two separate addresses?**

They can be, though the default setup uses one.

The Executor keeps the Agent running: it updates the share price and moves funds between the contract and the exchange. The Trading Wallet places orders on the Agent's behalf. By default a single address takes on both roles, and you can also configure them separately.

**Q: Why does the address have to be one that has never been used on Hyperliquid?**

The requirement applies to the Trading Wallet.

Hyperliquid will not register an address that already holds its own account as another account's trading wallet. If your Trading Wallet has traded or received funds on Hyperliquid, registration fails.

Under the default setup the Executor doubles as the Trading Wallet, so the requirement lands on the Executor address. Once you separate the two roles, only the Trading Wallet has to meet it, and the Executor faces no such limit.

A freshly created wallet is both safer and more convenient.

**Q: The address has been used on another chain. Does that matter?**

No. The restriction looks only at Hyperliquid. Activity on HyperEVM, Ethereum, or any other chain has no bearing on it.

**Q: Does the Trading Wallet authorization expire?**

Yes, after 90 days.

Once it lapses, the wallet can no longer place orders for the Agent and trading stops. Authorizing again restores it. Check ahead of the expiry date rather than waiting for trading to halt.

**Q: After I switch the Executor, does the old address keep any permissions?**

You can revoke its permissions on the Agent contract, but its registration as a trading wallet on Hyperliquid does not lapse automatically.

If the old address's private key may have leaked, treat it as still able to place orders in the Agent's name until you confirm its removal from the Agent's trading wallet list. Close any risky positions first, and contact the Moss technical team for help confirming.

**Q: How does the Executor arrive at the amount it transfers each time?**

A transfer changes the location of the funds, never the total. Whatever leaves HyperEVM appears on HyperCore, and the holder throughout is the Agent contract. Transferring more or less therefore has no effect on a user's total assets or on the share price.

**Q: The Executor runs on the publisher's own machine. Can it take my funds?**

No. Every transfer the Executor can initiate pays a fixed recipient, the Agent contract's account on the other side, and that destination is written into the contract and cannot be changed. The Executor decides how much to move and when, and it has no way to name a new address.

### Owner

**Q: What does the Owner do?**

The Owner created the Agent and holds the highest permissions, yet takes no part in daily operation. Its actions center on creating the Agent and changing its configuration later. It never joins a settlement or a trade.

**Q: Does the Owner's private key need to sit on a server?**

No.

The Executor handles daily operation. The Owner comes in only for a handful of configuration actions, which you sign directly in your own wallet; the private key stays in your own custody.

### Agent Contract and Fund Safety

**Q: Where do I find the Agent contract address?**

In the On-Chain Info panel on the detail page, on the Contract row.

**Q: Contract row and Share Token row show identical addresses—is that right?**

No. The Agent contract is the share token itself, so both rows point to the same contract. This sits at the core of FAT Protocol.

**Q: Where are the funds after an Agent's tokenization?**

Under the Agent contract. They only ever sit in two places: HyperEVM, where the Agent contract lives, and the Agent's account on Hyperliquid. Both sit under the Agent contract address.

**Q: After I mint, where do my funds actually sit?**

Under the Agent contract. They only ever sit in two places: inside the contract on HyperEVM, or in the Agent's trading account on HyperCore. Both use the same single Agent contract address.

**Q: Who holds my funds?**

The Agent contract holds them throughout. The Owner, the Executor, and the Trading Wallet never hold user funds at any stage.

**Q: Can the Executor or the Trading Wallet take my money?**

No. The Agent contract opens only a whitelist of restricted functions to the Executor, and the Trading Wallet can do nothing but sign. Even with either private key in hand, an attacker could at most submit a wrong settlement figure or place orders in the Agent's name. Neither path moves funds out.

**Q: If one of these private keys leaks, can someone take my money?**

No.

The Executor can call only the handful of operations the Agent contract permits. It cannot alter the configuration, and it cannot send funds to an arbitrary address. The Trading Wallet holds signing permission for orders alone, and every order and position belongs to the Agent contract.

At worst an attacker submits incorrect settlement data, or places reckless orders in the Agent's name and loses money on the trades. The funds themselves cannot leave.

**Q: If a trade loses money, has the money been taken?**

No. A loss is the outcome of a trade, and the funds go to a counterparty through the order book. That is the normal consequence of taking part in a market, and it differs entirely from an address moving funds into its own name. Neither the publisher, nor the Executor, nor the Trading Wallet gains anything from the Agent's losses.

This design keeps your funds from being stolen. It does not keep them from losing value. The strategy carries its own risk of loss at all times.

**Q: I sent funds to the Agent contract address by mistake. Can I get them back?**

No. Those funds count toward the Agent's total assets at the next settlement, and every shareholder shares them in proportion to their holding.

### Settlement, Minting, and Redemption

**Q: Why is there a wait after submitting a Trading Agent Mint before shares are issued?**

For a Hyperliquid Trading Agent, a submitted Mint waits for Executor settlement; shares are issued only after that settlement. How many shares you receive depends on the price per share for that period, and that price comes out of the Executor's settlement. Until it runs, the contract has no way to tell how many shares your deposit buys. Trading Agent redemption works the same way. The settlement schedule is part of the current Agent's configuration; check the page for the current timing.

**Q: After several Trading Agent redeem requests, do I claim each one separately?**

For a Hyperliquid Trading Agent, several redeem requests do not require separate claims: all matured requests are claimed once in a batch, while unmatured requests wait for a later settlement.

**Q: What if the Agent goes a long time without settling?**

If a Hyperliquid Trading Agent remains unsettled for a long time, the Agent contract still holds the funds; use Refund on the page to take the principal back.

### Fees

**Q: Does Mint or Redeem charge a fee? Who receives it? Are there any other fees?**

Whether a management fee, mint fee, redeem fee, or profit share applies, and at what rate, depends on the current Agent's fee configuration. Check the current fees shown on the detail page and in the action flow rather than relying on any fixed sample number.

Beyond Agent fees, the only cost you always pay is gas, the standard network fee on any on-chain action. It goes to the blockchain network, not to Moss and not to the Agent's creator. Check the fees shown on the page before you confirm each action.
