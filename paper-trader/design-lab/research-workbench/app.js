const views = [...document.querySelectorAll('.view')]
const links = [...document.querySelectorAll('.rail-link')]
const nextButtons = [...document.querySelectorAll('[data-next]')]
const title = document.querySelector('#view-title')
const mobileNav = document.querySelector('#mobile-nav')

const state = {
  draftReady: true,
  compatibilityReady: false,
  backtestSeen: false,
  challengeSeen: false,
  evidenceSaved: false,
  revision: '04',
  savedWindow: 15,
  stagedWindow: 15,
  candidate: false,
}

const resultViews = ['backtest', 'challenge', 'evidence', 'monitor']

function permitted(id) {
  if (id === 'compatibility') return state.draftReady
  if (resultViews.includes(id) && !state.compatibilityReady) return false
  if (id === 'challenge') return state.backtestSeen
  if (id === 'evidence') return state.challengeSeen
  if (id === 'monitor') return state.evidenceSaved
  return true
}

function nextRequiredView() {
  if (!state.draftReady) return 'compose'
  if (!state.compatibilityReady) return 'compatibility'
  if (!state.backtestSeen) return 'backtest'
  if (!state.challengeSeen) return 'challenge'
  if (!state.evidenceSaved) return 'evidence'
  return 'monitor'
}

function updateNavigation() {
  links.forEach((link) => { link.disabled = !permitted(link.dataset.view) })
  nextButtons.forEach((button) => { button.disabled = !permitted(button.dataset.next) })
  ;[...mobileNav.options].forEach((option) => { option.disabled = !permitted(option.value) })
}

function showView(id, focus = true) {
  if (!views.some((view) => view.id === id)) id = 'welcome'
  if (!permitted(id)) {
    id = nextRequiredView()
  }

  views.forEach((view) => view.classList.toggle('is-active', view.id === id))
  links.forEach((link) => {
    const active = link.dataset.view === id
    link.classList.toggle('is-active', active)
    if (active) link.setAttribute('aria-current', 'step')
    else link.removeAttribute('aria-current')
  })
  mobileNav.value = id
  const active = document.querySelector(`#${id}`)
  title.textContent = active.dataset.title || 'Research workbench'
  history.replaceState(null, '', `#${id}`)
  window.scrollTo(0, 0)
  if (id === 'backtest') state.backtestSeen = true
  if (id === 'challenge') state.challengeSeen = true
  updateNavigation()
  if (focus) {
    const heading = active.querySelector('h1')
    heading?.setAttribute('tabindex', '-1')
    heading?.focus({ preventScroll: true })
  }
}

links.forEach((link) => link.addEventListener('click', () => showView(link.dataset.view)))
nextButtons.forEach((button) => button.addEventListener('click', () => showView(button.dataset.next)))
mobileNav.addEventListener('change', () => showView(mobileNav.value))
document.querySelector('.brand').addEventListener('click', (event) => { event.preventDefault(); showView('welcome') })
document.querySelector('#account-button').addEventListener('click', () => {
  showView('welcome')
  document.querySelector('#signin-form input').focus()
})
window.addEventListener('hashchange', () => showView(location.hash.slice(1) || 'welcome'))

const rules = {
  observe: {
    explanation: 'Define the completed market data that the remaining rules may use.',
    rows: [
      ['1', 'Study RELIANCE and HDFCBANK on completed 5-minute candles.', 'study: RELIANCE,HDFCBANK; candle: completed'],
      ['2', 'Require NIFTY 50 to close above its 20-period average as a price-only market filter.', 'filter: NIFTY.close > sma(close,20)'],
      ['3', () => `Measure the first ${state.stagedWindow} minutes after the 09:15 market open.`, () => `opening_range.window = ${state.stagedWindow}m`],
    ],
  },
  enter: {
    explanation: 'Mark a research entry only when price, participation, and the market filter agree.',
    rows: [
      ['1', () => `After ${timeAfterOpen(state.stagedWindow)}, require an equity close above its opening-range high.`, 'close > range.high'],
      ['2', 'Require that equity’s volume exceeds its completed 20-bar average.', 'volume > sma(volume,20)'],
      ['3', 'Count at most one research entry per equity each day.', 'daily_entries.max = 1'],
    ],
  },
  protect: {
    explanation: 'Keep sizing and the adverse-move assumption explicit in the research test.',
    rows: [
      ['1', 'Limit assumed risk to 0.5% of the research allocation.', 'risk.fraction = 0.005'],
      ['2', 'Measure initial protection at 2.0 ATR below the example entry.', 'stop.distance = atr(14) × 2'],
    ],
  },
  exit: {
    explanation: 'Exit conditions close the research position without needing a fresh entry decision.',
    rows: [
      ['1', 'Exit when a completed candle closes below the 9-period EMA.', 'close < ema(close,9)'],
      ['2', 'Close any remaining research position at 15:15.', 'session.flat_at = 15:15'],
    ],
  },
}

