import { chooseSelect } from '../test/select'
import { useEffect } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiError, type StrategyApi } from '../shell/api'
import type { CatalogueComponent, GraphSummary, Project, V2Draft, V2Presentation, VerifiedCatalogue } from '../shell/contracts'
import { StrategyBuilderWorkspace } from './StrategyBuilderWorkspace'

const flowMock = vi.hoisted(() => ({
  updateNodeInternals: vi.fn(),
  getViewport: vi.fn(() => ({ x: 0, y: 0, zoom: 1 })),
  setViewport: vi.fn().mockResolvedValue(true),
  navigation: {} as Record<string, unknown>,
  getNodes: vi.fn(() => [] as { id: string; measured: { width: number; height: number } }[]),
  screenToFlowPosition: vi.fn((point: { x: number; y: number }) => point),
  nodes: [] as readonly { id: string; position: { x: number; y: number } }[],
  onNodesChange: undefined as ((changes: readonly Record<string, unknown>[]) => void) | undefined,
  onNodeClick: undefined as ((event: unknown, node: any) => void) | undefined,
  onNodeDrag: undefined as ((event: unknown, node: any) => void) | undefined,
  onNodeDragStop: undefined as ((event: unknown, node: any) => void) | undefined,
  onPaneClick: undefined as (() => void) | undefined,
}))
vi.mock('@xyflow/react', async () => { const actual = await vi.importActual<typeof import('@xyflow/react')>('@xyflow/react'); return { ...actual,
  ReactFlow: ({ children, nodes, onInit, nodeTypes, onNodesChange, onNodeClick, onNodeDrag, onNodeDragStop, onPaneClick, panOnDrag, panActivationKeyCode, selectionOnDrag }: { panOnDrag?: boolean | number[]; panActivationKeyCode?: string; selectionOnDrag?: boolean; children: React.ReactNode; nodes: readonly Record<string, any>[]; onInit?: (instance: unknown) => void; nodeTypes: Record<string, React.ComponentType<any>>; onNodesChange?: (changes: readonly Record<string, unknown>[]) => void; onNodeClick?: (event: unknown, node: any) => void; onNodeDrag?: (event: unknown, node: any) => void; onNodeDragStop?: (event: unknown, node: any) => void; onPaneClick?: () => void }) => { flowMock.navigation = { panOnDrag, panActivationKeyCode, selectionOnDrag }; flowMock.nodes = nodes as typeof flowMock.nodes; flowMock.onNodesChange = onNodesChange; flowMock.onNodeClick = onNodeClick; flowMock.onNodeDrag = onNodeDrag; flowMock.onNodeDragStop = onNodeDragStop; flowMock.onPaneClick = onPaneClick; useEffect(() => { onInit?.({ screenToFlowPosition: flowMock.screenToFlowPosition, getNodes: flowMock.getNodes, getViewport: flowMock.getViewport, setViewport: flowMock.setViewport }) }, [onInit]); return <div data-testid="react-flow">{nodes.map((node) => { const NodeView = nodeTypes[String(node.type)]; return <NodeView key={String(node.id)} {...node} /> })}{children}</div> },
  useUpdateNodeInternals: () => flowMock.updateNodeInternals,
  Background: () => null, Controls: () => null, Handle: (props: { id: string; type: string }) => <span data-testid="node-port" data-port-id={props.id} data-port-type={props.type} />,
} })

const address = (value: string) => `sha256:${value.repeat(64).slice(0, 64)}`
const project: Project = { project_id: 'project.a', name: 'A', description: '', status: 'active' }
const graph: GraphSummary = { identifier: 'strategy.a', display_name: 'A', draft_revision: 0, current_version: null }
const output = { port_id: 'out', direction: 'output', semantic_flow: 'value', semantic_role: 'value', type_ref: { type_id: 'number', type_version: 1 }, shape: 'series' }
const input = { ...output, port_id: 'in', direction: 'input', connections: { cardinality: 'optional', min: 0, max: 1, assembly: 'single' }, default: null }
const component = (index: number, family: string, direction: 'source' | 'target'): CatalogueComponent => ({
  component_kind: 'LEAF',
  component_id: `logic.${direction}_${index}`, component_version: 2, component_address: address(String(index)), display_name: `${direction === 'source' ? 'Source' : 'Target'} ${index}`,
  visible_family: family, presentation_group_name: family, descriptor: { component_id: `logic.${direction}_${index}`, component_version: 2,
    ports: direction === 'source' ? [output] : [input, output], parameters: direction === 'target' ? { length: { type: 'int', default: 20, units: 'bars' } } : {} },
  help: { component_id: `logic.${direction}_${index}`, component_version: 2, implementation_binding: address('i'), semantic_kind: 'LOGICAL_OPERATION',
    description: 'Returns the reviewed logic result when inputs are valid.', semantic_text: 'Return the reviewed result.',
    sources: [{ source_record_id: 'strategy-os-type5-evaluator-v1', title: 'Strategy OS logic evaluator', authors_or_organization: 'Strategy OS', publication_or_version: 'First-party evaluator version 1', year: 2026, url: null, claim_scope: `Defines logic.${direction}_${index}.` }],
    customisation: { parameters: direction === 'target' ? [{ name: 'length', type: 'int', required: false, default: 20, enum: null, domain: { minimum: 1, maximum: 100 }, units: 'bars', serialization: 'canonical-json' }] : [], guidance: direction === 'target' ? 'Set only this authored parameter: length.' : 'This built-in has no parameters.', built_in_code_immutable: true, immutable_boundary: 'This is an immutable built-in. You can change only the listed parameters; you cannot edit its code here.' },
    availability: { status: 'AVAILABLE', authority: 'NONE', condition: 'Available within the declared research contract when required inputs are valid.' } },
  data_requirement: {}, availability: { status: 'AVAILABLE', authority: 'NONE', provider_support_verified: false, data_rights_verified: false, backtest_eligible: false },
})
const families = ['TYPE_4', 'TYPE_2', 'TYPE_3', 'TYPE_5', 'TYPE_1']
const catalogue: VerifiedCatalogue = { schema: 'strategy-os-verified-language-catalogue/1', registry_identity: address('r'), catalogue_identity: address('q'),
  groups: families.map((family, index) => ({ order: index + 1, visible_family: family, display_name: family, components: [component(index, family, index === 0 ? 'source' : 'target')] })) }
const graphDocument = (nodes: V2Draft['document']['nodes'], edges: V2Draft['document']['edges'] = []): V2Draft['document'] => ({ format_version: 2, strategy_id: graph.identifier, strategy_version: 1,
  metadata: { metadata_version: 1, name: 'A', description: '', tags: [] }, graph_inputs: [], graph_outputs: [], nodes, edges })
const source = { node_id: 'source', component: { component_id: 'logic.source_0', component_version: 2 }, parameters: {} }
const initial: V2Draft = { project_id: project.project_id, graph_identifier: graph.identifier, semantic_revision: 0, current_version: null, published_revision: null,
  document: graphDocument([source]), content_address: address('a'), graph_address: address('b') }
const presentation = (revision = 0): V2Presentation => ({ schema: 'strategy-os-v2-presentation-state/1', semantic_revision: revision ? 1 : 0, presentation_revision: revision,
  presentation: { positions: { source: { x: 0, y: 0 } }, groups: {}, viewport: { x: 0, y: 0, zoom: 1 }, selection: { nodes: [], edges: [], outputs: [] } },
  presentation_address: address('p'), orphaned_references: { positions: [], groups: [], selection_nodes: [], selection_edges: [], selection_outputs: [] }, executable_identity: false })
const semanticReceipt = (intent: 'EDIT' | 'UNDO' | 'REDO', base: number, result: number, commands: readonly Record<string, unknown>[], inverse: readonly Record<string, unknown>[]) => ({
  schema: 'strategy-os-v2-semantic-receipt/2' as const, commit_state: 'DRAFT_COMMITTED' as const, intent, base_semantic_revision: base, result_semantic_revision: result,
  base_content_address: address('a'), result_content_address: address('c'), base_graph_address: address('b'), result_graph_address: address('d'),
  forward_commands: commands, inverse_commands: inverse, receipt_address: address(String(result)),
})
const presentationReceipt = { schema: 'strategy-os-v2-presentation-receipt/1' as const, commit_state: 'PRESENTATION_COMMITTED' as const, intent: 'EDIT' as const,
  base_presentation_revision: 0, result_presentation_revision: 1, forward_commands: [{ command: 'set_position', node_id: 'logic_target_1', x: 280, y: 0 }],
  inverse_commands: [{ command: 'clear_position', node_id: 'logic_target_1' }], receipt_address: address('l') }

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})
async function openExplorer() {
  const button = await screen.findByRole('button', { name: 'Add component' })
  if (!document.querySelector('.component-explorer[open]')) { button.focus(); fireEvent.click(button) }
  return screen.findByLabelText('Search node library')
}
async function selectFirstNode() {
  await screen.findByLabelText('Strategy graph canvas')
  act(() => flowMock.onNodeClick?.({}, { id: flowMock.nodes[0]?.id }))
}
async function selectedField(name: string) {
  await screen.findByLabelText('Strategy graph canvas')
  if (!screen.queryByLabelText(name)) await selectFirstNode()
  return screen.findByLabelText(name)
}

