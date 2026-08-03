import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { GraphStructureControls } from './GraphStructureControls'
import { CONTROL_DOCUMENT } from './graphControlTestFixture'

describe('GraphStructureControls', () => {
  it('renders native labelled structural selectors from server descriptors', () => {
    const document = {
      ...CONTROL_DOCUMENT,
      component_catalogue: [{
        identifier: 'math.abs', version: 1, display_name: 'Absolute',
        parameters: [], sockets: [],
      }],
      graph_sockets: [{
        instance_id: 'io_in' as const, identifier: 'close', display_name: 'Close',
        direction: 'output' as const, wire_type: { value: 'float' },
        has_default_source: false,
      }],
    }
    const html = renderToStaticMarkup(React.createElement(GraphStructureControls, {
      document, disabled: false, onSemantic: () => undefined,
    }))

    expect(html).toContain('Component and version')
    expect(html).toContain('Authored instance ID')
    expect(html).toContain('Add authored node')
    expect(html).toContain('Remove node and incident edges')
    expect(html).toContain('Source output socket')
    expect(html).toContain('Target input socket')
    expect(html).toContain('Connect typed sockets')
    expect(html).toContain('Existing semantic edge')
    expect(html).not.toContain('n_ema/n_internal')
  })
})
