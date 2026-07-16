## Trading Shares (DEX / Secondary Market)

**Q: How do I sell my minted shares?**

The Agent detail page checks whether the Agent's shares have a corresponding DEX trading pair:

- Yes: A Trade on DEX module is shown, and the selling flow is the same as trading on Uniswap.

- No: Selling is only possible via Redeem.

**Q: If the secondary market has no buyers or poor liquidity and I cannot sell, what do I do?**

When secondary market liquidity is insufficient, you can redeem your funds via Redeem.

**Q: The share price on the DEX differs from the Mint / Redeem price (NAV). Why? Which one should I follow?**

Because the DEX price and the Mint / Redeem price come from two different sources:

- Official price (NAV / exchangeRate): The net value calculated by the contract, that is, "how much Accept Token one share is actually worth right now." This is the price used when you Mint or Redeem, and it also reflects whether the Agent is making money.

- Market price (DEX price): The price negotiated between buyers and sellers on the secondary market, affected by how many buyers there are, how good the liquidity is, and how bullish people are on the Agent. It may deviate somewhat from the official price.

Which one to look at depends on how you want to operate:

- To Mint / Redeem directly with the contract: Look at the official price, and note fees and settlement status.

- To buy / sell on a DEX: Look at the live market price, and note liquidity, slippage, and fees.

- If the two prices differ greatly, be cautious: it may be because few people are trading (insufficient liquidity), or a premium / discount caused by market sentiment or redemption restrictions.

Moss Agent Marketplace does not decide for you which to choose, nor does it provide trading advice. Please compare price, fees, waiting time, and risk yourself before deciding.

**Q: Between buying shares on a DEX and minting directly, which is more recommended?**

You can compare price, the quantity you can buy, and fees comprehensively, then decide which way to acquire Agent shares.
