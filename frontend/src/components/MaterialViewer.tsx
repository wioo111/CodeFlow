import { FileText, FlaskConical, Timer } from 'lucide-react'
import type { Task } from '../types'

export function MaterialViewer({ task }: { task: Task }) {
  const data = task.material.material_data
  const isMock = task.material.material_type === 'mock'
  return (
    <section className="material-panel panel">
      <div className="panel-kicker"><span>{isMock ? <FlaskConical size={15} /> : <FileText size={15} />}{isMock ? '模拟材料' : '文本材料'}</span><span>#{data.sample_number}</span></div>
      <div className="material-stage">
        <div className="placeholder-mark">CF</div>
        <p>{data.placeholder}</p>
        {task.material.metadata.duration_hint && <span className="duration"><Timer size={14} /> {task.material.metadata.duration_hint}</span>}
      </div>
      <div className="material-copy">
        <span className="eyebrow">测试说明</span>
        <h2>{data.test_note}</h2>
        <p>{data.text}</p>
      </div>
      <div className="material-meta"><span>材料 ID {task.material.id}</span><span>类型 {task.material.material_type}</span></div>
    </section>
  )
}

