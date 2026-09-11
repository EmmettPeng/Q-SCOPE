import { capabilityMatchesEvidence, evidenceFilteredEdges, hitMatchesEvidence } from './evidence'
import type { Capability, DatabaseInfo, Hit, ResultCollection, Results } from './types'

interface DemoSnapshot {
  metadata: Record<string, unknown>
  projects: unknown[]
  databases: DatabaseInfo[]
  examples: unknown[]
  analysis_tree: { project_id: string; databases: Array<{ runs: Array<{ id: string }> }> }
  run: { id: string }
  results: Results
  profiles: Record<string, unknown[]>
}

let snapshotPromise: Promise<DemoSnapshot> | undefined

function snapshot(): Promise<DemoSnapshot> {
  snapshotPromise ??= fetch(`${import.meta.env.BASE_URL}demo/demo-snapshot.json`)
    .then((response) => {
      if (!response.ok) throw new Error('The bundled demo snapshot could not be loaded.')
      return response.json() as Promise<DemoSnapshot>
    })
  return snapshotPromise
}

function collection<T>(items: T[], baseline = items.length): ResultCollection<T> {
  return { items, total: items.length, baseline }
}

function evidenceParams(url: URL) {
  return {
    minHmmCoverage: Number(url.searchParams.get('min_hmm_coverage') ?? 0),
    minSequenceCoverage: Number(url.searchParams.get('min_sequence_coverage') ?? 0),
    includePartial: url.searchParams.get('include_partial') !== 'false',
    biologicalRuleId: url.searchParams.get('biological_rule_id') ?? '',
  }
}

function summary(results: Results): Results {
  return {
    ...structuredClone(results), hits: [], capabilities: [], biological_annotations: [],
    biological_rule_ids: [...new Set(results.biological_annotations.map((item) => item.rule_id))].sort(),
    result_counts: {
      hits: results.hits.length,
      capabilities: results.capabilities.length,
      biological_annotations: results.biological_annotations.length,
      network_edges: results.network.edges.length,
    },
    network: { ...structuredClone(results.network), edges: [] },
  }
}

function notFound(): never {
  throw new Error('This resource is not available in the read-only demo.')
}

export async function demoRequest<T>(path: string, init?: RequestInit): Promise<T> {
  if ((init?.method ?? 'GET').toUpperCase() !== 'GET') {
    throw new Error('Read-only demo: this action is available in the local Q-SCOPE application.')
  }
  const data = await snapshot()
  const url = new URL(path, 'https://qscope.demo')
  if (url.pathname === '/api/projects') return structuredClone(data.projects) as T
  if (url.pathname === '/api/databases') return structuredClone(data.databases) as T
  if (url.pathname === '/api/examples') return structuredClone(data.examples) as T
  if (url.pathname === `/api/projects/${data.analysis_tree.project_id}/analysis-tree`) return structuredClone(data.analysis_tree) as T
  if (url.pathname === `/api/runs/${data.run.id}`) return structuredClone(data.run) as T
  if (url.pathname === `/api/runs/${data.run.id}/results`) {
    const requested = url.searchParams.get('interpretation_id')
    if (requested && requested !== data.results.interpretation_id) notFound()
    return (url.searchParams.get('summary') === 'true' ? summary(data.results) : structuredClone(data.results)) as T
  }
  if (url.pathname === `/api/runs/${data.run.id}/results/capabilities`) {
    const filters = evidenceParams(url)
    const hits = new Map(data.results.hits.map((hit) => [hit.hit_id, hit]))
    const items = data.results.capabilities.filter((item) => capabilityMatchesEvidence(item, hits, filters))
    return collection<Capability>(structuredClone(items), data.results.capabilities.length) as T
  }
  if (url.pathname === `/api/runs/${data.run.id}/results/network-edges`) {
    const items = evidenceFilteredEdges(data.results, evidenceParams(url))
    return collection(structuredClone(items), data.results.network.edges.length) as T
  }
  if (url.pathname === `/api/runs/${data.run.id}/results/annotations`) {
    return collection(structuredClone(data.results.biological_annotations)) as T
  }
  if (url.pathname === `/api/runs/${data.run.id}/results/hits`) {
    const filters = evidenceParams(url)
    const profiles = new Set(url.searchParams.getAll('profile_id'))
    const allowed = filters.biologicalRuleId ? new Set(data.results.biological_annotations
      .filter((item) => item.rule_id === filters.biologicalRuleId)
      .flatMap((item) => item.supporting_hit_ids)) : null
    const scoped = data.results.hits.filter((hit) => !profiles.size || profiles.has(hit.profile_id))
    const items = scoped.filter((hit) => (!allowed || allowed.has(hit.hit_id)) && hitMatchesEvidence(hit, filters))
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const limit = Number(url.searchParams.get('limit') ?? 500)
    return { items: structuredClone(items.slice(offset, offset + limit)), record_ids: items.map((hit: Hit) => hit.hit_id), total: items.length, baseline: scoped.length, offset, limit } as T
  }
  const profileMatch = url.pathname.match(/^\/api\/databases\/([^/]+)\/profiles$/)
  if (profileMatch) {
    const databaseId = decodeURIComponent(profileMatch[1])
    const all = data.profiles[databaseId]
    if (!all) notFound()
    const query = (url.searchParams.get('query') ?? '').toLocaleLowerCase()
    const filtered = all.filter((item) => JSON.stringify(item).toLocaleLowerCase().includes(query))
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const limit = Number(url.searchParams.get('limit') ?? 50)
    return { items: structuredClone(filtered.slice(offset, offset + limit)), total: filtered.length, baseline: all.length, offset, limit } as T
  }
  return notFound()
}

export function resetDemoSnapshotForTests(): void {
  snapshotPromise = undefined
}
