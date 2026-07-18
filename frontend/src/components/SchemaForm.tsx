import type { ProjectSchema, SchemaField } from '../types'

type Value = string | number | boolean | string[] | null
type FormData = Record<string, Value>

function Field({ field, value, disabled, onChange }: { field: SchemaField; value: Value; disabled: boolean; onChange: (value: Value) => void }) {
  const common = { id: field.id, disabled, 'aria-label': field.label }
  if (field.type === 'long_text') return <textarea {...common} rows={5} value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} placeholder="请输入客观描述…" />
  if (field.type === 'short_text') return <input {...common} value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} placeholder="可选补充说明" />
  if (field.type === 'number') return <input {...common} type="number" value={(value as number) ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
  if (field.type === 'single_select') return (
    <div className="option-grid">{field.options?.map((option) => (
      <label key={option.value} className={`choice ${(value === option.value) ? 'selected' : ''}`}>
        <input type="radio" name={field.id} value={option.value} checked={value === option.value} disabled={disabled} onChange={() => onChange(option.value)} />
        <span className="choice-code">{option.value}</span><span>{option.label}</span>
      </label>
    ))}</div>
  )
  if (field.type === 'multi_select') {
    const selected = (value as string[]) ?? []
    return <div className="chip-grid">{field.options?.map((option) => (
      <label key={option.value} className={`chip ${selected.includes(option.value) ? 'selected' : ''}`}>
        <input type="checkbox" checked={selected.includes(option.value)} disabled={disabled} onChange={() => onChange(selected.includes(option.value) ? selected.filter((v) => v !== option.value) : [...selected, option.value])} />
        {option.label}
      </label>
    ))}</div>
  }
  if (field.type === 'boolean') return (
    <div className="boolean-group">{[[true, '是'], [false, '否']].map(([option, label]) => (
      <button key={label as string} type="button" className={value === option ? 'active' : ''} disabled={disabled} onClick={() => onChange(option as boolean)}>{label as string}</button>
    ))}</div>
  )
  if (field.type === 'scale') {
    const min = field.min ?? 1; const max = field.max ?? 5
    return <div className="scale-group">{Array.from({ length: max - min + 1 }, (_, i) => min + i).map((n) => (
      <button key={n} type="button" className={value === n ? 'active' : ''} disabled={disabled} onClick={() => onChange(n)}>{n}</button>
    ))}</div>
  }
  return null
}

export function SchemaForm({ schema, data, disabled, errors, onChange }: { schema: ProjectSchema; data: FormData; disabled: boolean; errors: Record<string, string>; onChange: (data: FormData) => void }) {
  return (
    <section className="form-panel panel">
      <div className="panel-kicker"><span>编码表单</span><span>Schema {schema.version}</span></div>
      <div className="fields">
        {schema.fields.map((field, index) => (
          <div className={`field ${errors[field.id] ? 'field-error' : ''}`} key={field.id}>
            <label className="field-label" htmlFor={field.id}><span>{String(index + 1).padStart(2, '0')}</span>{field.label}{field.required && <b>*</b>}</label>
            {field.description && <p className="field-help">{field.description}</p>}
            <Field field={field} value={data[field.id]} disabled={disabled} onChange={(value) => onChange({ ...data, [field.id]: value })} />
            {errors[field.id] && <p className="error-text">{errors[field.id]}</p>}
          </div>
        ))}
      </div>
    </section>
  )
}

