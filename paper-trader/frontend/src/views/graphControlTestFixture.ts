import type { IrEditorDocument } from '../lib/api'

export const CONTROL_DOCUMENT: IrEditorDocument = {
  project_id: 'project.test', identifier: 'strategy.test', display_name: 'Test',
  draft_revision: 0, version: 1, content_address: 'sha256:test',
  authored_graph: {
    identifier: 'strategy.test', version: 1, display_name: 'Test',
    nodes: [{
      instance_id: 'n_ema', component: { identifier: 'indicator.ema', version: 1 },
      overrides: {},
    }],
    edges: [],
  },
  view: {
    identifier: 'strategy.test', version: 1, display_name: 'Test', warmup: 0,
    layers: 0, inputs: [], outputs: [], nodes: [], edges: [],
  },
  editable_nodes: [{
    instance_id: 'n_ema', component_identifier: 'indicator.ema',
    component_version: 1, parameters: [], sockets: [],
  }],
  component_catalogue: [], graph_sockets: [],
  layout: {
    graph_identifier: 'strategy.test', graph_version: 1, revision: 0,
    positions: [], groups: [],
  },
  command_receipt: null,
}
