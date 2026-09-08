# TradingView integration decision

Checked 5 September 2026. Owner wants familiar TradingView chart interaction, Fibonacci/trendline drawings, saved chart versions and typed strategy-node inputs.

## Product and licensing

Target Advanced Charts for the full technical-analysis drawing interface. It is a self-hosted JavaScript library with datafeed, drawing and persistence APIs. Market data is supplied by Strategy OS; the licence does not grant NSE or broker data rights.

TradingView's published Free Advanced Charts Agreement v.0626.FAC restricts the standard free implementation to a free public service. Registration may be required. Private/personal/internal uses are excluded, and attribution is required. Do not assume our invited beta or future paid offering qualifies. Request written eligibility and commercial terms; no public price for that case was found. A consumer TradingView subscription is a separate product. Trading Platform adds broker execution and carries licensing fees; no public fixed integration price was found. It is not required for the current research-and-alerts V0.

Lightweight Charts is Apache2 open source. The legacy frontend already uses4.2; its chart controls can be reused while Advanced Charts access is unresolved. It is not the full drawing/indicator toolbar. Never claim the Lightweight implementation supplies Advanced Charts. No private proprietary library was downloaded, agreement accepted or vendor message sent.

## Implementation boundary

1. Serve canonical owner-scoped historical/live data through the Datafeed API. Preserve symbol, interval, session/timezone, availability and adjustment semantics. Render the same verified data and strategy-derived series that research uses.
2. Capture drawing events and point/property data through documented APIs. Record actual normalized timestamps: TradingView may snap a requested point to an existing bar.
3. Save immutable chart versions in Strategy OS, including instrument, timeframe, dataset/as-of, drawing geometry and properties, visible range and price-scale settings. Layout save alone does not preserve every research context field.
4. Convert supported drawings into our typed annotation records. Trend lines, horizontal levels and Fibonacci ratios need precise geometry/scale semantics. Retain raw chart layout for restoration, not as the strategy execution contract.
5. A strategy node binds a particular chart/annotation version. Editing a drawing creates a new version; it must not rewrite earlier backtests or active bindings. Record creation/effective times and flag retrospective drawings; historical hindsight is not causal evidence.

Advanced Charts does not run Pine Script or provide TradingView's server-side alerts. Strategy OS remains responsible for IR execution, backtesting, validation and alerts. Existing studies/drawings are not permission to execute an order. Keep self-hosted save/load authorization tied to the session owner; do not adopt the unauthenticated demo storage.

## Official sources

- Product/features: https://www.tradingview.com/advanced-charts/
- Current introduction/free conditions/datafeed requirement: https://www.tradingview.com/charting-library-docs/latest/introduction/
- Published agreement: https://s3.amazonaws.com/tradingview/charting_library_license_agreement.pdf
- Product comparison: https://www.tradingview.com/free-charting-libraries/
- FAQs, Trading Platform fees and Pine limitations: https://www.tradingview.com/charting-library-docs/latest/getting_started/Frequently-Asked-Questions/
- Drawings API: https://www.tradingview.com/charting-library-docs/latest/ui_elements/drawings/drawings-api/
- Save/load: https://www.tradingview.com/charting-library-docs/latest/saving_loading/
- Separate drawings: https://www.tradingview.com/charting-library-docs/latest/saving_loading/saving_drawings_separately/
- Datafeed: https://www.tradingview.com/charting-library-docs/latest/connecting_data/Datafeed-API/
- Lightweight source/licence: https://github.com/tradingview/lightweight-charts
