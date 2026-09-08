# Strategy OS: data and broker rights

Checked 5 September 2026. This is an engineering and product decision record from public official sources. It is not legal clearance. A broker's staff interpretation is identified as such; it is not a general ruling by SEBI.

## Decision

Do not launch paid hosted access on the assumption that customer-owned API keys confer all necessary permissions. Four facts must be resolved separately: permission to sell the software, broker approval of the integration, rights to use the market data, and regulation of the actual research/alert/execution service.

The product need not be discarded. The existing separation of data providers, canonical research and execution brokers supports a licensed data route and broker-approved execution. Keep the research-and-alerts V0 boundary while resolving its own data and RA/IA questions. A self-authored rule, a disclaimer, a paid API subscription or a user clicking confirmation is not by itself a legal exemption.

## Official NIFTY data acquired

The normal [NSE Indices historical-data export](https://niftyindices.com/reports/historical-data) returned **248 daily NIFTY 50 OHLC observations, 5 September 2025–4 September 2026**. The raw CSV is in the user's Downloads folder as `NIFTY 50_Historical_PR_05092025to04092026.csv`. A normalized copy and provenance are in `.agent/runs/v0-launch-reset-2026-09-05/nse-data/`.

Dates are unique and prices pass finite/positive/OHLC-order checks. Complete exchange-calendar coverage has not yet been checked. This file has no volume, intraday bars, constituent-stock prices, option data or historical data-availability timestamps. Daily gap rules can use daily prices; opening-range/intraday rules need another interval. A one-year evaluation may need additional warmup and prior state. Never fill absent volume with zero or invent an intraday path from daily bars.

Public download is not commercial permission. [NSE's data policy](https://www.nseindia.com/static/market-data/nse-data-policy) makes intended use and redistribution subject to the relevant agreement. [NSE Indices website terms](https://niftyindices.com/terms-of-use) restrict use and automated collection. Obtain explicit storage, backtest/replay, display, non-display calculation, derived-alert and end-user rights through [NSE Indices data subscription](https://niftyindices.com/offerings/data-subscription), NSE Data or an authorised vendor before using the data as a paid product feed.

The owner-supplied [Telegram post](https://t.me/joshiquant/508) offers `Nifty_option_historical.zip`, 400.3 MB, described as one-minute NIFTY options with OI/IV from 2021–2026. It is not the underlying index dataset. The public browser exposes no direct file bytes and Telegram is unavailable in this session. It was not downloaded; keep it for later options work. Provenance and redistribution rights remain unknown.

## Broker configuration and permission

| Broker | Documented connection | Commercial implication |
| --- | --- | --- |
| Zerodha | Kite app key/secret and broker login/token flow. Use the documented flow and keep secrets server-side. | Terms expressly contemplate platforms serving Zerodha clients subject to required approvals. They restrict public market-data display, API sublicensing, permanent copies/redistribution and virtual/mock trading. BYOK does not remove those clauses. Obtain written permission for hosted research, retention, replay and alerts. [Kite terms, sections 2–5](https://kite.trade/terms/) |
| Dhan | Individuals and partners are distinct categories. Partners receive partner credentials, generate consent, redirect the user to Dhan and consume the consent for a user token. | The documented route for a platform serving users is the partner programme. Market-data use, caching and replay need the actual partner agreement. The public declaration's API-terms link was unavailable during this check; absence is not permission or prohibition. [Authentication](https://dhanhq.co/docs/v2/authentication/), [partner declaration](https://survey.dhan.co/api-partner-declaration-mar25) |
| Groww | Per-account API subscription; access-token, key/secret and TOTP flows with daily approval/expiry behavior. | The current retail algo terms limit use to self and defined family. General terms do not grant commercial data exploitation. No public paid multi-client grant was found. Ask for an API-specific partner agreement rather than treating personal tokens as a hosted-service licence. [API documentation](https://groww.in/trade-api/docs/curl), [terms IV/XI, updated 19 August 2026](https://groww.in/pages/terms-and-conditions-groww) |
| Angel One | SmartAPI app registration has trading, publisher, historical and market-feed categories, with app/redirect/client details. | Angel's implementation notice says registered static-IP order origins are required from 1 April 2026 and distinguishes client, provider and broker algos. API availability is not partner approval or permission for every commercial data use. Confirm hosting and data rights in writing. [App registration](https://smartapi.angelone.in/create), [April 2026 changes](https://www.angelone.in/news/market-updates/what-s-changing-in-angel-one-s-smartapi-access-from-april-1-2026) |
| Upstox | OAuth customer login, single-use authorization code, app secret and exact registered redirect URI. | On 1 September 2026 official staff said new Multi-Client/Business API onboarding was paused. Staff also stated broker-hosting/empanelment requirements including read-only fintech analytics. Treat this as a current broker onboarding constraint, not an independently established rule for every analytical product. [OAuth](https://upstox.com/developer/api-documentation/authentication/), [staff response](https://community.upstox.com/t/multi-user-platform-api-access-for-alphapatner-production-oauth-trading-integration/17298) |

Upstox staff separately discussed [private retention and derived research](https://community.upstox.com/t/can-upstox-historical-api-data-be-retained-locally-for-private-ml-backtesting-research/17302) and [sharing API data](https://community.upstox.com/t/clarification-needed-on-pulling-sharing-nifty-option-chain-data-via-upstox-api/17176). Those replies do not establish a signed paid-service licence, resolve exchange rights, or specify cache duration and termination deletion.

## Research and execution are different regulatory questions

Current-source limit: NSE's page links consolidated circular 73992 dated 30 April 2026 in a ZIP uploaded in May. Its download did not complete during this check. The 2025 text and currently linked FAQ below have not been reconciled against every provision in that consolidated package. Obtain and check that package before final implementation or legal sign-off.

[SEBI's February 2025 retail-algo framework](https://www.sebi.gov.in/sebi_data/attachdocs/feb-2025/1738665456458.pdf) addresses API algo orders and broker/provider responsibilities. Its [September extension](https://www.sebi.gov.in/sebi_data/attachdocs/sep-2025/1759232056254.pdf) made the framework applicable to all brokers from 1 April 2026. A low order rate does not remove the framework: [NSE's FAQ](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/FAQ_Retail%20Algo_03112025_NSE.pdf) requires tagging for client-API orders and distinguishes the client's own logic/static-IP route from provider logic hosted on broker infrastructure. Use the [current NSE empanelment materials](https://www.nseindia.com/static/trade/empanelled-algo-providers-exchange) for an application; do not freeze old thresholds into a new product promise.

Research and alerts without order capability still need classification. [SEBI's RA FAQ](https://www.sebi.gov.in/sebi_data/attachdocs/jul-2025/1753268710217.pdf) distinguishes research services/trading calls from exclusions such as broad-index analysis. Review actual presets, ranking, security-specific calls and marketing with Indian securities counsel. Personalized portfolio or allocation advice raises the separate [Investment Adviser question](https://www.sebi.gov.in/sebi_data/attachdocs/aug-2025/1755176446980.pdf). Neither an educational label nor white-box rules automatically settles these issues.

## Concrete next decisions

Prepare one architecture and permissions brief for each prospective broker/data supplier: paid hosted service; each user's authorization; exact fields and instruments; server and browser locations; raw/derived storage and retention; chart display; backtests/replay; in-app/external alerts; exports; deletion; and future order flow. Request written answers and the applicable contract. Do not contact anyone without owner authorization.

For V0, resolve a licensed research-data supply and the actual alert/preset classification. For later execution, secure a named broker's acceptance of provider/client classification, hosting, static IPs, registration/tagging, audit and risk controls. Do not route around restrictions by sharing credentials, disguising server origins or relabelling automated orders as manual.

Supporting independent reports: `.agent/runs/v0-launch-reset-2026-09-05/provider-rights/dhan-groww-upstox.md` and `sebi-nse.md`. No broker was contacted; no agreement was accepted, account connected, paid data purchased, order placed or production capability opened.
