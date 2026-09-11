import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import cytoscape, { Core } from 'cytoscape'
import { copy, displayEvidenceLevel } from './copy/en'
import { displayEdges, networkMetrics } from './network'
import type { DirectionBucket, DirectionSummary, NetworkEdgeEvidence, NetworkViewMode } from './network'
import { jpegDataUrlToPdf, saveBlob } from './pdf'
import type { NetworkEdge, Results } from './types'

interface Props { results: Results; evidenceEdges: NetworkEdge[]; showSelf: boolean; mode: NetworkViewMode }
export interface NetworkViewHandle { exportCurrentView: () => Promise<void> }
interface Tooltip { x: number; y: number; pathways: string[]; summary?: DirectionSummary; source: string; target: string }

function evidenceFromSelection(selected: Record<string, unknown>): NetworkEdgeEvidence[] | null {
  return Array.isArray(selected.evidence_edges) ? selected.evidence_edges as NetworkEdgeEvidence[] : null
}

function signalText(bucket: DirectionBucket): string {
  return bucket.signals.map((item) => `${item.signal_name} (${item.pathway_count})`).join('; ')
}

const NetworkView = forwardRef<NetworkViewHandle, Props>(function NetworkView({ results, evidenceEdges: filteredEvidence, showSelf, mode }, ref) {
  const container = useRef<HTMLDivElement>(null)
  const graph = useRef<Core | null>(null)
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)
  const [tooltip, setTooltip] = useState<Tooltip | null>(null)
  const visibleEvidence = useMemo(() => filteredEvidence.filter((edge) => showSelf || !edge.self_communication), [filteredEvidence, showSelf])
  const metrics = useMemo(() => networkMetrics(results.network.nodes, visibleEvidence), [results, visibleEvidence])
  const edges = useMemo(() => displayEdges(visibleEvidence, mode), [visibleEvidence, mode])

  useEffect(() => {
    setSelected((current) => {
      if (!current) return null
      if (current.kind !== 'genome') return null
      const metric = metrics.bySample.get(String(current.sample_id))
      return metric ? { ...current, ...metric } : null
    })
  }, [metrics, edges])

  function runLayout() { graph.current?.layout({ name: 'cose', animate: true, animationDuration: 650, padding: 48, nodeRepulsion: () => 10000 }).run() }

  useImperativeHandle(ref, () => ({
    async exportCurrentView() {
      const cy = graph.current
      if (!cy) return
      const source = cy.jpg({ full: false, scale: 2, bg: '#fffdf8', quality: 0.95 })
      const visibleLegend = results.network.legend.filter((item) => visibleEvidence.some((edge) => edge.signal_name === item.signal_name))
      const legend = mode === 'minimal' && visibleLegend.length > 1
        ? [{ signal_name: copy.network.multipleSignals, color: '#70766f' }, ...visibleLegend]
        : visibleLegend
      const blob = await jpegDataUrlToPdf(source, Math.round(cy.width() * 2), Math.round(cy.height() * 2), {
        title: copy.network.pdfTitle,
        meta: copy.network.pdfMeta(mode, visibleEvidence.length, edges.length),
        legend: legend.map((item) => ({ label: item.signal_name, color: item.color })),
      })
      saveBlob(blob, `qscn-network-${results.run_id.slice(0, 8)}-${results.interpretation_id.slice(0, 8)}-${mode}.pdf`)
    },
  }), [results, mode, visibleEvidence, edges])

  useEffect(() => {
    if (!container.current) return
    graph.current?.destroy()
    const cy = cytoscape({
      container: container.current,
      elements: [
        ...results.network.nodes.map((node) => ({ data: { ...node, ...(metrics.bySample.get(node.sample_id) ?? {}) } })),
        ...edges.map((edge) => ({ data: edge })),
      ],
      layout: { name: 'cose', animate: false, padding: 48, nodeRepulsion: () => 10000 },
      style: [
        { selector: 'node', style: { label: 'data(label)', 'font-size': '10px', 'font-family': 'Cabinet Grotesk, -apple-system, BlinkMacSystemFont, sans-serif', 'font-weight': 600, 'text-wrap': 'wrap', 'text-max-width': '100px', 'text-valign': 'bottom', 'text-margin-y': '7px', color: '#182630', 'background-color': '#3c8c92', 'border-width': 2, 'border-color': '#ffffff', width: 'mapData(total_degree, 0, 20, 26, 44)', height: 'mapData(total_degree, 0, 20, 26, 44)' } },
        { selector: 'edge', style: { width: 2.5, 'curve-style': 'bezier', 'source-arrow-shape': 'data(source_arrow_shape)', 'target-arrow-shape': 'data(target_arrow_shape)', 'arrow-scale': 0.85, 'line-color': 'data(color)', 'source-arrow-color': 'data(color)', 'target-arrow-color': 'data(color)', opacity: 0.82, 'loop-direction': '-45deg', 'loop-sweep': '68deg' } },
        { selector: '.faded', style: { opacity: 0.12 } },
        { selector: '.focused', style: { 'border-color': '#3f6049', 'border-width': 4, width: 48, height: 48, opacity: 1 } },
        { selector: 'edge.focused', style: { width: 5, opacity: 1 } },
        { selector: ':selected', style: { 'overlay-color': '#506c57', 'overlay-opacity': 0.14, 'overlay-padding': 8 } },
      ] as cytoscape.StylesheetJson,
    })
    cy.on('tap', 'node, edge', (event) => setSelected({ ...event.target.data() }))
    cy.on('tap', (event) => { if (event.target === cy) setSelected(null) })
    cy.on('mouseover', 'node', (event) => { cy.elements().addClass('faded'); event.target.closedNeighborhood().removeClass('faded').addClass('focused') })
    cy.on('mouseout', 'node', () => cy.elements().removeClass('faded focused'))
    cy.on('mouseover', 'edge', (event) => {
      const data = event.target.data(); const position = event.renderedPosition ?? event.target.midpoint()
      setTooltip({ x: position.x, y: position.y, pathways: data.pathway_names ?? [data.pathway_name], summary: data.direction_summary, source: data.source_label, target: data.target_label })
    })
    cy.on('mouseout', 'edge', () => setTooltip(null))
    graph.current = cy
    return () => cy.destroy()
  }, [results, edges, metrics])

  const evidenceEdges = selected ? evidenceFromSelection(selected) : null
  const nodeSelected = selected?.kind === 'genome'
  return <div className="network-shell">
    <div className="network-stage">
      <button className="layout-button" onClick={runLayout}>{copy.network.layout}</button>
      <div ref={container} className="network-canvas" aria-label={copy.network.canvasLabel}/>
      {tooltip && <div className="edge-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
        {tooltip.summary ? <>
          <b>{copy.network.tooltipTotal(tooltip.summary.total_pathways)}</b>
          {tooltip.summary.forward.pathway_count > 0 && <span>{copy.network.tooltipDirected(tooltip.summary.forward.pathway_count, tooltip.source, tooltip.target)}<small>{signalText(tooltip.summary.forward)}</small></span>}
          {tooltip.summary.reverse.pathway_count > 0 && <span>{copy.network.tooltipDirected(tooltip.summary.reverse.pathway_count, tooltip.target, tooltip.source)}<small>{signalText(tooltip.summary.reverse)}</small></span>}
          {tooltip.summary.bidirectional.pathway_count > 0 && <span>{copy.network.tooltipBidirectional(tooltip.summary.bidirectional.pathway_count)}<small>{signalText(tooltip.summary.bidirectional)}</small></span>}
          {tooltip.summary.self.pathway_count > 0 && <span>{copy.network.tooltipSelf(tooltip.summary.self.pathway_count)}<small>{signalText(tooltip.summary.self)}</small></span>}
        </> : <><b>{copy.network.tooltipPathways}</b><span>{tooltip.pathways.join(', ')}</span></>}
      </div>}
    </div>
    <aside className="network-inspector">
      <span className="eyebrow">{copy.network.inspector}</span>
      {selected ? <>
        <h3>{String(selected.label ?? selected.signal_name ?? copy.network.evidence)}</h3>
        {nodeSelected ? <dl>
          <div><dt>{copy.network.fields.inDegree}</dt><dd>{String(selected.in_degree)}</dd></div>
          <div><dt>{copy.network.fields.outDegree}</dt><dd>{String(selected.out_degree)}</dd></div>
          <div><dt>{copy.network.fields.totalDegree}</dt><dd>{String(selected.total_degree)}</dd></div>
          <div><dt>{copy.network.fields.uniqueNeighbors}</dt><dd>{String(selected.unique_neighbors)}</dd></div>
          <div><dt>{copy.network.fields.selfEdges}</dt><dd>{String(selected.self_edge_count)}</dd></div>
        </dl> : evidenceEdges ? <>
          <dl className="edge-summary">
            <div><dt>{copy.network.fields.source}</dt><dd>{String(selected.source_label ?? selected.source_sample ?? copy.common.unknown)}</dd></div>
            <div><dt>{copy.network.fields.target}</dt><dd>{String(selected.target_label ?? selected.target_sample ?? copy.common.unknown)}</dd></div>
            <div><dt>{copy.network.fields.signal}</dt><dd>{Array.isArray(selected.signal_names) ? selected.signal_names.join(', ') : String(selected.signal_name ?? copy.common.unknown)}</dd></div>
            <div><dt>{copy.network.fields.direction}</dt><dd>{selected.bidirectional ? copy.network.bidirectional : copy.network.directed}</dd></div>
            <div><dt>{copy.network.fields.database}</dt><dd>{String(selected.database_source ?? copy.common.unknown)}</dd></div>
            <div><dt>{copy.network.fields.evidenceEdges}</dt><dd>{String(selected.evidence_edge_count ?? evidenceEdges.length)}</dd></div>
          </dl>
          <div className="pathway-evidence-list"><h4>{copy.network.pathwayEvidence}</h4>{evidenceEdges.map((edge) => <article className="pathway-evidence" key={edge.edge_id}>
            <h5>{edge.pathway_name}</h5><code>{edge.pathway_id}</code><dl>
              <div><dt>{copy.network.fields.signal}</dt><dd>{edge.signal_name}</dd></div>
              <div><dt>{copy.network.fields.direction}</dt><dd>{copy.network.edgeDirection(edge.source_label, edge.target_label)}</dd></div>
              <div><dt>{copy.network.fields.senderComponents}</dt><dd>{(edge.sender_component_labels ?? edge.sender_components).join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.receiverComponents}</dt><dd>{(edge.receiver_component_labels ?? edge.receiver_components).join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.references}</dt><dd>{edge.references.join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.biologicalRules}</dt><dd>{edge.biological_rule_ids?.join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.biologicalBoundaries}</dt><dd>{edge.biological_states?.join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.biologicalReferences}</dt><dd>{edge.boundary_references?.join(', ') || copy.common.unknown}</dd></div>
              <div><dt>{copy.network.fields.evidenceLevel}</dt><dd>{edge.evidence_level ? displayEvidenceLevel(edge.evidence_level) : copy.common.unknown}</dd></div>
            </dl>
          </article>)}</div>
        </> : null}
      </> : <p>{copy.network.emptyInspector}</p>}
    </aside>
  </div>
})

export default NetworkView
