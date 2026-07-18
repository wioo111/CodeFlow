export type Option = { value: string; label: string }
export type SchemaField = {
  id: string
  label: string
  description?: string
  type: 'short_text' | 'long_text' | 'single_select' | 'multi_select' | 'boolean' | 'number' | 'scale'
  required?: boolean
  options?: Option[]
  min?: number
  max?: number
}
export type ProjectSchema = { version: string; fields: SchemaField[] }
export type Project = {
  id: number; name: string; description: string; schema_version: string; codebook_version: string
  status: string; created_at: string; total: number; completed: number
}
export type Task = {
  id: number; project_id: number; stage: string; status: string; assigned_at: string
  submitted_at: string | null; duration_seconds: number
  coder: { id: number; name: string }
  material: { id: number; material_type: string; material_data: Record<string, string>; metadata: Record<string, string> }
  annotation: null | { annotation_data: Record<string, unknown>; is_submitted: boolean; schema_version: string; codebook_version: string; updated_at: string }
}
export type ResultRow = {
  assignment_id: number; sample_number: string; coder: string; stage: string; status: string
  submitted_at: string | null; duration_seconds: number; schema_version: string | null
  codebook_version: string | null; annotation_data: Record<string, unknown>
}

