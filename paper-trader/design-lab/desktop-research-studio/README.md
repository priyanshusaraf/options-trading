# Desktop workspace prototype

Entry: `paper-trader/design-lab/desktop-research-studio/index.html`. Open directly or serve this directory. No build step, account, backend call or production dependency change. This is a separate prototype; its graph is presentation state, not another IR or execution engine.

## Design intent

A quiet desktop workspace based on the existing adjustable three-pane foundation and production StrategyBuilderWorkspace node reference. One system UI typeface, moderate weights, neutral charcoal surfaces, compact controls and thin structural dividers. Monospace is reserved for numerical display. Repeated eyebrows, Research studio/Design preview titles, helper footer, blue left strips, marketing blocks and the forced builder-title/example-draft row are removed. NIFTY50 /248rows /1D share one compact aligned line.

The eight requested WhatsApp notebook JPEGs were located but all view_image calls failed with macOS Operation not permitted. They were **not inspected**. Root directed continuation from the supplied sketch description and prior frontend source. No image access workaround or browser session was used.

## Working interactions

- Resize both dividers by pointer, arrow keys, Shift+arrows, Home/End, or Layout sliders. Existing240px watchlist,480px chart,280px upper-pane and250px builder minimums remain, within the declared desktop viewport. Only `{left, top}` dimensions persist in the existing localStorage key; node state and toolbar visibility stay in memory.
- Context and Tools are independently hideable from the always-present top bar; Shift+C and Shift+T also toggle them. Shift+A opens the component palette outside inputs/editing fields. Phone/responsive work is deferred.
- Expand watchlist, chart or graph across the workspace below the top bar, instead of being limited to its former pane. Restore is always reachable in the top bar; Escape also restores. Nested SVG targets cannot intercept button pointer events, expand uses currentTarget and suppresses default actions, and the brand is a non-navigating workspace button.
- The prior source did not establish a pointer-to-logo navigation defect: expand buttons were not nested in the logo link. The DOM interaction check now clicks each nested SVG/use target and verifies the intended pane. Actual browser hit testing is still required; the earlier report is not claimed reproduced or fully resolved by a DOM simulation.
- Six separate graph components replace grouped rule cards. Drag nodes; select each for its name/parameter inspector; use arrow keys on focused nodes to move them. Click an output then an input to connect. The inspector can disconnect edges or remove a component. Zoom/Fit controls and the Shift+A palette remain available through Tools. Fresh draft starts empty; presets restore example graph layouts.
- Graph edits are in-memory UI changes. They do not calculate signals, execute, save a canonical strategy or serialize a second strategy representation. About discloses those limits; component details remain in its inspector.
- Lightweight Charts provides actual price-chart pan, wheel/pinch zoom, drag-to-scale price/time axes, double-click scale reset, crosshair and individual candle OHLC. Visible date labels follow the actual chart range. Resizing and inspector selection retain the user's pan/zoom range. Candles/line and1M/3M/6M/1Y controls remain.

## Chart source and truth

Reused the installed `paper-trader/frontend/node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js`, version4.2.3. The unchanged prototype-only copy is `vendor/lightweight-charts-4.2.3.js`. Apache2.0 LICENSE is copied from that local package; the npm installation omitted NOTICE, so the original NOTICE was retrieved from the official tagged source:

https://raw.githubusercontent.com/tradingview/lightweight-charts/v4.2.3/NOTICE

The original copyright header remains in the bundle. About carries the NOTICE attribution; a visible chart link and the enabled built-in attribution logo link to TradingView. The latter remains available when toolbars are hidden. This is **Lightweight Charts, not Advanced Charts**: no Fibonacci/drawing toolbar, paid/private Advanced package or production adoption is claimed. Root owns the full-chart licence decision.

`history.js` is unchanged:248 recorded NIFTY50 daily OHLC rows from the approved NSE Indices export,5Sep2025–4Sep2026. No volume, historical publication timestamps or asserted calendar coverage. Missing dates are not filled. The50-row EMA remains a calculated chart guide, seeded from its first50 recorded closes. Node parameter edits do not alter that independently labelled guide. Other watchlist entries retain honest missing-history states. No trades, returns, equity curve or execution authority is fabricated. Truth limits and source details are available through About/Data details rather than a repeated instruction footer.

## Verification and handoff

`node --check studio.js` and the vendored bundle pass. Run the existing-runtime interaction check with:

```sh
/Users/priyanshusaraf/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node paper-trader/design-lab/desktop-research-studio/check.cjs --mutations
```

The check passes source row count, chart option/crosshair/range wiring, missing-history behavior, nested SVG expand clicks, restore, divider pointer/keyboard bounds, dimension-only persistence, independent chrome, shortcut input guard, node drag/edit/connect/remove and fresh/add flows. Five selected mutants are caught by assertions: wrong expansion target, shortcut input guard removal, connection write removal, crosshair OHLC update removal, and invented availability for missing history. Temporary mutation copies are removed. This is targeted proof, not exhaustive mutation analysis.

JSDOM uses a chart API stub because it does not render the real canvas. It does not prove visual layout, native browser hit testing, chart gesture behavior, full accessibility, performance or release readiness. Root owns final desktop browser review. No shared browser tools were used.

Static source checks on142 functions/callbacks: Oxlint1.75.0 maximum cyclomatic complexity15 (below22); SonarJS4.2.0/ESLint9.39.5 reports no cognitive complexity above21; typhonjs-escomplex0.1.0 maximum method Halstead difficulty22 (below80). Existing ignored verification tooling was reused, not added as a dependency. Per-function measured CRAP is unverified for this prototype; the DOM check is not represented as coverage. No global quality/launch pass.

Source hashes and local package integrity are in `source-freeze.json`. Root should inspect the1440×900 desktop: actual expand pointer path and top-bar restore, independent hide/show, Shift+A outside fields, node dragging/editing/connections, chart pan/zoom/price-axis scaling/crosshair and readable OHLC after resizing.

## Root browser check, 5 September

At 1440×900, actual pointer activation expanded the chart below the app bar and Restore returned the three panes. The initial resize changed the visible interval. The native resize-lock option alone did not resolve the observed behavior, so the observer now captures the logical interval, resizes synchronously, and restores that interval; it ignores hidden zero-sized hosts. Real-browser checks confirmed 9 June–4 September stayed unchanged through expand and restore. The existing interaction check now exercises the observer and kills a sixth selected mutation that removes interval restoration.

Context and Tools hid independently; Shift+A still opened the component palette with both hidden. No captured browser console errors. This is a limited desktop interaction check, not full chart gesture, screen-reader, accessibility, production or release evidence. Per-function CRAP remains unverified. The temporary desktop viewport was reset after checking.

Dropdown alignment follow-up: replaced font-dependent arrow characters in Revision, dataset and OHLC controls with one shared SVG chevron. Labels share a baseline and icons are centered. Browser pointer checks opened both dataset and revision dialogs; the existing interaction check passes. This does not turn the prototype dialogs into live dataset/revision selection.

Dialog follow-up: removed the shared modal outer border. Browser computed style confirms border0px and outline-style none; screenshot confirms no light perimeter. Keyboard focus styles on interactive controls remain.
