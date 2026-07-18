import { Download, Filter, Timer, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ResultRow } from '../types'

export function ResultsPage({ projectId }: { projectId: number }) {
  const [rows, setRows] = useState<ResultRow[]>([])
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<ResultRow | null>(null)
  useEffect(() => { api.results(projectId, status).then(setRows) }, [projectId, status])
  return (
    <main className="page results-page">
      <header className="page-title"><div><span className="eyebrow">Result archive</span><h1>编码结果</h1><p>每一份判断都绑定人员、时间与版本，不覆盖原始记录。</p></div><div className="export-actions"><a href={`/api/exports/${projectId}/jsonl`}><Download size={17} /> JSONL</a><a href={`/api/exports/${projectId}/csv`}><Download size={17} /> CSV</a></div></header>
      <div className="results-toolbar"><Filter size={16} /><span>筛选状态</span>{[['', '全部'], ['pending', '待处理'], ['draft', '草稿'], ['submitted', '已提交']].map(([value, label]) => <button key={value} className={status === value ? 'active' : ''} onClick={() => setStatus(value)}>{label}</button>)}<strong>{rows.length} 条记录</strong></div>
      <div className="table-wrap"><table><thead><tr><th>样本</th><th>编码员</th><th>阶段</th><th>状态</th><th>传播点类型</th><th>提交时间</th><th>Schema</th></tr></thead><tbody>{rows.map((row) => <tr key={row.assignment_id} onClick={() => setSelected(row)}><td><b>{row.sample_number}</b></td><td>{row.coder}</td><td>{row.stage}</td><td><span className={`result-status ${row.status}`}>{row.status === 'submitted' ? '已提交' : row.status === 'draft' ? '草稿' : '待处理'}</span></td><td>{String(row.annotation_data.communicative_type ?? '—')}</td><td>{row.submitted_at ? new Date(row.submitted_at).toLocaleString('zh-CN') : '—'}</td><td className="mono">{row.schema_version ?? '—'}</td></tr>)}</tbody></table></div>
      {selected && <div className="drawer-backdrop" onClick={() => setSelected(null)}><aside className="result-drawer" onClick={(e) => e.stopPropagation()}><button className="drawer-close" onClick={() => setSelected(null)}><X /></button><span className="eyebrow">完整编码记录</span><h2>{selected.sample_number}</h2><div className="drawer-meta"><span>{selected.coder}</span><span><Timer size={14} /> {selected.duration_seconds}s</span><span>{selected.schema_version}</span></div>{Object.entries(selected.annotation_data).map(([key, value]) => <div className="result-field" key={key}><span>{key}</span><p>{Array.isArray(value) ? value.join('、') : String(value ?? '—')}</p></div>)}</aside></div>}
    </main>
  )
}