beforeEach(() => { flowMock.setViewport.mockClear(); flowMock.getViewport.mockReturnValue({ x: 0, y: 0, zoom: 1 }); flowMock.getNodes.mockReset(); flowMock.getNodes.mockReturnValue([]); flowMock.screenToFlowPosition.mockReset(); flowMock.screenToFlowPosition.mockImplementation((point) => point); flowMock.onNodesChange = undefined; flowMock.onNodeClick = undefined; flowMock.onNodeDrag = undefined; flowMock.onNodeDragStop = undefined; flowMock.onPaneClick = undefined; vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 100, y: 50, top: 50, left: 100, right: 1100, bottom: 650, width: 1000, height: 600, toJSON: () => ({}) }) })
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('uses native Space and middle-button pan and keeps viewport controls out of graph edits', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await selectFirstNode()
  expect(flowMock.navigation).toEqual({ panOnDrag: [0, 1], panActivationKeyCode: 'Space', selectionOnDrag: false })
  const positions = flowMock.nodes.map((node) => node.position)
  fireEvent.keyDown(screen.getByLabelText('Strategy graph canvas'), { key: 'ArrowRight' })
  expect(flowMock.setViewport).toHaveBeenLastCalledWith({ x: 32, y: 0, zoom: 1 })
  fireEvent.keyDown(screen.getByLabelText('Strategy graph canvas'), { key: 'ArrowUp' })
  expect(flowMock.setViewport).toHaveBeenLastCalledWith({ x: 0, y: -32, zoom: 1 })
  fireEvent.keyDown(screen.getByRole('button', { name: 'Add component' }), { key: 'ArrowDown' })
  expect(screen.queryByRole('group', { name: 'Pan graph' })).not.toBeInTheDocument()
  expect(flowMock.setViewport).toHaveBeenCalledTimes(2)
  expect(flowMock.nodes.map((node) => node.position)).toEqual(positions)
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
})

it('colors all five families from component visible_family rather than group order', async () => {
  const nodes = catalogue.groups.flatMap((group) => group.components).map((item, index) => ({ node_id: `family_${index}`, component: { component_id: item.component_id, component_version: item.component_version }, parameters: {} }))
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue({ ...initial, document: graphDocument(nodes) }), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await selectFirstNode()
  expect([...document.querySelectorAll('.workstation-node')].map((node) => node.getAttribute('data-node-family'))).toEqual(families)
  for (const value of ['Execution', 'Indicators', 'Market structure', 'Data', 'Logic']) expect(screen.getByText(value, { selector: '.node-family-label' })).toBeInTheDocument()
})

it('keeps an unknown visible family neutral and labels it without guessing from its group', async () => {
  const unknown = { ...catalogue, groups: catalogue.groups.map((group, index) => index === 0 ? { ...group, components: [{ ...group.components[0], visible_family: 'FUTURE' }] } : group) }
  const api = { catalogue: vi.fn().mockResolvedValue(unknown), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  expect(await screen.findByText('Unclassified')).toBeInTheDocument()
  expect(document.querySelector('.workstation-node')).toHaveAttribute('data-node-family', 'UNKNOWN')
})

it('uses the five-family V2 catalogue and visibly stages add, keyboard connect, parameter and position commands', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await openExplorer()
  expect([...document.querySelectorAll('.component-explorer summary')].map((item) => item.firstChild?.textContent)).toEqual(['Data', 'Indicators', 'Market structure', 'Logic', 'Execution'])
  const search = screen.getByLabelText('Search node library'); fireEvent.change(search, { target: { value: 'Target 1' } }); fireEvent.keyDown(search, { key: 'Enter' })
  expect(await screen.findByRole('heading', { name: 'Target 1' })).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Stage typed connection' }))
  expect(screen.getByText('Indicators', { selector: '.node-family-label' }).closest('.workstation-node')).toHaveAttribute('data-node-family', 'TYPE_2')
  expect(screen.getByRole('button', { name: 'Disconnect Source 0 → Target 1' })).toBeInTheDocument(); fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  act(() => flowMock.onNodesChange?.([{ id: 'logic_target_1', type: 'position', position: { x: 24, y: 0 }, dragging: false }])); expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Stage node removal' })); await waitFor(() => expect(screen.getByLabelText('Strategy graph canvas')).toHaveFocus())
})

it.each(['Delete', 'Backspace'])('stages one selected-node removal with %s and restores focus', async (key) => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await selectFirstNode()
  fireEvent.keyDown(window, { key })
  await waitFor(() => expect(flowMock.nodes).toHaveLength(0))
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByLabelText('Strategy graph canvas')).toHaveFocus())
})

it.each([{ metaKey: true }, { ctrlKey: true }])('undoes and redoes connected node deletion with parameters and layout intact (%o)', async (modifier) => {
  const target = { node_id: 'target', component: { component_id: 'logic.target_1', component_version: 2 }, parameters: { length: 20 } }
  const draft = { ...initial, document: graphDocument([source, target], [{ edge_id: 'existing', source: { scope: 'node', node_id: 'source', port_id: 'out' }, target: { scope: 'node', node_id: 'target', port_id: 'in' }, binding: { kind: 'single' } }]) }
  const savedLayout = { ...presentation(), presentation: { ...presentation().presentation, positions: { target: { x: 80, y: 90 } } } }
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(draft), v2Presentation: vi.fn().mockResolvedValue(savedLayout), mutateV2: vi.fn() }
  render(<StrategyBuilderWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  await waitFor(() => expect(flowMock.nodes).toHaveLength(2))
  act(() => flowMock.onNodeClick?.({}, flowMock.nodes.find((node) => node.id === 'target')))
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  act(() => flowMock.onNodesChange?.([{ id: 'target', type: 'position', position: { x: 100, y: 120 }, dragging: false }]))
  const canvas = screen.getByLabelText('Strategy graph canvas')
  fireEvent.keyDown(canvas, { key: 'Delete' })
  await waitFor(() => expect(flowMock.nodes).toHaveLength(1))
  fireEvent.keyDown(canvas, { key: 'z', ...modifier })
  await waitFor(() => expect(flowMock.nodes).toHaveLength(2))
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(flowMock.nodes.find((node) => node.id === 'target')?.position).toEqual({ x: 100, y: 120 })
  expect(screen.getByRole('button', { name: 'Disconnect Source 0 → Target 1' })).toBeInTheDocument()
  fireEvent.keyDown(canvas, { key: 'z', ...modifier })
  await waitFor(() => expect(flowMock.nodes.find((node) => node.id === 'target')?.position).toEqual({ x: 80, y: 90 }))
  fireEvent.keyDown(canvas, { key: 'z', ...modifier })
  expect(screen.getByLabelText('Length')).toHaveValue('20')
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  for (let index = 0; index < 3; index += 1) fireEvent.keyDown(canvas, { key: 'Z', shiftKey: true, ...modifier })
  await waitFor(() => expect(flowMock.nodes).toHaveLength(1))
  expect(api.mutateV2).not.toHaveBeenCalled()
  expect(api.v2Draft).toHaveBeenCalledOnce()
})

it('undoes a staged addition and connection as separate complete edits and drops redo after new work', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const search = await openExplorer(); fireEvent.change(search, { target: { value: 'Target 1' } }); fireEvent.keyDown(search, { key: 'Enter' })
  fireEvent.click(screen.getByRole('button', { name: 'Stage typed connection' }))
  fireEvent.click(screen.getByRole('button', { name: 'Undo draft' }))
  expect(screen.queryByRole('button', { name: 'Disconnect Source 0 → Target 1' })).not.toBeInTheDocument()
  expect(flowMock.nodes).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Undo draft' }))
  await waitFor(() => expect(flowMock.nodes).toHaveLength(1))
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Redo draft' }))
  await waitFor(() => expect(flowMock.nodes).toHaveLength(2))
  expect(screen.getByRole('button', { name: 'Redo draft' })).toBeEnabled()
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '25' } }); fireEvent.blur(screen.getByLabelText('Length'))
  expect(screen.getByRole('button', { name: 'Redo draft' })).toBeDisabled()
  expect(screen.queryByText('Keyboard position')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Move node .* by 24 units/ })).not.toBeInTheDocument()
})

