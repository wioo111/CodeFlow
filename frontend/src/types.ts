export type Option = { value: string | number; label: string }
export type SchemaField = {
  key: string; label: string; type: 'string' | 'long_text' | 'number' | 'integer' | 'boolean' | 'enum' | 'multi_enum' | 'string_array' | 'object' | 'object_array' | 'time_point' | 'time_span' | 'asset_reference' | 'record_reference' | 'computed_readonly'
  required?: boolean; readonly?: boolean; description?: string; options?: Option[]; min?: number; max?: number
  min_length?: number; max_length?: number; properties?: SchemaField[] | Record<string, Omit<SchemaField, 'key'>>; fields?: SchemaField[]
  items?: { properties?: SchemaField[] | Record<string, Omit<SchemaField, 'key'>> }
  required_when?: { field: string; equals?: unknown; value?: unknown }
}
export type ProjectSchema = { schema_id: string; version: string; primary_key: string; fields: SchemaField[]; rules?: unknown[]; relations?: unknown[] }
export type ViewConfig = { default_view?: string; table?: { columns?: string[] }; form?: { sections?: { title: string; description?: string; fields: string[] }[] } }
export type Project = { id:number; name:string; description:string; schema_id:string; schema_version:string; created_at:string; updated_at:string; record_count:number; invalid_count:number; approved_count:number; needs_review_count:number; latest_batch_id:number|null; latest_batch_name:string|null; latest_dataset_version_id?:number|null;latest_dataset_version?:string|null;research_sample_count?:number;batches?:Batch[] }
export type Batch = { id:number; name:string; data_version:string; source_filename:string; record_count:number; created_at:string }
export type ValidationError = { path:string; message:string; code:string }
export type ChangeLog = { id:number; field_path:string; old_value:unknown; new_value:unknown; operator:string; changed_at:string }
export type DataRecord = { id:number; batch_id:number; record_key:string; current_data:Record<string,unknown>; original_data?:Record<string,unknown>; validation_status:'valid'|'invalid'; validation_errors:ValidationError[]; review_status:'unreviewed'|'in_progress'|'approved'|'rejected'|'needs_review'; reviewer:string|null; reviewed_at:string|null; review_note:string; changed_fields:string[]; created_at:string; updated_at:string; change_logs?:ChangeLog[]; schema?:ProjectSchema; view_config?:ViewConfig; project_id?:number; previous_id?:number|null; next_id?:number|null }

export type DatasetVersion = { id:number; dataset_version:string; digest:string; source_filename:string; sample_count:number; versions:Record<string,string>; frozen:boolean; created_at:string }
export type ResearchSample = { sample_record_id:number; sample_id:string; assignment_id:number; coder_id:string; stage:string; experiment_group:string; blind:boolean; status:string; sample:Record<string,unknown> }
export type SampleQueue = { items:ResearchSample[]; page:number; page_size:number; total:number;status_counts:Record<string,number> }
export type EvidenceSpan = { start?:number; end?:number; primary?:boolean; unlocatable?:boolean }
export type ResearchChangeLog = { id:number; field_path:string; old_value:unknown; new_value:unknown; change_type:string; operator:string; stage:string; reason:string; versions:Record<string,string>; changed_at:string }
export type Assignment = {
  id:number; project_id:number; dataset_version_id:number; sample_record_id:number; sample_id:string; coder_id:string; stage:string; experiment_group:string; blind:boolean;
  evidence_config:Record<string,boolean>; status:string; active_seconds:number; annotation_schema:ProjectSchema; view_config:ViewConfig; codebook:{version?:string;categories?:Record<string,unknown>[]}; versions:Record<string,string>;
  human_annotation:{current_data:Record<string,unknown>;submitted_data:Record<string,unknown>|null;field_decisions:Record<string,string>;evidence_spans:EvidenceSpan[];versions:Record<string,string>;locked:boolean};
  ai_raw_annotation:{id:number;model_run_id:number;raw_output:Record<string,unknown>;immutable:boolean;validation_errors:ValidationError[]}|null;
  change_logs:ResearchChangeLog[];
}
export type SampleDetail = { sample_record_id:number;sample_id:string;dataset_version_id:number;project_id:number;data:Record<string,unknown>;assignment_id:number;evidence_config:Record<string,boolean>;versions:Record<string,string> }
export type FrameEvidence = { frame_id:string;sample_id:string;time_seconds:number;frame_set:string;path:string }
export type CommentEvidence = { comment_id:string;sample_id:string;text:string;like_count:number;rank_by_like:number;comment_type:string;reply_count?:number;created_at?:string }
export type PackageReport = {valid:boolean;errors:{file?:string;line?:number;table?:string;field?:string;message:string}[];warnings:{message:string}[];project_id:string;dataset_version:string;digest:string;tables:Record<string,number>;sample_count:number;media_root_bound:boolean;duplicate:boolean}