function timeAfterOpen(minutes) {
  const total = 9 * 60 + 15 + minutes
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

let activeRule = 'observe'

function renderRule(key = activeRule) {
  activeRule = key
  const content = document.querySelector('#rule-content')
  if (!state.draftReady) {
    content.innerHTML = '<div class="empty-draft"><span>EMPTY DRAFT</span><h2>No rules yet</h2><p>Load the opening-range starter, then edit its native controls. Data checks stay unavailable until the draft has rules.</p><button class="primary" data-inline-preset>Load starter rules</button></div>'
    document.querySelector('#rule-explanation').textContent = 'A strategy needs at least one observation and one testable condition.'
    document.querySelector('#rule-technical').textContent = 'No technical rule details yet.'
    content.querySelector('[data-inline-preset]').addEventListener('click', loadPreset)
    return
  }

  const group = rules[key]
  const technical = []
  content.innerHTML = group.rows.map(([no, copy, detail]) => {
    const resolvedCopy = typeof copy === 'function' ? copy() : copy
    const resolvedDetail = typeof detail === 'function' ? detail() : detail
    technical.push(`${no}. ${resolvedDetail}`)
    return `<div class="rule-row"><span>${no}</span><p>${resolvedCopy}</p></div>`
  }).join('')
  document.querySelector('#rule-technical').textContent = technical.join('\n')
  document.querySelector('#rule-explanation').textContent = group.explanation
  document.querySelectorAll('.rule-tab').forEach((button) => button.classList.toggle('is-active', button.dataset.rule === key))
}

document.querySelectorAll('.rule-tab').forEach((button) => button.addEventListener('click', () => renderRule(button.dataset.rule)))

function resetDownstream() {
  state.compatibilityReady = false
  state.backtestSeen = false
  state.challengeSeen = false
  state.evidenceSaved = false
  document.querySelector('#replace-dataset').disabled = false
  document.querySelector('#replace-dataset').textContent = 'Use complete example dataset'
  document.querySelector('#hdfc-row').classList.add('blocked')
  document.querySelector('#hdfc-volume').innerHTML = '<strong>Missing</strong>'
  document.querySelector('#hdfc-result').innerHTML = '<span class="state-badge bad">Blocked</span>'
  document.querySelector('#compat-badge').className = 'state-badge warn'
  document.querySelector('#compat-badge').textContent = '1 dataset blocked'
  document.querySelector('#diagnosis-title').textContent = 'HDFCBANK cannot be tested with this dataset'
  document.querySelector('#diagnosis-copy').innerHTML = 'This example HDFCBANK dataset has no volume values from 01 Aug to 29 Aug 2026. The equity rule needs volume to confirm entry conditions. NIFTY is only a price filter, so its volume is not required.'
  document.querySelector('#resolution-copy').textContent = 'Choose the complete example dataset before running the test. No missing value will be guessed.'
  document.querySelector('#compat-status').textContent = 'Backtest and later results are blocked.'
  document.querySelector('#scope-summary').textContent = '2 equities + 1 price-only index filter · 1 dataset blocked'
  document.querySelector('#to-backtest').disabled = true
  document.querySelector('#save-evidence').disabled = false
  document.querySelector('#save-evidence').textContent = 'Save evidence record'
  document.querySelector('#evidence-status').textContent = 'Evidence has not been saved.'
  document.querySelector('#to-monitor').disabled = true
  updateNavigation()
}

function syncDraft() {
  const label = !state.draftReady ? 'Empty draft' : state.candidate ? `Candidate 04-A · ${state.stagedWindow}-minute window` : `Opening range · Revision ${state.revision}`
  document.querySelector('#revision-name').textContent = label
  document.querySelector('#revision-state').textContent = state.draftReady ? (state.candidate ? 'Unsaved research candidate' : 'Saved preset') : 'No rules'
  document.querySelector('#compose-kicker').textContent = state.draftReady ? `Equity opening range · ${label}` : 'New strategy · Empty draft'
  document.querySelector('#compose').dataset.title = state.draftReady ? `Compose · ${label}` : 'Compose · Empty draft'
  if (document.querySelector('#compose').classList.contains('is-active')) title.textContent = document.querySelector('#compose').dataset.title
  document.querySelector('#sheet-revision').innerHTML = state.draftReady ? `${state.candidate ? '04-A' : state.revision}<br>—<br>A` : '—<br>—<br>—'
  document.querySelector('#window-select').disabled = !state.draftReady || state.candidate
  document.querySelectorAll('.rule-tab').forEach((button) => {
    button.disabled = !state.draftReady
    button.querySelector('span').textContent = state.draftReady ? String(rules[button.dataset.rule].rows.length) : '0'
  })
  document.querySelector('#stage-change').disabled = !state.draftReady || state.stagedWindow === state.savedWindow
  document.querySelector('#load-preset').hidden = state.draftReady
  document.querySelector('#current-window').textContent = state.draftReady ? `${state.savedWindow} minutes` : 'No value'
  document.querySelector('#proposed-revision').textContent = state.candidate ? 'Candidate 04-A' : 'None'
  document.querySelector('#change-title').textContent = state.candidate ? 'One unsaved edit' : 'No unsaved edits'
  document.querySelector('#change-effect').textContent = state.candidate ? 'Data compatibility must be checked again.' : `Results remain tied to revision ${state.revision}.`
  document.querySelector('#stage-change').textContent = state.candidate ? 'Revert to revision 04' : 'Stage selected value'
  document.querySelector('#compose-status').textContent = state.draftReady ? (state.candidate ? 'Candidate 04-A is staged. Later results remain unavailable until its data check passes.' : 'No unsaved edits.') : 'Empty draft created. Add starter rules to continue.'
  document.querySelector('#compat-caption').textContent = state.candidate ? 'Required fields for candidate 04-A' : `Required fields for revision ${state.revision}`
  document.querySelector('#backtest-kicker').textContent = state.candidate ? 'Example run 119 · candidate 04-A · net of example charges' : `Example run 118 · revision ${state.revision} · net of example charges`
  renderRule()
  updateNavigation()
}

function loadPreset() {
  state.draftReady = true
  state.revision = '04'
  state.savedWindow = 15
  state.stagedWindow = 15
  state.candidate = false
  document.querySelector('#window-select').value = '15'
  resetDownstream()
  syncDraft()
  showView('compose')
}

function startEmpty() {
  state.draftReady = false
  state.revision = 'Draft'
  state.savedWindow = 15
  state.stagedWindow = 15
  state.candidate = false
  resetDownstream()
  syncDraft()
  showView('compose')
}

document.querySelector('[data-preset]').addEventListener('click', loadPreset)
document.querySelector('[data-new]').addEventListener('click', startEmpty)
document.querySelector('#load-preset').addEventListener('click', loadPreset)

document.querySelector('#window-select').addEventListener('change', (event) => {
  state.stagedWindow = Number(event.currentTarget.value)
  const changed = state.stagedWindow !== state.savedWindow
  document.querySelector('#stage-change').disabled = !changed
  document.querySelector('#change-title').textContent = changed ? 'Edit ready to stage' : 'No unsaved edits'
  document.querySelector('#proposed-revision').textContent = changed ? 'Candidate 04-A' : 'None'
  document.querySelector('#change-effect').textContent = changed ? 'Staging this value will make existing data checks stale.' : `Results remain tied to revision ${state.revision}.`
})

document.querySelector('#stage-change').addEventListener('click', () => {
  if (state.candidate) {
    state.stagedWindow = state.savedWindow
    state.candidate = false
    document.querySelector('#window-select').value = String(state.savedWindow)
  } else {
    state.candidate = true
  }
  resetDownstream()
  syncDraft()
})

document.querySelector('#replace-dataset').addEventListener('click', (event) => {
  state.compatibilityReady = true
  event.currentTarget.disabled = true
  event.currentTarget.textContent = 'Complete dataset selected'
  document.querySelector('#hdfc-row').classList.remove('blocked')
  document.querySelector('#hdfc-volume').textContent = '✓'
  document.querySelector('#hdfc-result').innerHTML = '<span class="state-badge good">Compatible</span>'
  document.querySelector('#compat-badge').className = 'state-badge good'
  document.querySelector('#compat-badge').textContent = 'All fields available'
  document.querySelector('#diagnosis-title').textContent = 'This scope can now be tested'
  document.querySelector('#diagnosis-copy').textContent = 'The complete example dataset supplies OHLCV for both equities. NIFTY supplies the OHLC prices required by the market filter.'
  document.querySelector('#resolution-copy').textContent = 'Run the scoped example backtest, then challenge the result before recording evidence.'
  document.querySelector('#compat-status').textContent = 'Compatibility passed for this draft and dataset.'
  document.querySelector('#scope-summary').textContent = '2 equities + 1 price-only index filter · compatible'
  document.querySelector('#to-backtest').disabled = false
  updateNavigation()
})

document.querySelector('#compare-toggle').addEventListener('click', (event) => {
  const panel = document.querySelector('#revision-compare')
  panel.hidden = !panel.hidden
  event.currentTarget.setAttribute('aria-expanded', String(!panel.hidden))
  event.currentTarget.textContent = panel.hidden ? 'Compare revisions' : 'Hide comparison'
})

document.querySelector('#save-evidence').addEventListener('click', (event) => {
  state.evidenceSaved = true
  event.currentTarget.disabled = true
  event.currentTarget.textContent = 'Evidence saved'
  document.querySelector('#evidence-status').textContent = 'Saved as example evidence record ER-118-04. Alert monitoring is now available.'
  document.querySelector('#to-monitor').disabled = false
  updateNavigation()
})

const evidence = {
  hdfc: { title: 'HDFCBANK range break', reason: 'The completed close crossed the saved opening-range high, volume exceeded its completed average, and the NIFTY price filter passed.', candle: 'HDFCBANK · 10:05 IST · completed 5m candle', decision: 'Revision 04 retained · evidence ER-118-04' },
  reliance: { title: 'RELIANCE confirmation pending', reason: 'Price crossed the range, but volume did not exceed its completed 20-bar average. No confirmed alert was produced.', candle: 'RELIANCE · 10:05 IST · completed 5m candle', decision: 'Condition withheld · evidence ER-118-04' },
}

document.querySelectorAll('[data-alert]').forEach((button) => button.addEventListener('click', () => {
  const item = evidence[button.dataset.alert]
  document.querySelector('#lineage-title').textContent = item.title
  document.querySelector('#lineage-body').innerHTML = `<p>${item.reason}</p><dl><dt>Rule</dt><dd>Opening range · Revision 04</dd><dt>Completed data</dt><dd>${item.candle}</dd><dt>Research decision</dt><dd>${item.decision}</dd></dl><details class="technical-details"><summary>Technical identifiers</summary><p>graph 7ac…91e · dataset c41…2bd</p></details>`
  document.querySelector('#lineage').focus()
}))

document.querySelector('#signin-form').addEventListener('submit', (event) => {
  event.preventDefault()
  document.querySelector('#account-button').textContent = 'A. Researcher'
  document.querySelector('#signin-status').textContent = 'Concept session opened. No credentials were sent.'
  showView('compose')
})

syncDraft()
const initial = location.hash.slice(1) || 'welcome'
showView(initial, false)