it('leaves native undo to inputs, editable content and open dialogs', async () => {
  const fixture = versionSaveFixture()
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  const field = await selectedField('Length')
  fireEvent.change(field, { target: { value: '30' } }); fireEvent.blur(field)
  const nativeUndo = (target: Element) => { const event = new KeyboardEvent('keydown', { key: 'z', metaKey: true, bubbles: true, cancelable: true }); fireEvent(target, event); expect(event.defaultPrevented).toBe(false) }
  nativeUndo(field)
  const editable = document.createElement('span'); editable.setAttribute('contenteditable', 'true'); document.querySelector('.builder-workstation')!.append(editable)
  nativeUndo(editable); editable.remove()
  fireEvent.click(screen.getByRole('button', { name: 'Help for Target 1' }))
  nativeUndo(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'Add component' }))
  nativeUndo(screen.getByLabelText('Search node library'))
  fireEvent.keyDown(screen.getByLabelText('Search node library'), { key: 'Escape' })
  nativeUndo(screen.getByRole('combobox', { name: 'Source node' }))
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
})

it('keeps local undo on the saved side of a draft acknowledgement and never reloads staged work', async () => {
  const fixture = versionSaveFixture()
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Apply draft' }))
  await screen.findByText('Draft applied.')
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '40' } }); fireEvent.blur(screen.getByLabelText('Length'))
  const canvas = screen.getByLabelText('Strategy graph canvas')
  fireEvent.keyDown(canvas, { key: 'z', metaKey: true })
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  fireEvent.keyDown(canvas, { key: 'z', metaKey: true })
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(fixture.client.v2Draft).toHaveBeenCalledTimes(2)
  fireEvent.keyDown(canvas, { key: 'Z', metaKey: true, shiftKey: true })
  expect(screen.getByLabelText('Length')).toHaveValue('40')
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
})

it('uses the saved receipt when undo follows a successful draft acknowledgement', async () => {
  const fixture = versionSaveFixture()
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Apply draft' }))
  await screen.findByText('Draft applied.')
  fireEvent.click(screen.getByRole('button', { name: 'Undo draft' }))
  await waitFor(() => expect(fixture.client.mutateV2).toHaveBeenCalledTimes(2))
  expect(fixture.client.mutateV2).toHaveBeenNthCalledWith(2,
    project.project_id, graph.identifier, 1, expect.any(Array), 'UNDO',
    expect.objectContaining({ intent: 'EDIT' }), expect.any(AbortSignal))
})

it('does not delete while editing, composing, repeating, modified, or using node help', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const search = await openExplorer()
  fireEvent.keyDown(search, { key: 'Delete' })
  for (const init of [{ key: 'Delete', repeat: true }, { key: 'Delete', ctrlKey: true }, { key: 'Backspace', altKey: true }, { key: 'Backspace', metaKey: true }, { key: 'Delete', isComposing: true }]) fireEvent.keyDown(window, init)
  expect(flowMock.nodes).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Help for Source 0' }))
  fireEvent.keyDown(window, { key: 'Delete' })
  expect(flowMock.nodes).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  const editable = document.createElement('div'); editable.setAttribute('contenteditable', 'true'); const child = document.createElement('span'); editable.append(child); document.body.append(editable)
  fireEvent.keyDown(child, { key: 'Backspace' })
  expect(flowMock.nodes).toHaveLength(1)
})

it('tracks every drag frame without snapping and stages only the final layout position', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await selectFirstNode()
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  act(() => flowMock.onNodesChange?.([{ id: 'source', type: 'position', position: { x: 13.25, y: 17.75 }, dragging: true }]))
  await waitFor(() => expect(flowMock.nodes[0]?.position).toEqual({ x: 13.25, y: 17.75 }))
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  act(() => flowMock.onNodesChange?.([{ id: 'source', type: 'position', position: { x: 26.5, y: 35.125 }, dragging: true }]))
  await waitFor(() => expect(flowMock.nodes[0]?.position).toEqual({ x: 26.5, y: 35.125 }))
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  act(() => flowMock.onNodesChange?.([{ id: 'source', type: 'position', position: { x: 31.75, y: 40.5 }, dragging: false }]))
  await waitFor(() => expect(flowMock.nodes[0]?.position).toEqual({ x: 31.75, y: 40.5 }))
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
})

it('renders one native help control per graph node and restores focus after Close and Escape', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const search = await openExplorer()
  expect(screen.getAllByRole('button', { name: /^Help for / })).toHaveLength(1)
  fireEvent.change(search, { target: { value: 'Target 1' } }); fireEvent.keyDown(search, { key: 'Enter' })
  await waitFor(() => expect(screen.getAllByRole('button', { name: /^Help for / })).toHaveLength(2))
  const sourceHelp = screen.getByRole('button', { name: 'Help for Source 0' }); fireEvent.click(sourceHelp)
  const dialog = screen.getByRole('dialog', { name: 'Source 0' }); expect(dialog).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Exact semantics' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Sources' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Parameters and customisation' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Availability' })).toBeInTheDocument()
  expect(dialog).toHaveTextContent('No parameters.')
  expect(dialog.textContent).not.toMatch(/sha256:[0-9a-f]{64}/i)
  const close = screen.getByRole('button', { name: 'Close' }); await waitFor(() => expect(close).toHaveFocus()); fireEvent.click(close); await waitFor(() => expect(sourceHelp).toHaveFocus())

  const targetHelp = screen.getByRole('button', { name: 'Help for Target 1' }); fireEvent.click(targetHelp)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus())
  expect(screen.getByRole('dialog', { name: 'Target 1' })).toHaveTextContent('length')
  fireEvent.keyDown(screen.getByRole('dialog', { name: 'Target 1' }), { key: 'Escape' })
  await waitFor(() => expect(targetHelp).toHaveFocus())
})

it('renders exact completed-candle OHLCV splitter help without exposing a raw hash', async () => {
  const base = component(0, 'TYPE_4', 'source')
  const ohlcv: CatalogueComponent = { ...base, component_id: 'analytical.ohlcv', display_name: 'OHLCV', descriptor: { ...base.descriptor, component_id: 'analytical.ohlcv' },
    help: { ...base.help, component_id: 'analytical.ohlcv', semantic_kind: 'FIELD_SPLITTER', description: 'Splits each fully completed candle into five named outputs: open, high, low, close and volume. It does not calculate an indicator.', semantic_text: 'Return separately named completed-bar open, high, low, close and volume series. No DataFrame hidden under a scalar value port.', sources: [{ ...base.help.sources[0], claim_scope: 'Defines the accepted analytical.ohlcv V2 formula and its stated validity boundary.' }] } }
  const ohlcvCatalogue: VerifiedCatalogue = { ...catalogue, groups: catalogue.groups.map((group, index) => index === 0 ? { ...group, components: [ohlcv] } : group) }
  const ohlcvDraft: V2Draft = { ...initial, document: graphDocument([{ ...source, component: { component_id: 'analytical.ohlcv', component_version: 2 } }]) }
  const api = { catalogue: vi.fn().mockResolvedValue(ohlcvCatalogue), v2Draft: vi.fn().mockResolvedValue(ohlcvDraft), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Help for OHLCV' }))
  const dialog = screen.getByRole('dialog', { name: 'OHLCV' })
  expect(dialog).toHaveTextContent('Splits each fully completed candle into five named outputs: open, high, low, close and volume. It does not calculate an indicator.')
  expect(dialog).toHaveTextContent('Return separately named completed-bar open, high, low, close and volume series.')
  expect(dialog.textContent).not.toMatch(/\bcanonical\b/i)
  expect(dialog.textContent).not.toMatch(/sha256:[0-9a-f]{64}/i)
})

it('keeps internal terminology out of rendered node copy and accessibility labels', async () => {
  const base = component(0, 'TYPE_4', 'source')
  const guarded: CatalogueComponent = { ...base, display_name: 'Canonical strategy node',
    help: { ...base.help,
      description: 'Reads a canonical dataset for a canonical strategy.',
      semantic_text: 'Return the canonical instrument from the canonical strategy graph.',
      sources: [{ ...base.help.sources[0], title: 'Canonical source', authors_or_organization: 'Canonical team', publication_or_version: 'Canonical release', claim_scope: 'Defines the canonical strategy.' }],
      customisation: { ...base.help.customisation, guidance: 'Use the canonical default.', immutable_boundary: 'The canonical built-in is fixed.' },
      availability: { ...base.help.availability, condition: 'Available with a canonical dataset.' } } }
  const guardedCatalogue: VerifiedCatalogue = { ...catalogue, groups: catalogue.groups.map((group, index) => index === 0
    ? { ...group, display_name: 'Canonical datasets', components: [guarded] } : group) }
  const api = { catalogue: vi.fn().mockResolvedValue(guardedCatalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  expect(JSON.stringify(guardedCatalogue)).toMatch(/\bcanonical\b/i)
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const help = await screen.findByRole('button', { name: /Help for strategy node/i })
  expect(document.body.textContent).not.toMatch(/\bcanonical\b/i)
  for (const element of document.querySelectorAll('[aria-label], [title]')) expect(`${element.getAttribute('aria-label') ?? ''} ${element.getAttribute('title') ?? ''}`).not.toMatch(/\bcanonical\b/i)
  fireEvent.click(help)
  expect(await screen.findByRole('dialog', { name: /strategy node/i })).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/\bcanonical\b/i)
  expect(screen.getAllByText(/historical dataset/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/Return the instrument from the strategy graph/i)).toBeInTheDocument()
})

it('executes V2 rollback validate, apply, sealed undo/redo, immutable publish and reload', async () => {
  let draft = initial; let layout = presentation(); let editReceipt = semanticReceipt('EDIT', 0, 1, [], [{ command: 'remove_node', node_id: 'logic_target_1' }]); let undoReceipt = semanticReceipt('UNDO', 1, 2, [], editReceipt.forward_commands)
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockImplementation(async () => draft), v2Presentation: vi.fn().mockImplementation(async () => layout),
    validateV2: vi.fn().mockResolvedValue({ ...semanticReceipt('EDIT', 0, 1, [], []), commit_state: 'DRY_RUN_ROLLED_BACK' }),
    mutateV2: vi.fn().mockImplementation(async (_p, _g, _base, commands, intent) => { if (intent === 'EDIT') { editReceipt = semanticReceipt('EDIT', 0, 1, commands, [{ command: 'remove_node', node_id: 'logic_target_1' }]); draft = { ...initial, semantic_revision: 1, document: graphDocument([source, { node_id: 'logic_target_1', component: { component_id: 'logic.target_1', component_version: 2 }, parameters: { length: 30 } }], [{ edge_id: 'edge', source: { scope: 'node', node_id: 'source', port_id: 'out' }, target: { scope: 'node', node_id: 'logic_target_1', port_id: 'in' }, binding: { kind: 'single' } }]), content_address: address('c'), graph_address: address('d') }; return editReceipt }
      if (intent === 'UNDO') { draft = { ...initial, semantic_revision: 2 }; undoReceipt = semanticReceipt('UNDO', 1, 2, commands, editReceipt.forward_commands); return undoReceipt }
      draft = { ...draft, semantic_revision: 3 }; return semanticReceipt('REDO', 2, 3, commands, editReceipt.inverse_commands) }),
    mutateV2Presentation: vi.fn().mockImplementation(async (_p, _g, semanticRevision) => { layout = { ...presentation(1), semantic_revision: semanticRevision }; return presentationReceipt }),
    publishV2: vi.fn().mockImplementation(async () => { const saved = draft; draft = { ...draft, current_version: 1, published_revision: draft.semantic_revision, content_address: address('9'), document: { ...draft.document, strategy_version: 2 } }; return { schema: 'strategy-os-v2-publish-receipt/1', project_id: project.project_id, graph_identifier: graph.identifier, graph_version: 1, semantic_revision: saved.semantic_revision, content_address: saved.content_address, graph_address: saved.graph_address, canonical_document: saved.document, receipt_address: address('z') } }),
  } as unknown as StrategyApi
  const published = vi.fn(); render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={published} />)
  const search = await openExplorer(); fireEvent.change(search, { target: { value: 'Target 1' } }); fireEvent.keyDown(search, { key: 'Enter' }); fireEvent.click(screen.getByRole('button', { name: 'Stage typed connection' })); fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Check strategy' })); const validation = await screen.findByText(/Strategy check completed. Nothing was saved/); await waitFor(() => expect(validation).toHaveFocus()); expect(api.mutateV2).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Apply draft' })); expect(await screen.findByText(/Draft applied/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Undo draft' })); expect(await screen.findByText(/Undo restored/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Redo draft' })); expect(await screen.findByText(/Redo restored/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save version' })); expect(await screen.findByText(/Saved strategy version 1/)).toBeInTheDocument(); expect(published).toHaveBeenCalledWith(expect.objectContaining({ version: 1 })); fireEvent.click(screen.getByRole('button', { name: 'Reload' })); await screen.findByLabelText('Strategy graph canvas'); expect(screen.queryByText(draft.content_address)).not.toBeInTheDocument(); expect(flowMock.nodes).toHaveLength(draft.document.nodes.length)
})

