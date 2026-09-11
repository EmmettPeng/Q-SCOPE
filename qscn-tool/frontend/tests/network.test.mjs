import assert from 'node:assert/strict'
import test from 'node:test'
import { build } from 'esbuild'

async function loadModule(entry) {
  const result = await build({ entryPoints: [entry], bundle: true, write: false, format: 'esm', platform: 'node' })
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`)
}

const { displayEdges, networkMetrics } = await loadModule('src/network.ts')

function edge(id, source, target, signal, pathway) {
  return {
    id, source, target, signal_name: signal, pathway_id: pathway, pathway_name: pathway.toUpperCase(),
    source_sample: source, target_sample: target, sender_components: [`send-${pathway}`],
    receiver_components: [`receive-${pathway}`], references: [`ref-${pathway}`], self_communication: source === target,
    kind: 'potential_communication', color: '#000', database_version_id: 'db', database_source: 'source',
    source_label: source, target_label: target, evidence_level: 'potential_communication',
  }
}

test('groups only directed same-signal arrows and aggregates evidence', () => {
  const edges = [
    edge('1', 'a', 'b', 'AI-1', 'p1'), edge('2', 'a', 'b', 'AI-1', 'p2'),
    edge('3', 'b', 'a', 'AI-1', 'p3'), edge('4', 'a', 'b', 'AI-2', 'p4'),
    edge('5', 'a', 'a', 'AI-1', 'p5'), edge('6', 'a', 'a', 'AI-1', 'p6'),
  ]
  const grouped = displayEdges(edges, 'signal')
  assert.equal(grouped.length, 4)
  const ab = grouped.find((item) => item.source === 'a' && item.target === 'b' && item.signal_name === 'AI-1')
  assert.deepEqual(ab.pathway_ids, ['p1', 'p2'])
  assert.equal(ab.evidence_edge_count, 2)
  assert.deepEqual(ab.references, ['ref-p1', 'ref-p2'])
  assert.deepEqual(ab.evidence_edges, [
    {
      edge_id: '1', pathway_id: 'p1', pathway_name: 'P1', signal_name: 'AI-1', source_sample: 'a', source_label: 'a', target_sample: 'b', target_label: 'b', sender_components: ['send-p1'],
      receiver_components: ['receive-p1'], references: ['ref-p1'], evidence_level: 'potential_communication',
    },
    {
      edge_id: '2', pathway_id: 'p2', pathway_name: 'P2', signal_name: 'AI-1', source_sample: 'a', source_label: 'a', target_sample: 'b', target_label: 'b', sender_components: ['send-p2'],
      receiver_components: ['receive-p2'], references: ['ref-p2'], evidence_level: 'potential_communication',
    },
  ])
  assert.equal(grouped.find((item) => item.self_communication).evidence_edge_count, 2)
})

test('pathway mode preserves every evidence edge', () => {
  const edges = [edge('1', 'a', 'b', 'AI-1', 'p1'), edge('2', 'a', 'b', 'AI-1', 'p2')]
  const displayed = displayEdges(edges, 'pathway')
  assert.equal(displayed.length, 2)
  assert.equal(displayed[0].evidence_edges.length, 1)
  assert.equal(displayed[0].evidence_edges[0].pathway_id, 'p1')
})

test('collapses reciprocal edges only for the same pathway and keeps two evidence edges', () => {
  const edges = [
    edge('1', 'a', 'b', 'AI-1', 'p1'),
    edge('2', 'b', 'a', 'AI-1', 'p1'),
    edge('3', 'b', 'a', 'AI-1', 'p2'),
  ]
  const displayed = displayEdges(edges, 'pathway')
  assert.equal(displayed.length, 2)
  const reciprocal = displayed.find((item) => item.pathway_id === 'p1')
  assert.equal(reciprocal.bidirectional, true)
  assert.equal(reciprocal.source_arrow_shape, 'triangle')
  assert.equal(reciprocal.target_arrow_shape, 'triangle')
  assert.equal(reciprocal.evidence_edge_count, 2)
  assert.deepEqual(reciprocal.evidence_edges.map((item) => `${item.source_sample}->${item.target_sample}`), ['a->b', 'b->a'])
  assert.equal(displayed.find((item) => item.pathway_id === 'p2').bidirectional, false)
})

test('same-signal merge keeps bidirectional and directed pathway groups separate', () => {
  const edges = [
    edge('1', 'a', 'b', 'AI-1', 'p1'), edge('2', 'b', 'a', 'AI-1', 'p1'),
    edge('3', 'a', 'b', 'AI-1', 'p2'), edge('4', 'b', 'a', 'AI-1', 'p2'),
    edge('5', 'a', 'b', 'AI-1', 'p3'),
  ]
  const displayed = displayEdges(edges, 'signal')
  assert.equal(displayed.length, 2)
  const reciprocal = displayed.find((item) => item.bidirectional)
  assert.deepEqual(reciprocal.pathway_ids, ['p1', 'p2'])
  assert.equal(reciprocal.evidence_edge_count, 4)
  assert.equal(displayed.find((item) => !item.bidirectional).evidence_edge_count, 1)
})

test('minimal mode creates at most one edge per sample pair with directional pathway summaries', () => {
  const edges = [
    edge('1', 'a', 'b', 'AI-1', 'p1'),
    edge('2', 'b', 'a', 'AI-1', 'p1'),
    edge('3', 'a', 'b', 'DSF', 'p2'),
    edge('4', 'b', 'a', 'PQS', 'p3'),
    edge('5', 'a', 'a', 'AI-1', 'p4'),
    edge('6', 'a', 'a', 'DSF', 'p5'),
  ]
  const displayed = displayEdges(edges, 'minimal')
  assert.equal(displayed.length, 2)
  const pair = displayed.find((item) => !item.self_communication)
  assert.equal(pair.source_arrow_shape, 'triangle')
  assert.equal(pair.target_arrow_shape, 'triangle')
  assert.equal(pair.direction_summary.total_pathways, 3)
  assert.equal(pair.direction_summary.forward.pathway_count, 1)
  assert.equal(pair.direction_summary.reverse.pathway_count, 1)
  assert.equal(pair.direction_summary.bidirectional.pathway_count, 1)
  assert.equal(pair.evidence_edge_count, 4)
  const self = displayed.find((item) => item.self_communication)
  assert.equal(self.direction_summary.self.pathway_count, 2)
  assert.equal(self.direction_summary.total_pathways, 2)
})

test('network metrics use evidence edges and remove self contributions when filtered', () => {
  const nodes = [{ id: 'genome:a', kind: 'genome', sample_id: 'a', label: 'A' }, { id: 'genome:b', kind: 'genome', sample_id: 'b', label: 'B' }]
  const edges = [edge('1', 'a', 'a', 'AI-1', 'p1'), edge('2', 'a', 'b', 'AI-1', 'p2')]
  const all = networkMetrics(nodes, edges).bySample.get('a')
  assert.deepEqual([all.in_degree, all.out_degree, all.total_degree, all.self_edge_count], [1, 2, 3, 1])
  const withoutSelf = networkMetrics(nodes, edges.filter((item) => !item.self_communication)).bySample.get('a')
  assert.deepEqual([withoutSelf.in_degree, withoutSelf.out_degree, withoutSelf.total_degree, withoutSelf.self_edge_count], [0, 1, 1, 0])
})
