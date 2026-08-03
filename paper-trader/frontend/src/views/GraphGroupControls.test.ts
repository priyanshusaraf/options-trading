import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { GraphGroupControls } from './GraphGroupControls'
import { CONTROL_DOCUMENT } from './graphControlTestFixture'

describe('GraphGroupControls', () => {
  it('renders closed group, membership, frame, and collapse controls', () => {
    const document = {
      ...CONTROL_DOCUMENT,
      layout: {
        ...CONTROL_DOCUMENT.layout,
        groups: [{
          identifier: 'g_signal', display_name: 'Signal',
          frame: { x: 10, y: 20, width: 300, height: 180 },
          collapsed: false, members: ['n_ema'],
        }],
      },
    }
    const html = renderToStaticMarkup(React.createElement(GraphGroupControls, {
      document, disabled: false, onPresentation: () => undefined,
    }))

    expect(html).toContain('Create visual group')
    expect(html).toContain('Rename visual group')
    expect(html).toContain('Remove visual group')
    expect(html).toContain('Authored group member')
    expect(html).toContain('Add member')
    expect(html).toContain('Remove member')
    expect(html).toContain('Frame width')
    expect(html).toContain('Collapse visual group')
  })
})