it('places new cards at the converted visible centre, offsets collisions, and refuses a zero-size canvas', async () => {
  flowMock.screenToFlowPosition.mockImplementation(({ x, y }) => ({ x: (x - 40) / 1.8, y: (y + 20) / 1.8 }))
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const search = await openExplorer(); fireEvent.change(search, { target: { value: 'Target 1' } }); fireEvent.keyDown(search, { key: 'Enter' })
  expect(flowMock.screenToFlowPosition).toHaveBeenCalledWith({ x: 600, y: 350 }); await waitFor(() => expect(flowMock.nodes.find((node) => node.id === 'logic_target_1')?.position).toEqual({ x: (600 - 40) / 1.8 - 115, y: (350 + 20) / 1.8 - 42.5 }))
  await openExplorer(); fireEvent.keyDown(search, { key: 'Enter' }); await waitFor(() => expect(flowMock.nodes.find((node) => node.id === 'logic_target_1_2')?.position.x).toBeCloseTo((600 - 40) / 1.8 - 115 + 24))
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }); await openExplorer(); fireEvent.keyDown(search, { key: 'Enter' }); expect(await screen.findByText(/canvas is not ready/)).toBeInTheDocument(); expect(flowMock.nodes.some((node) => node.id === 'logic_target_1_3')).toBe(false)
})

it('opens the component explorer with Shift+A, closes with Escape and restores focus', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  const canvas = await screen.findByLabelText('Strategy graph canvas'); canvas.focus()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Component settings')).not.toBeInTheDocument()
  fireEvent.keyDown(canvas, { key: 'A', shiftKey: true })
  const dialog = await screen.findByRole('dialog', { name: 'Add component' }), search = screen.getByLabelText('Search node library')
  expect(search).toHaveFocus(); fireEvent.change(search, { target: { value: 'Target' } })
  fireEvent(dialog, new Event('cancel', { cancelable: true }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument(); expect(canvas).toHaveFocus()
  for (const init of [{ key: 'A', shiftKey: true, repeat: true }, { key: 'A', shiftKey: true, ctrlKey: true }, { key: 'A', shiftKey: true, altKey: true }, { key: 'A', shiftKey: true, metaKey: true }]) { fireEvent.keyDown(canvas, init); expect(screen.queryByRole('dialog')).not.toBeInTheDocument() }
  await openExplorer(); expect(search).toHaveValue('Target')
})

it('keeps explorer search state and blocks behind-dialog deletion while selecting a component', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await selectFirstNode(); const search = await openExplorer()
  fireEvent.change(search, { target: { value: 'Target' } })
  fireEvent.keyDown(screen.getByRole('button', { name: 'Close component explorer' }), { key: 'Delete' })
  expect(flowMock.nodes).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Close component explorer' }))
  await openExplorer(); expect(search).toHaveValue('Target')
  fireEvent.keyDown(search, { key: 'Enter' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Component settings')).toHaveTextContent('Target 1')
  act(() => flowMock.onPaneClick?.())
  expect(screen.queryByLabelText('Component settings')).not.toBeInTheDocument()
  expect(flowMock.nodes).toHaveLength(2)
})

it('leaves nested and composed-path editable Shift+A events untouched', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />); await openExplorer()
  fireEvent.click(screen.getByRole('button', { name: 'Close component explorer' })); const root = screen.getByRole('heading', { name: 'Build strategy' }).closest('section')!
  const contenteditable = document.createElement('div'); contenteditable.setAttribute('contenteditable', 'true'); const contenteditableChild = document.createElement('span'); contenteditable.append(contenteditableChild); root.append(contenteditable)
  const roleTextbox = document.createElement('div'); roleTextbox.setAttribute('role', 'textbox'); const roleChild = document.createElement('span'); roleTextbox.append(roleChild); root.append(roleTextbox)
  for (const target of [contenteditableChild, roleChild]) { const event = new KeyboardEvent('keydown', { key: 'A', shiftKey: true, bubbles: true, cancelable: true }); target.dispatchEvent(event); expect(event.defaultPrevented).toBe(false); expect(screen.getByRole('button', { name: 'Add component' })).toBeInTheDocument() }
  const shadowHost = document.createElement('div'); root.append(shadowHost); const shadow = shadowHost.attachShadow({ mode: 'open' }); const shadowEditable = document.createElement('div'); shadowEditable.setAttribute('contenteditable', 'true'); const shadowChild = document.createElement('span'); shadowEditable.append(shadowChild); shadow.append(shadowEditable)
  const shadowEvent = new KeyboardEvent('keydown', { key: 'A', shiftKey: true, bubbles: true, cancelable: true, composed: true }); shadowChild.dispatchEvent(shadowEvent); expect(shadowEvent.defaultPrevented).toBe(false); expect(screen.getByRole('button', { name: 'Add component' })).toBeInTheDocument()
  const explicitlyFalse = document.createElement('span'); explicitlyFalse.setAttribute('contenteditable', 'false'); root.append(explicitlyFalse); const ordinaryEvent = new KeyboardEvent('keydown', { key: 'A', shiftKey: true, bubbles: true, cancelable: true }); explicitlyFalse.dispatchEvent(ordinaryEvent); expect(ordinaryEvent.defaultPrevented).toBe(true)
})

