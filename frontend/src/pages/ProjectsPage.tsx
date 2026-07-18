import { ArrowRight, CheckCircle2, Database, Layers3 } from 'lucide-react'
import type { Project } from '../types'

export function ProjectsPage({ projects, onStart }: { projects: Project[]; onStart: (projectId: number) => void }) {
  return (
    <main className="page projects-page">
      <header className="hero">
        <div><span className="eyebrow">Research coding infrastructure</span><h1>让研究判断，<br /><em>有迹可循。</em></h1></div>
        <p>CodeFlow 将材料、编码规则与任务进度放进同一个可靠闭环。字段由 Schema 驱动，研究主题可以替换，过程始终可追溯。</p>
      </header>
      <div className="project-grid">
        {projects.map((project) => {
          const progress = project.total ? Math.round(project.completed / project.total * 100) : 0
          return <article className="project-card" key={project.id}>
            <div className="project-top"><span className="status-dot">运行中</span><span className="mono">P-{String(project.id).padStart(2, '0')}</span></div>
            <h2>{project.name}</h2><p>{project.description}</p>
            <div className="metrics"><div><Database size={17} /><strong>{project.total}</strong><span>材料</span></div><div><CheckCircle2 size={17} /><strong>{project.completed}</strong><span>已提交</span></div><div><Layers3 size={17} /><strong>{project.schema_version}</strong><span>Schema</span></div></div>
            <div className="progress-line"><span style={{ width: `${progress}%` }} /></div>
            <div className="project-bottom"><span>{progress}% 完成</span><button onClick={() => onStart(project.id)}>进入工作台 <ArrowRight size={17} /></button></div>
          </article>
        })}
      </div>
    </main>
  )
}

