import { BarChart3, Braces, FolderKanban, PenLine } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from './api/client'
import { CodingPage } from './pages/CodingPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ResultsPage } from './pages/ResultsPage'
import type { Project } from './types'

type Page = 'projects' | 'coding' | 'results'

export default function App() {
  const [page, setPage] = useState<Page>('projects')
  const [projectId, setProjectId] = useState(1)
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState('')
  useEffect(() => { api.projects().then(setProjects).catch((e: Error) => setError(e.message)) }, [page])
  return <div className="app-shell">
    <nav className="sidebar"><button className="brand" onClick={() => setPage('projects')}><Braces size={24} /><span>Code<strong>Flow</strong></span></button><div className="nav-items"><button className={page === 'projects' ? 'active' : ''} onClick={() => setPage('projects')}><FolderKanban /><span>项目</span></button><button className={page === 'coding' ? 'active' : ''} onClick={() => setPage('coding')}><PenLine /><span>编码</span></button><button className={page === 'results' ? 'active' : ''} onClick={() => setPage('results')}><BarChart3 /><span>结果</span></button></div><div className="sidebar-foot"><span>CF</span><div><b>演示编码员</b><small>Coder · Online</small></div></div></nav>
    <div className="content">{error ? <div className="empty-state"><p>{error}</p></div> : page === 'projects' ? <ProjectsPage projects={projects} onStart={(id) => { setProjectId(id); setPage('coding') }} /> : page === 'coding' ? <CodingPage projectId={projectId} onResults={() => setPage('results')} /> : <ResultsPage projectId={projectId} />}</div>
  </div>
}