it('shows settings only for selection and never renders transport identities or a technical dump', async () => {
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(initial), v2Presentation: vi.fn().mockResolvedValue(presentation()) } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await screen.findByLabelText('Strategy graph canvas')
  expect(screen.queryByLabelText('Component settings')).not.toBeInTheDocument()
  await selectFirstNode()
  expect(screen.getByLabelText('Component settings')).toBeInTheDocument()
  expect(screen.queryByLabelText(/^X$|^Y$/)).not.toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/sha256:|Semantic receipt|Presentation receipt|Technical details|logic.source_0/)
  fireEvent.keyDown(screen.getByLabelText('Component settings'), { key: 'Escape' })
  expect(screen.queryByLabelText('Component settings')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Strategy graph canvas')).toHaveFocus()
})

it.each([[300, 450, 1500], [600, 900, 2500]])('keeps %i nodes and %i edges interactive within the desktop budget', async (nodeCount, edgeCount, budget) => {
  const nodes = Array.from({ length: nodeCount }, (_, index) => ({ node_id: `node_${index}`, component: { component_id: 'logic.source_0', component_version: 2 }, parameters: {} }))
  const edges = Array.from({ length: edgeCount }, (_, index) => ({ edge_id: `edge_${index}`, source: { scope: 'node', node_id: `node_${index % nodeCount}`, port_id: 'out' }, target: { scope: 'node', node_id: `node_${(index + 1) % nodeCount}`, port_id: 'in' }, binding: { kind: 'single' } }))
  const large = { ...initial, document: graphDocument(nodes, edges) }; const positions = Object.fromEntries(nodes.map((node, index) => [node.node_id, { x: (index % 20) * 220, y: Math.floor(index / 20) * 120 }]))
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(large), v2Presentation: vi.fn().mockResolvedValue({ ...presentation(), presentation: { ...presentation().presentation, positions } }) } as unknown as StrategyApi
  const started = performance.now(); render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />); await waitFor(() => expect(document.querySelectorAll('.workstation-node')).toHaveLength(nodeCount), { timeout: budget }); const elapsed = performance.now() - started
  expect(elapsed).toBeLessThan(budget); act(() => flowMock.onNodeClick?.({}, { id: 'node_99' })); expect(screen.getByLabelText('Component settings')).toHaveTextContent('Source 0'); console.info(JSON.stringify({ benchmark: 'v2-editor', nodeCount, edgeCount, interactive_ms: elapsed }))
})

it.each(['strategy.trend_impulse_v3', 'strategy.expanding_z_v4_pine'])('opens copied %s parameters and keeps an edit after reload', async (componentId) => {
  const values = componentId.endsWith('v3') ? { ema_length: 50, z_length: 50, slope_lookback: 5, entry_z: 1.0 }
    : { ema_length: 50, z_length: 50, adapt_length: 200, atr_length: 14, slope_lookback: 5, entry_pct: 65.0, exit_pct: 35.0, min_abs_z: 0.6, min_drift_atr: 0.08, max_signal_atr: 2.75, require_expansion: true, allow_reexpansion: true, use_absz_contraction_exit: false, exit_on_drift_flip: true, exit_on_ema_cross: true }
  const parameters = Object.fromEntries(Object.entries(values).map(([name, value]) => [name, {
    type: typeof value === 'boolean' ? 'bool' : name.endsWith('length') || name.endsWith('lookback') ? 'int' : 'float',
    required: true, default: null, enum: null, domain: typeof value === 'boolean' ? null : { minimum: -10, maximum: 4096 }, units: 'value', serialization: 'canonical-json',
  }]))
  const base = component(1, 'TYPE_2', 'target')
  const compound: CatalogueComponent = { ...base, component_kind: 'COMPOUND', component_id: componentId, component_version: 1, display_name: componentId,
    descriptor: { component_id: componentId, component_version: 1, ports: [input, ...['longEntry', 'shortEntry', 'longExit', 'shortExit'].map((port_id) => ({ ...output, port_id }))], parameters,
      compound: { body: { graph_inputs: [], graph_outputs: [], nodes: [], edges: [] }, parameter_bindings: [] } }, data_requirement: null,
    help: { ...base.help, component_id: componentId, component_version: 1, implementation_binding: null,
      composition_binding: { component_address: base.component_address, registry_identity: catalogue.registry_identity },
      semantic_kind: 'MATHEMATICAL_FORMULA', description: 'An immutable compound recipe with editable authored parameters.' } }
  const nextCatalogue: VerifiedCatalogue = { ...catalogue, schema: 'strategy-os-verified-language-catalogue/2', groups: catalogue.groups.map((group, index) => index === 1 ? { ...group, components: [...group.components, compound] } : group) }
  let draft: V2Draft = { ...initial, document: graphDocument([{ node_id: 'rules', component: { component_id: componentId, component_version: 1 }, parameters: values }]) }
  const mutateV2 = vi.fn(async (_project: string, _graph: string, revision: number, commands: readonly Record<string, unknown>[]) => {
    const changed = { ...values, ema_length: commands[0].value as number }
    draft = { ...draft, semantic_revision: revision + 1, content_address: address('c'), graph_address: address('d'), document: graphDocument([{ node_id: 'rules', component: { component_id: componentId, component_version: 1 }, parameters: changed }]) }
    return semanticReceipt('EDIT', revision, revision + 1, commands, [])
  })
  const api = { catalogue: vi.fn().mockResolvedValue(nextCatalogue), v2Draft: vi.fn(async () => draft), v2Presentation: vi.fn().mockResolvedValue(presentation()), mutateV2 } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  expect(await selectedField('Ema Length')).toHaveValue('50')
  const card = screen.getByRole('button', { name: `Help for ${componentId}` }).closest('.workstation-node')!
  expect(card.querySelectorAll('.workstation-port-row')).toHaveLength(4)
  expect(card.querySelectorAll('[data-testid="node-port"]')).toHaveLength(5)
  expect(card.textContent).toContain('Long Entry')
  expect(card.textContent).not.toContain('Strategy node')
  expect(flowMock.updateNodeInternals).toHaveBeenCalledWith('rules')

  fireEvent.click(screen.getByRole('button', { name: `Help for ${componentId}` }))
  expect(await screen.findByText('An immutable compound recipe with editable authored parameters.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^Close$/ }))
  fireEvent.change(screen.getByLabelText('Ema Length'), { target: { value: '20' } }); fireEvent.blur(screen.getByLabelText('Ema Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Apply draft' }))
  expect(await screen.findByText(/Draft applied/)).toBeInTheDocument()
  expect(mutateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 0, [{ command: 'set_parameter', node_id: 'rules', parameter_id: 'ema_length', value: 20 }], 'EDIT', null, expect.any(AbortSignal))
  fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
  expect(await selectedField('Ema Length')).toHaveValue('20')
})

it('arranges measured tall nodes with space between rows without saving strategy changes', async () => {
  const nodes = Array.from({ length: 7 }, (_, index) => ({ ...initial.document.nodes[0], node_id: `n_${index}` }))
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue({ ...initial, document: { ...initial.document, nodes, edges: [] } }), v2Presentation: vi.fn().mockResolvedValue(presentation()), mutateV2: vi.fn(), mutateV2Presentation: vi.fn() } as unknown as StrategyApi
  flowMock.getNodes.mockReturnValue([{ id: 'n_0', measured: { width: 280, height: 360 } }])
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Arrange' }))
  await waitFor(() => expect(flowMock.nodes.find((node) => node.id === 'n_6')?.position).toEqual({ x: 0, y: 400 }))
  expect(flowMock.nodes.find((node) => node.id === 'n_1')?.position).toEqual({ x: 320, y: 0 })
  expect(api.mutateV2).not.toHaveBeenCalled()
  expect(api.mutateV2Presentation).not.toHaveBeenCalled()
})


import { ResearchSettings } from './ResearchSettings'
it('saves only explicitly edited strategy overrides and retains them when disabled', async () => {
  const defaults = { research_capital: 100000, min_trades: 10, n_folds: 4, seed: 0, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const revision = { owner_id: 'owner.a', graph_identifier: graph.identifier, revision: 0, enabled: true, values: {}, content_address: address('a') }
  const saveResearchSettings = vi.fn().mockResolvedValue({ ...revision, revision: 1, enabled: true, values: { n_folds: 8 } })
  const api = { strategyResearchSettings: vi.fn().mockResolvedValue({ workspace: { ...revision, graph_identifier: null, values: defaults }, strategy: revision, values: defaults, sources: {} }), saveResearchSettings } as unknown as StrategyApi
  render(<ResearchSettings api={api} strategy={{ projectId: project.project_id, graphId: graph.identifier }} />)
  const folds = await screen.findByLabelText('Walk-forward folds')
  await waitFor(() => expect(folds).toHaveValue(4))
  expect(folds).toBeDisabled()
  fireEvent.click(screen.getByLabelText('Use strategy overrides'))
  fireEvent.change(folds, { target: { value: '8' } })
  expect(screen.getByLabelText('Walk-forward folds')).toHaveValue(8)
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await screen.findByText(/Settings saved/)
  expect(saveResearchSettings).toHaveBeenLastCalledWith(expect.objectContaining({ expected_revision: 0, values: { n_folds: 8 } }), expect.any(AbortSignal), { projectId: project.project_id, graphId: graph.identifier, enabled: true })
  fireEvent.click(screen.getByLabelText('Use strategy overrides'))
  expect(folds).toHaveValue(4)
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() => expect(saveResearchSettings).toHaveBeenCalledTimes(2))
  expect(saveResearchSettings).toHaveBeenLastCalledWith(expect.objectContaining({ expected_revision: 1, values: { n_folds: 8 } }), expect.any(AbortSignal), expect.objectContaining({ enabled: false }))
})

