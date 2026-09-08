const components = [
  {
    name: 'Historical gap overlay',
    description: 'Track unresolved full-range daily gaps and use them as targets within a parent trend.',
    inputs: 'Completed daily OHLC, ATR and a separately defined trend state.',
    outputs: 'Gap zones, the selected target and overlay eligibility.',
  },
  {
    name: 'Bullish / bearish trend state',
    description: 'Provide a reusable trend state for overlays and strategy routing.',
    inputs: 'Completed price data and an explicit classification rule.',
    outputs: 'A named trend state and its confirmation or invalidation.',
  },
  {
    name: 'Break / retest / reclaim',
    description: 'Recognise a confirmed zone break, wait for a retest and detect rejection or reclaim.',
    inputs: 'Completed OHLC, ATR and a fixed, versioned support or resistance zone.',
    outputs: 'Approach, break, retest, rejection and invalidation states.',
  },
] as const

export function StrategyComponents() {
  return <section aria-label="Strategy components">
    <p className="slate-preset-note">Ready-made rules for a strategy you’re building. These planned components will be added to an existing strategy as one expandable node.</p>
    <div className="slate-preset-grid">{components.map((component) => <article className="slate-preset-card" key={component.name}>
      <h2>{component.name}</h2><p>{component.description}</p>
      <p className="slate-component-status">Planned for a later release</p>
      <details><summary>Inputs and outputs</summary>
        <p><strong>Inputs:</strong> {component.inputs}</p>
        <p><strong>Outputs:</strong> {component.outputs}</p>
      </details>
    </article>)}</div>
  </section>
}
