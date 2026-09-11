import { useRef } from 'react'
import type { ReactNode } from 'react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import qscopeLogo from './assets/Q_SCOPE_logo.png'
import { copy } from './copy/en'

gsap.registerPlugin(useGSAP)

export type WorkspaceView = 'projects' | 'project' | 'evidence' | 'network'
export type EvidenceView = 'capabilities' | 'hits'

interface AppMastheadProps {
  view: WorkspaceView
  hasProject: boolean
  hasResults: boolean
  onNavigate: (view: WorkspaceView) => void
}

export function AppMasthead({ view, hasProject, hasResults, onNavigate }: AppMastheadProps) {
  const items: Array<{ id: WorkspaceView; label: string; disabled: boolean }> = [
    { id: 'projects', label: copy.navigation.atlas.projects, disabled: false },
    { id: 'project', label: copy.navigation.atlas.project, disabled: !hasProject },
    { id: 'evidence', label: copy.navigation.atlas.evidence, disabled: !hasResults },
    { id: 'network', label: copy.navigation.atlas.network, disabled: !hasResults },
  ]
  return <header className="atlas-masthead">
    <button className="atlas-brand" type="button" onClick={() => onNavigate('projects')} aria-label={copy.common.product}>
      <img src={qscopeLogo} alt="Q-SCOPE logo"/>
      <span><b>Q-SCOPE</b><small><strong>Q</strong>uorum-<strong>S</strong>ensing <strong>Co</strong>mmunication Link <strong>P</strong>r<strong>e</strong>dictor</small></span>
    </button>
    <nav className="atlas-primary-nav" aria-label={copy.navigation.atlas.primaryLabel}>
      {items.map((item) => <button type="button" key={item.id} disabled={item.disabled} aria-current={view === item.id ? 'page' : undefined} onClick={() => onNavigate(item.id)}>{item.label}</button>)}
    </nav>
    <div className="atlas-masthead-actions">
      <span className="atlas-local-state"><i/>{copy.navigation.localOnly}</span>
    </div>
  </header>
}

interface ProjectsHomeProps {
  upload: ReactNode
  projects: ReactNode
  databases: ReactNode
  projectCount: number
}

export function ProjectsHome({ upload, projects, databases, projectCount }: ProjectsHomeProps) {
  const root = useRef<HTMLElement>(null)
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      const projectCards = gsap.utils.toArray<HTMLElement>('.atlas-project-card')
      if (projectCards.length) gsap.from(projectCards, { y: 54, opacity: 0, rotate: -1.5, duration: .75, stagger: .09, ease: 'power3.out' })
    })
    return () => media.revert()
  }, { scope: root })

  return <main className="atlas-home" ref={root}>
    <section className="atlas-hero">
      <h1>{copy.home.titleLead}<span className="atlas-hero-product-name">{copy.home.titleTail}</span></h1>
      {upload}
    </section>

    <section className="atlas-section atlas-recent-projects">
      <div className="atlas-section-heading"><div><p className="atlas-kicker">{copy.home.continue}</p><h2>{copy.home.recentProjects}</h2></div><span>{copy.home.projectCount(projectCount)}</span></div>
      <div className="atlas-project-stack">{projects}</div>
    </section>

    <section className="atlas-section atlas-databases">
      <div className="atlas-section-heading"><div><p className="atlas-kicker">{copy.navigation.localOnly}</p><h2>{copy.home.databases}</h2></div></div>
      {databases}
    </section>

    <footer className="atlas-provenance"><span>Q-SCOPE v1.0.0</span><span>Schema 5</span><span>{copy.common.release}</span></footer>
  </main>
}

export function ProjectWorkspace({ title, context, children }: { title: string; context: ReactNode; children: ReactNode }) {
  return <main className="atlas-workspace atlas-project-workspace">
    <header className="atlas-page-heading"><div><p className="atlas-kicker">{copy.navigation.atlas.projects} / {title}</p><h1>{title}</h1><div className="atlas-project-context">{context}</div></div></header>
    {children}
  </main>
}

interface EvidenceWorkspaceProps {
  active: EvidenceView
  onChange: (view: EvidenceView) => void
  context: string
  actions?: ReactNode
  children: ReactNode
}

export function EvidenceWorkspace({ active, onChange, context, actions, children }: EvidenceWorkspaceProps) {
  return <main className="atlas-workspace atlas-evidence-workspace">
    <header className="atlas-page-heading atlas-results-heading"><div><p className="atlas-kicker">{context}</p><h1>{copy.navigation.atlas.evidence}</h1></div>{actions}</header>
    <nav className="atlas-secondary-nav" aria-label={copy.navigation.atlas.evidenceLabel}>
      <button type="button" aria-current={active === 'capabilities' ? 'page' : undefined} onClick={() => onChange('capabilities')}>{copy.navigation.tabs.capabilities}</button>
      <button type="button" aria-current={active === 'hits' ? 'page' : undefined} onClick={() => onChange('hits')}>{copy.navigation.tabs.hits}</button>
    </nav>
    {children}
  </main>
}

export function NetworkWorkspace({ context, actions, children }: { context: string; actions: ReactNode; children: ReactNode }) {
  return <main className="atlas-workspace atlas-network-workspace">
    <header className="atlas-page-heading atlas-results-heading"><div><p className="atlas-kicker">{context}</p><h1>{copy.network.title}</h1></div>{actions}</header>
    {children}
  </main>
}