it('keeps settings input and request identity when retrying an uncertain save', async () => {
  const values = { research_capital: 100000, min_trades: 10, n_folds: 4, seed: 0, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const revision = { owner_id: 'owner.a', graph_identifier: null, revision: 0, enabled: true, values, content_address: address('a') }
  const saveResearchSettings = vi.fn().mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValue({ ...revision, revision: 1, values: { ...values, n_folds: 7 } })
  const api = { workspaceResearchSettings: vi.fn().mockResolvedValue(revision), saveResearchSettings } as unknown as StrategyApi
  render(<ResearchSettings api={api} />)
  const folds = await screen.findByLabelText('Walk-forward folds')
  await waitFor(() => expect(folds).toHaveValue(4))
  fireEvent.change(folds, { target: { value: '7' } })
  expect(screen.getByLabelText('Minimum profitable folds (%)')).toHaveValue(60)
  fireEvent.change(screen.getByLabelText('Minimum profitable folds (%)'), { target: { value: '75' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save settings' })).toBeEnabled())
  expect(folds).toHaveValue(7)
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await screen.findByText(/Settings saved/)
  expect(saveResearchSettings).toHaveBeenCalledTimes(2)
  expect(saveResearchSettings.mock.calls[0][0].values.min_positive_fold_frac).toBe(.75)
  expect(saveResearchSettings.mock.calls[0][0]).toEqual(saveResearchSettings.mock.calls[1][0])
})


it('retries an unavailable settings read and clears one override without replacing inherited values', async () => {
  const defaults = { research_capital: 100000, min_trades: 10, n_folds: 4, seed: 0, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const revision = { owner_id: 'owner.a', graph_identifier: graph.identifier, revision: 1, enabled: true, values: { n_folds: 8 }, content_address: address('a') }
  const client = { strategyResearchSettings: vi.fn().mockRejectedValueOnce(new Error('Settings unavailable')).mockResolvedValue({ workspace: { ...revision, graph_identifier: null, values: defaults }, strategy: revision }),
    saveResearchSettings: vi.fn().mockResolvedValue({ ...revision, revision: 2, values: {} }) } as unknown as StrategyApi
  render(<ResearchSettings api={client} strategy={{ projectId: project.project_id, graphId: graph.identifier }} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Reload settings' })).toBeEnabled())
  expect(screen.getByRole('button', { name: 'Save settings' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Reload settings' }))
  await waitFor(() => expect(screen.getByLabelText('Walk-forward folds')).toHaveValue(8))
  fireEvent.click(screen.getByRole('button', { name: 'Use workspace value' }))
  expect(screen.getByLabelText('Walk-forward folds')).toHaveValue(4)
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await screen.findByText(/Settings saved/)
  expect(client.saveResearchSettings).toHaveBeenCalledWith(expect.objectContaining({ expected_revision: 1, values: {} }), expect.any(AbortSignal), expect.objectContaining({ enabled: true }))
})


function versionSaveFixture() {
  const node = { node_id: 'target', component: { component_id: 'logic.target_1', component_version: 2 }, parameters: { length: 20 } }
  let draft: V2Draft = { ...initial, document: graphDocument([node]) }
  let layout = presentation()
  let immutable = draft
  const client = {
    catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn(async () => draft), v2Presentation: vi.fn(async () => layout),
    mutateV2: vi.fn(async (_project, _graph, base, commands) => {
      const previous = draft
      draft = { ...draft, semantic_revision: base + 1, content_address: address('c'), graph_address: address('d'),
        document: { ...graphDocument([{ ...node, parameters: { length: commands.at(-1).value } }]), strategy_version: (draft.current_version ?? 0) + 1 } }
      return { ...semanticReceipt('EDIT', base, base + 1, commands, []), base_content_address: previous.content_address, base_graph_address: previous.graph_address }
    }),
    mutateV2Presentation: vi.fn(async (_project, _graph, revision, base, commands) => {
      layout = { ...layout, semantic_revision: revision, presentation_revision: base + 1 }
      return { ...presentationReceipt, base_presentation_revision: base, result_presentation_revision: base + 1, forward_commands: commands }
    }),
    v2Version: vi.fn(async () => ({ format_version: 2, graph_identifier: graph.identifier, graph_version: immutable.document.strategy_version, content_address: immutable.content_address, graph_address: immutable.graph_address, document: immutable.document })),
    publishV2: vi.fn(async (_project, _graph, revision) => {
      immutable = draft
      const version = (draft.current_version ?? 0) + 1
      draft = { ...draft, current_version: version, published_revision: revision, content_address: address('9'), document: { ...draft.document, strategy_version: version + 1 } }
      return { schema: 'strategy-os-v2-publish-receipt/1', project_id: project.project_id, graph_identifier: graph.identifier,
        graph_version: version, semantic_revision: revision, content_address: immutable.content_address, graph_address: immutable.graph_address,
        canonical_document: immutable.document, receipt_address: address('e') }
    }),
  }
  return { client, current: () => draft, setDraft: (next: V2Draft) => { draft = next } }
}

it('saves a staged parameter before publishing the exact returned revision', async () => {
  const { client } = versionSaveFixture(), published = vi.fn()
  render(<StrategyBuilderWorkspace api={client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } })
  fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalled())
  expect(client.mutateV2).toHaveBeenCalledOnce()
  expect(client.publishV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 1, null, expect.any(AbortSignal))
  expect(published).toHaveBeenCalledWith(expect.objectContaining({ content_address: address('c') }))
})


it('saves an untouched draft version without inventing an edit', async () => {
  const { client } = versionSaveFixture(), published = vi.fn()
  render(<StrategyBuilderWorkspace api={client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  await selectedField('Length')
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(client.mutateV2).not.toHaveBeenCalled()
  expect(client.publishV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 0, null, expect.any(AbortSignal))
})

it('retries only layout after the semantic batch was acknowledged', async () => {
  const { ApiError } = await import('../shell/api')
  const { client } = versionSaveFixture(), published = vi.fn()
  client.mutateV2Presentation.mockRejectedValueOnce(new ApiError('input', 'Layout rejected'))
  render(<StrategyBuilderWorkspace api={client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Arrange' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/The layout was not saved/)
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  expect(client.publishV2).not.toHaveBeenCalled()
  fireEvent.keyDown(screen.getByLabelText('Strategy graph canvas'), { key: 'z', metaKey: true })
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(client.mutateV2).toHaveBeenCalledOnce()
  fireEvent.keyDown(screen.getByLabelText('Strategy graph canvas'), { key: 'Z', metaKey: true, shiftKey: true })
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(client.mutateV2).toHaveBeenCalledOnce()
  expect(client.mutateV2Presentation).toHaveBeenCalledTimes(2)
  expect(await screen.findByText('Draft saved')).toBeInTheDocument()
  expect(client.mutateV2Presentation.mock.calls[1][2]).toBe(1)
  expect(client.publishV2.mock.calls[0][2]).toBe(1)
})

it('retains edits and permits retry when receipt sealing refuses before the draft write', async () => {
  const { ApiError } = await import('../shell/api')
  const fixture = versionSaveFixture(), published = vi.fn()
  fixture.client.mutateV2.mockRejectedValueOnce(new ApiError('server', 'Service unavailable', { code: 'RECEIPT_SEAL_UNAVAILABLE', message: 'Internal configuration detail' }))
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('The server cannot save edits until the workspace configuration is fixed. Your changes are retained. Contact the workspace administrator, then retry saving.')
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  expect(screen.queryByText(/Save status is uncertain|Internal configuration detail/)).not.toBeInTheDocument()
  expect(fixture.current().semantic_revision).toBe(0)
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Apply draft' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('Saved strategy version 1.')
  expect(fixture.client.mutateV2).toHaveBeenCalledTimes(2)
  expect(fixture.client.mutateV2.mock.calls[0].slice(0, 4)).toEqual(fixture.client.mutateV2.mock.calls[1].slice(0, 4))
  expect(published).toHaveBeenCalledOnce()
})

it.each(['layout', 'readback', 'publish', 'published'])('does not infer an unwritten draft from a receipt refusal during %s', async (phase) => {
  const { ApiError } = await import('../shell/api')
  const fixture = versionSaveFixture()
  const refusal = new ApiError('server', 'Service unavailable', { code: 'RECEIPT_SEAL_UNAVAILABLE', message: 'Configuration unavailable' })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  if (phase === 'layout') {
    fireEvent.click(screen.getByRole('button', { name: 'Arrange' }))
    fixture.client.mutateV2Presentation.mockRejectedValueOnce(refusal)
  } else if (phase === 'publish') fixture.client.publishV2.mockRejectedValueOnce(refusal)
  else if (phase === 'readback') fixture.client.v2Draft.mockRejectedValueOnce(refusal)
  else fixture.client.v2Draft.mockImplementationOnce(async () => fixture.current()).mockRejectedValueOnce(refusal)
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(phase === 'published' ? /Version 1 is saved. Reload/ : /Save status is uncertain/)
  expect(screen.queryByText(/The server cannot save edits until/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(fixture.current().semantic_revision).toBe(1)
})

it.each(['network', 'server'])('retains intent and blocks repetition after a committed edit loses its response (%s)', async (failure) => {
  const { ApiError } = await import('../shell/api')
  const fixture = versionSaveFixture(), original = fixture.client.mutateV2.getMockImplementation()!
  fixture.client.mutateV2.mockImplementationOnce(async (...args) => { await original(...args); throw failure === 'network' ? new Error('Response lost') : new ApiError('server', 'Response lost', { code: 'UNKNOWN_SAVE_FAILURE', message: 'Response lost' }) })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/Save status is uncertain/)
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Apply draft' })).toBeDisabled()
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Discard staged changes and reload' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save version' })).toBeEnabled())
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('Saved strategy version 1.')
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
})

it.each([{ semantic_revision: 2 }, { content_address: address('f') }, { graph_address: address('f') }, { current_version: 1 }])('refuses changed readback facts instead of publishing another editor’s rules %#', async (change) => {
  const fixture = versionSaveFixture(), original = fixture.client.mutateV2.getMockImplementation()!
  fixture.client.mutateV2.mockImplementationOnce(async (...args) => {
    const receipt = await original(...args)
    fixture.setDraft({ ...fixture.current(), ...change })
    return receipt
  })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/saved draft changed during this save/)
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(screen.getByLabelText('Length')).toHaveValue('30')
})

it('retries publication of the exact saved revision without replaying draft edits', async () => {
  const { ApiError } = await import('../shell/api')
  const { client } = versionSaveFixture(), published = vi.fn()
  client.publishV2.mockRejectedValueOnce(new ApiError('input', 'Version unavailable'))
  render(<StrategyBuilderWorkspace api={client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/draft is saved, but the version was not saved/)
  expect(published).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(client.mutateV2).toHaveBeenCalledOnce()
  expect(client.publishV2.mock.calls.map((call) => call[2])).toEqual([1, 1])
})

it('does not save an older parameter when the visible edit is invalid', async () => {
  const { client } = versionSaveFixture()
  render(<StrategyBuilderWorkspace api={client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: 'invalid' } }); fireEvent.blur(screen.getByLabelText('Length'))
  expect(screen.getByLabelText('Length')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(client.publishV2).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  expect(screen.getByRole('button', { name: 'Save version' })).toBeEnabled()
})

it('saves edits to an already published draft as the next version', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  fixture.setDraft({ ...fixture.current(), current_version: 1, published_revision: 0, document: { ...fixture.current().document, strategy_version: 2 } })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 1 }} onPublished={published} />)
  await selectedField('Length')
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  expect(screen.getByRole('button', { name: 'Save version' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('Saved strategy version 2.')
  expect(fixture.client.publishV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 1, 1, expect.any(AbortSignal))
  expect(published).toHaveBeenCalledWith(expect.objectContaining({ version: 2, content_address: address('c') }))
})

it('recovers an uncertain publication from the immutable row, not the advanced draft hash', async () => {
  const fixture = versionSaveFixture(), published = vi.fn(), original = fixture.client.publishV2.getMockImplementation()!
  fixture.client.publishV2.mockImplementationOnce(async (...args) => { await original(...args); throw new Error('Publication response lost') })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/Save status is uncertain/)
  expect(published).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(fixture.client.v2Version).toHaveBeenCalledWith(project.project_id, graph.identifier, 1, expect.any(AbortSignal))
  expect(published).toHaveBeenCalledWith(expect.objectContaining({ content_address: address('c') }))
  expect(fixture.current().content_address).toBe(address('9'))
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
})

it('does not start publication after the saving editor unmounts', async () => {
  const fixture = versionSaveFixture(), original = fixture.client.mutateV2.getMockImplementation()!
  let finish!: () => void
  fixture.client.mutateV2.mockImplementationOnce(async (...args) => { await new Promise<void>((resolve) => { finish = resolve }); return original(...args) })
  const view = render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  expect(screen.getByRole('heading', { name: 'Build strategy', hidden: true }).closest('section')).toHaveAttribute('inert')
  fireEvent.keyDown(window, { key: 'Delete' })
  expect(flowMock.nodes).toHaveLength(1)
  view.unmount(); await act(async () => finish())
  expect((fixture.client.mutateV2.mock.calls[0].at(-1) as AbortSignal).aborted).toBe(true)
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
})

it('keeps the published rules and cleared stages through the parent refresh callback', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  const view = render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  published.mockImplementation((saved) => view.rerender(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: saved.version, draft_revision: 1 }} onPublished={published} />))
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('Saved strategy version 1.')
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByText('Draft saved')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce(); expect(fixture.client.publishV2).toHaveBeenCalledOnce()
})

it('keeps an acknowledged publication successful if its following draft refresh fails', async () => {
  const fixture = versionSaveFixture(), published = vi.fn(), read = fixture.client.v2Draft.getMockImplementation()!
  fixture.client.v2Draft.mockImplementationOnce(read).mockImplementationOnce(read).mockRejectedValueOnce(new Error('Read unavailable'))
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/Version 1 is saved. Reload to refresh/)
  expect(published).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
  await selectedField('Length')
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
  expect(fixture.client.v2Version).not.toHaveBeenCalled() // the verified receipt already identifies the version
})

it('saves layout without publishing a duplicate unchanged version', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  fixture.setDraft({ ...fixture.current(), current_version: 1, published_revision: 0, document: { ...fixture.current().document, strategy_version: 2 } })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 1 }} onPublished={published} />)
  await selectedField('Length'); fireEvent.click(screen.getByRole('button', { name: 'Arrange' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText('Layout saved. The strategy version is unchanged.')
  expect(fixture.client.mutateV2).not.toHaveBeenCalled(); expect(fixture.client.publishV2).not.toHaveBeenCalled()
  expect(fixture.client.mutateV2Presentation).toHaveBeenCalledOnce()
})

it('refuses a dry-run semantic receipt as proof of a saved draft', async () => {
  const fixture = versionSaveFixture(), original = fixture.client.mutateV2.getMockImplementation()!
  fixture.client.mutateV2.mockImplementationOnce(async (...args) => ({ ...await original(...args), commit_state: 'DRY_RUN_ROLLED_BACK' as never }))
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/draft save could not be verified/)
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
})

