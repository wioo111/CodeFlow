import { ArrowLeft, ArrowRight, Check, Cloud, CloudOff, LockKeyhole, Save } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import { MaterialViewer } from '../components/MaterialViewer'
import { SchemaForm } from '../components/SchemaForm'
import type { ProjectSchema, Task } from '../types'

type FormData = Record<string, string | number | boolean | string[] | null>

function validate(schema: ProjectSchema, data: FormData) {
  const errors: Record<string, string> = {}
  schema.fields.forEach((field) => {
    const value = data[field.id]
    if (field.required && (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length))) errors[field.id] = '请完成此必填项'
  })
  return errors
}

export function CodingPage({ projectId, onResults }: { projectId: number; onResults: () => void }) {
  const [schema, setSchema] = useState<ProjectSchema | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [data, setData] = useState<FormData>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const startedAt = useRef(0)
  const hydratedTask = useRef<number | null>(null)
  const task = tasks[currentIndex]
  const submitted = task?.status === 'submitted'

  useEffect(() => { Promise.all([api.schema(projectId), api.tasks(projectId)]).then(([s, t]) => { setSchema(s); setTasks(t); const firstOpen = t.findIndex((item) => item.status !== 'submitted'); setCurrentIndex(firstOpen >= 0 ? firstOpen : 0) }).catch((e: Error) => setMessage(e.message)) }, [projectId])
  useEffect(() => { if (!task || hydratedTask.current === task.id) return; hydratedTask.current = task.id; setData((task.annotation?.annotation_data ?? {}) as FormData); setErrors({}); setMessage(''); startedAt.current = Date.now() }, [task])

  useEffect(() => {
    if (!task || submitted || hydratedTask.current !== task.id || !Object.keys(data).length) return
    setSaveState('saving')
    const timer = window.setTimeout(() => {
      const duration = task.duration_seconds + Math.round((Date.now() - startedAt.current) / 1000)
      api.saveDraft(task.id, data, duration).then(() => setSaveState('saved')).catch(() => setSaveState('error'))
    }, 800)
    return () => window.clearTimeout(timer)
  }, [data, task, submitted])

  const elapsed = () => task ? task.duration_seconds + Math.round((Date.now() - startedAt.current) / 1000) : 0
  const completed = useMemo(() => tasks.filter((item) => item.status === 'submitted').length, [tasks])
  const move = (offset: number) => { const next = currentIndex + offset; if (next >= 0 && next < tasks.length) setCurrentIndex(next) }
  const refreshTask = async () => { if (!task) return; const updated = await api.task(task.id); setTasks((all) => all.map((item) => item.id === task.id ? updated : item)); hydratedTask.current = null }
  const save = async () => { if (!task || submitted) return; setSaveState('saving'); try { await api.saveDraft(task.id, data, elapsed()); await refreshTask(); setSaveState('saved'); setMessage('草稿已安全保存') } catch (e) { setSaveState('error'); setMessage((e as Error).message) } }
  const submit = async () => {
    if (!task || !schema || submitted) return
    const nextErrors = validate(schema, data); setErrors(nextErrors)
    if (Object.keys(nextErrors).length) { setMessage('还有必填项未完成'); return }
    try {
      await api.submit(task.id, data, elapsed())
      const updated = await api.tasks(projectId); setTasks(updated); setMessage('提交成功，结果已锁定')
      const next = updated.findIndex((item, index) => index > currentIndex && item.status !== 'submitted')
      if (next >= 0) setTimeout(() => setCurrentIndex(next), 450)
    } catch (e) { setMessage((e as Error).message) }
  }

  if (!schema || !task) return <main className="empty-state"><div className="loader" /><p>{message || '正在准备编码工作台…'}</p></main>
  return (
    <main className="coding-page">
      <header className="coding-header"><div><span className="eyebrow">编码工作台</span><h1>{task.material.material_data.sample_number}</h1></div><div className="coding-progress"><span>{completed} / {tasks.length} 已完成</span><div><i style={{ width: `${completed / tasks.length * 100}%` }} /></div></div></header>
      <div className="workspace"><MaterialViewer task={task} /><SchemaForm schema={schema} data={data} disabled={submitted} errors={errors} onChange={(value) => { setData(value); setErrors({}) }} /></div>
      <footer className="action-bar">
        <div className="pager"><button onClick={() => move(-1)} disabled={currentIndex === 0}><ArrowLeft size={18} /> 上一条</button><span>{currentIndex + 1} / {tasks.length}</span><button onClick={() => move(1)} disabled={currentIndex === tasks.length - 1}>下一条 <ArrowRight size={18} /></button></div>
        <div className="save-state">{saveState === 'saving' && <><Cloud size={16} /> 正在保存</>}{saveState === 'saved' && <><Check size={16} /> 草稿已同步</>}{saveState === 'error' && <><CloudOff size={16} /> 保存失败</>}{message && <b>{message}</b>}</div>
        <div className="actions">{submitted ? <button className="locked" disabled><LockKeyhole size={17} /> 已提交并锁定</button> : <><button className="secondary" onClick={save}><Save size={17} /> 保存草稿</button><button className="primary" onClick={submit}>提交并继续 <ArrowRight size={17} /></button></>}<button className="text-button" onClick={onResults}>查看结果</button></div>
      </footer>
    </main>
  )
}
