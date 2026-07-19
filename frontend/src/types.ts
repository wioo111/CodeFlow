export type Option = { value: string | number; label: string }
export type SchemaField = {
  key: string; label: string; type: 'string' | 'long_text' | 'number' | 'boolean' | 'enum' | 'multi_enum' | 'string_array' | 'object' | 'object_array'
  required?: boolean; readonly?: boolean; description?: string; options?: Option[]; min?: number; max?: number
  min_length?: number; max_length?: number; properties?: SchemaField[] | Record<string, Omit<SchemaField, 'key'>>; fields?: SchemaField[]
  items?: { properties?: SchemaField[] | Record<string, Omit<SchemaField, 'key'>> }
  required_when?: { field: string; equals?: unknown; value?: unknown }
}
export type ProjectSchema = { schema_id: string; version: string; primary_key: string; fields: SchemaField[]; rules?: unknown[]; relations?: unknown[] }
export type ViewConfig = { default_view?: string; table?: { columns?: string[] }; form?: { sections?: { title: string; description?: string; fields: string[] }[] } }
export type Project = { id:number; name:string; description:string; schema_id:string; schema_version:string; created_at:string; updated_at:string; record_count:number; invalid_count:number; approved_count:number; needs_review_count:number; latest_batch_id:number|null; latest_batch_name:string|null; batches?:Batch[] }
export type Batch = { id:number; name:string; data_version:string; source_filename:string; record_count:number; created_at:string }
export type ValidationError = { path:string; message:string; code:string }
export type ChangeLog = { id:number; field_path:string; old_value:unknown; new_value:unknown; operator:string; changed_at:string }
export type DataRecord = { id:number; batch_id:number; record_key:string; current_data:Record<string,unknown>; original_data?:Record<string,unknown>; validation_status:'valid'|'invalid'; validation_errors:ValidationError[]; review_status:'unreviewed'|'in_progress'|'approved'|'rejected'|'needs_review'; reviewer:string|null; reviewed_at:string|null; review_note:string; changed_fields:string[]; created_at:string; updated_at:string; change_logs?:ChangeLog[]; schema?:ProjectSchema; view_config?:ViewConfig; project_id?:number; previous_id?:number|null; next_id?:number|null }