it.each([{ graph_version: 2 }, { semantic_revision: 99 }, { content_address: address('f') }, { graph_address: address('f') }])('does not announce a mismatched publication receipt %#', async (change) => {
  const fixture = versionSaveFixture(), published = vi.fn(), original = fixture.client.publishV2.getMockImplementation()!
  fixture.client.publishV2.mockImplementationOnce(async (...args) => ({ ...await original(...args), ...change }))
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/saved version does not match your draft/)
  expect(published).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
})

it('does not duplicate a save during two clicks before the pending render', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  const button = screen.getByRole('button', { name: 'Save version' })
  await act(async () => { fireEvent.click(button); fireEvent.click(button) })
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
})

it('clears invalid input only for the removed node, including colon-containing IDs', async () => {
  const fixture = versionSaveFixture(), first = fixture.current().document.nodes[0]
  fixture.setDraft({ ...fixture.current(), document: graphDocument([first, { ...first, node_id: 'target:other' }]) })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: 'invalid' } }); fireEvent.blur(screen.getByLabelText('Length'))
  act(() => flowMock.onNodeClick?.({}, { id: 'target:other' }))
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: 'invalid' } }); fireEvent.blur(screen.getByLabelText('Length'))
  act(() => flowMock.onNodeClick?.({}, { id: 'target' }))
  fireEvent.click(screen.getByRole('button', { name: /Stage node removal/ }))
  expect(flowMock.nodes.map((node) => node.id)).toEqual(['target:other'])
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Length'), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length'))
  expect(screen.getByRole('button', { name: 'Save version' })).toBeEnabled()
})


it('includes the visible parameter without depending on a blur event', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(fixture.client.mutateV2.mock.calls[0][3]).toEqual([{ command: 'set_parameter', node_id: 'target', parameter_id: 'length', value: 30 }])
})

it('does not replay a non-idempotent node addition after a layout refusal', async () => {
  const { ApiError } = await import('../shell/api')
  const fixture = versionSaveFixture(), published = vi.fn()
  fixture.client.mutateV2.mockImplementation(async (_project, _graph, base, commands) => {
    const previous = fixture.current(), addition = commands[0]
    expect(addition.command).toBe('add_node')
    if (previous.document.nodes.some((node) => node.node_id === addition.node_id)) throw new Error('Duplicate node addition')
    fixture.setDraft({ ...previous, semantic_revision: base + 1, content_address: address('c'), graph_address: address('d'),
      document: { ...previous.document, nodes: [...previous.document.nodes, { node_id: addition.node_id,
        component: { component_id: addition.component_id, component_version: addition.component_version }, parameters: addition.parameters }] } })
    return { ...semanticReceipt('EDIT', base, base + 1, commands, []), base_content_address: previous.content_address, base_graph_address: previous.graph_address }
  })
  fixture.client.mutateV2Presentation.mockRejectedValueOnce(new ApiError('input', 'Layout rejected'))
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await openExplorer(), { target: { value: 'Target 1' } })
  fireEvent.keyDown(screen.getByLabelText('Search node library'), { key: 'Enter' })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/layout was not saved/)
  expect(fixture.current().document.nodes).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await waitFor(() => expect(published).toHaveBeenCalledOnce())
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(fixture.current().document.nodes).toHaveLength(2)
})

const changedLibrary = () => new ApiError('input', 'Library changed', { code: 'STRATEGY_LIBRARY_CHANGED', message: 'Library changed' })

it('requires a deliberate current-components save after a library refusal without replaying saved edits', async () => {
  const fixture = versionSaveFixture(), published = vi.fn()
  fixture.client.publishV2.mockRejectedValueOnce(changedLibrary())
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={published} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  const update = await screen.findByRole('button', { name: 'Save updated version' })
  expect(fixture.client.publishV2).toHaveBeenCalledTimes(1)
  expect(fixture.client.publishV2.mock.calls[0]).toHaveLength(5)
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(screen.getByRole('button', { name: 'Save version' })).toBeDisabled()
  expect(screen.getByText(/Components have changed. Earlier results/)).toBeInTheDocument()
  fireEvent.click(update)
  await screen.findByText('Saved strategy version 1.')
  expect(fixture.client.publishV2).toHaveBeenLastCalledWith(project.project_id, graph.identifier, 1, null, expect.any(AbortSignal), catalogue.registry_identity)
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(published).toHaveBeenCalledOnce()
})

it('refreshes a stale target without retrying publication or losing the remaining draft edits', async () => {
  const fixture = versionSaveFixture()
  fixture.client.publishV2.mockRejectedValueOnce(changedLibrary()).mockRejectedValueOnce(changedLibrary())
  fixture.client.catalogue.mockResolvedValueOnce(catalogue).mockResolvedValueOnce(catalogue).mockResolvedValue({ ...catalogue, registry_identity: address('f') })
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Save updated version' }))
  await waitFor(() => expect(fixture.client.catalogue).toHaveBeenCalledTimes(3))
  expect(fixture.client.publishV2).toHaveBeenCalledTimes(2)
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  fireEvent.click(await screen.findByRole('button', { name: 'Save updated version' }))
  await screen.findByText('Saved strategy version 1.')
  expect(fixture.client.publishV2).toHaveBeenLastCalledWith(project.project_id, graph.identifier, 1, null, expect.any(AbortSignal), address('f'))
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
})

it('offers unchanged published rules for explicit saving under the current components', async () => {
  const fixture = versionSaveFixture(), current = fixture.current()
  fixture.setDraft({ ...current, current_version: 1, published_revision: 0, document: { ...current.document, strategy_version: 2 } })
  fixture.client.v2Version.mockResolvedValue({ format_version: 2, graph_identifier: graph.identifier, graph_version: 1, content_address: current.content_address, graph_address: current.graph_address, document: current.document, registry_snapshot_address: address('f') } as never)
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 1 }} onPublished={vi.fn()} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Save updated version' }))
  await screen.findByText('Saved strategy version 2.')
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  expect(fixture.client.publishV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 0, 1, expect.any(AbortSignal), catalogue.registry_identity)
})

it('retains unsaved rules when library validation refuses the semantic save and retries a failed catalogue read deliberately', async () => {
  const fixture = versionSaveFixture()
  fixture.client.mutateV2.mockRejectedValueOnce(changedLibrary())
  fixture.client.catalogue.mockResolvedValueOnce(catalogue).mockRejectedValueOnce(new Error('Offline')).mockResolvedValue(catalogue)
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={graph} onPublished={vi.fn()} />)
  fireEvent.change(await selectedField('Length'), { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save version' }))
  await screen.findByText(/Current components could not be loaded/)
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument()
  expect(screen.getByLabelText('Length')).toHaveValue('30')
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Review current components' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Save updated version' }))
  await screen.findByText('Saved strategy version 1.')
  expect(fixture.client.mutateV2).toHaveBeenCalledTimes(2)
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
})

it.each([catalogue.registry_identity, 'invalid'])('does not offer a changed-library action without a different verified saved registry: %s', async (registry) => {
  const fixture = versionSaveFixture(), current = fixture.current()
  fixture.setDraft({ ...current, current_version: 1, published_revision: 0, document: { ...current.document, strategy_version: 2 } })
  fixture.client.v2Version.mockResolvedValue({ format_version: 2, graph_identifier: graph.identifier, graph_version: 1, content_address: current.content_address, graph_address: current.graph_address, document: current.document, registry_snapshot_address: registry } as never)
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 1 }} onPublished={vi.fn()} />)
  await selectedField('Length')
  await waitFor(() => expect(fixture.client.v2Version).toHaveBeenCalledOnce())
  expect(screen.queryByRole('button', { name: 'Save updated version' })).not.toBeInTheDocument()
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
})


it('clears an earlier library warning when an explicit reload confirms the current library', async () => {
  const fixture = versionSaveFixture(), current = fixture.current()
  fixture.setDraft({ ...current, current_version: 1, published_revision: 0, document: { ...current.document, strategy_version: 2 } })
  const row = { format_version: 2, graph_identifier: graph.identifier, graph_version: 1, content_address: current.content_address, graph_address: current.graph_address, document: current.document, registry_snapshot_address: address('f') }
  fixture.client.v2Version.mockResolvedValueOnce(row as never).mockResolvedValue({ ...row, registry_snapshot_address: catalogue.registry_identity } as never)
  render(<StrategyBuilderWorkspace api={fixture.client as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 1 }} onPublished={vi.fn()} />)
  await screen.findByRole('button', { name: 'Save updated version' })
  fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
  await selectedField('Length')
  expect(screen.queryByRole('button', { name: 'Save updated version' })).not.toBeInTheDocument()
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
})

it('distinguishes repeated components in connection menus while preserving internal connection values', async () => {
  const nodes = [{ ...source, node_id: 'private-source-a' }, { ...source, node_id: 'private-source-b' }, { node_id: 'private-target', component: { component_id: 'logic.target_1', component_version: 2 }, parameters: {} }]
  const validateV2 = vi.fn().mockResolvedValue(undefined)
  const api = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue({ ...initial, document: graphDocument(nodes) }), v2Presentation: vi.fn().mockResolvedValue(presentation()), validateV2 } as unknown as StrategyApi
  render(<StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={vi.fn()} />)
  await screen.findByLabelText('Strategy graph canvas')
  act(() => flowMock.onNodeClick?.({}, { id: 'private-target' }))
  const sourceSelect = screen.getByRole('combobox', { name: 'Source node' })
  fireEvent.keyDown(sourceSelect, { key: 'Delete' }); expect(flowMock.nodes).toHaveLength(3)
  fireEvent.keyDown(sourceSelect, { key: 'A', shiftKey: true }); expect(screen.queryByRole('dialog', { name: 'Add component' })).not.toBeInTheDocument()
  fireEvent.keyDown(sourceSelect, { key: 'ArrowDown' })
  const menu = await screen.findByRole('listbox')
  expect(menu).toHaveTextContent('Source 0 (1)')
  expect(menu).toHaveTextContent('Source 0 (2)')
  expect(menu).not.toHaveTextContent('private-source')
  fireEvent.keyDown(menu, { key: 'Backspace' }); expect(flowMock.nodes).toHaveLength(3)
  fireEvent.keyDown(menu, { key: 'Escape' })
  await chooseSelect('Source node', 'private-source-b')
  expect(screen.getByRole('combobox', { name: 'Source node' })).toHaveTextContent('Source 0 (2)')
  await chooseSelect('Target node', 'private-target')
  await chooseSelect('Source port', 'out')
  await chooseSelect('Target port', 'in')
  fireEvent.click(screen.getByRole('button', { name: 'Stage typed connection' }))
  fireEvent.click(screen.getByRole('button', { name: 'Check strategy' }))
  await waitFor(() => expect(validateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 0, [expect.objectContaining({ source: { node_id: 'private-source-b', port_id: 'out' }, target: { node_id: 'private-target', port_id: 'in' } })], expect.any(AbortSignal)))
})
