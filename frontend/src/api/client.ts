import type { Assignment, CommentEvidence, DataRecord, DatasetVersion, FrameEvidence, PackageReport, Project, ProjectSchema, SampleDetail, SampleQueue, ViewConfig } from '../types'

async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response=await fetch(`/api${path}`,init)
  if(!response.ok){const body=await response.json().catch(()=>({detail:'请求失败'}));const detail=body.detail;throw new Error(typeof detail==='string'?detail:detail?.message||JSON.stringify(detail))}
  return response.json() as Promise<T>
}
const json=(method:string,body:unknown):RequestInit=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})

export const api={
  projects:()=>request<Project[]>('/projects'),
  project:(id:number)=>request<Project>(`/projects/${id}`),
  schema:(id:number)=>request<ProjectSchema>(`/projects/${id}/schema`),
  view:(id:number)=>request<ViewConfig>(`/projects/${id}/view`),
  importProject:(data:FormData)=>request<{project_id:number;batch_id:number;record_count:number;invalid_count:number}>('/imports',{method:'POST',body:data}),
  records:(batchId:number,params:Record<string,string>={})=>request<DataRecord[]>(`/batches/${batchId}/records?${new URLSearchParams(params)}`),
  record:(id:number)=>request<DataRecord>(`/records/${id}`),
  updateRecord:(id:number,current_data:Record<string,unknown>,review_status?:string,review_note?:string)=>request<DataRecord>(`/records/${id}`,json('PATCH',{current_data,operator:'local_reviewer',review_status,review_note})),
  review:(id:number,status:string,note='')=>request<DataRecord>(`/records/${id}/review`,json('PATCH',{status,operator:'local_reviewer',note})),
  bulk:(batchId:number,payload:unknown)=>request<{updated:number}>(`/batches/${batchId}/records/bulk`,json('PATCH',payload)),
  validation:(batchId:number)=>request<{total:number;valid:number;invalid:number;records:{record_id:number;record_key:string;errors:{path:string;message:string;code:string}[]}[]}>(`/validation/batches/${batchId}`),
  exportUrl:(batchId:number,format:string,source='current',status='')=>`/api/exports/batches/${batchId}/${format}?source=${source}${status?`&review_status=${status}`:''}`,
  preflightPackage:(data:FormData)=>request<PackageReport>('/dataset-packages/preflight',{method:'POST',body:data}),
  importPackage:(data:FormData)=>request<{status:string;project_id:number;dataset_version_id:number;sample_count:number}>('/dataset-packages/import',{method:'POST',body:data}),
  datasetVersions:(projectId:number)=>request<DatasetVersion[]>(`/projects/${projectId}/dataset-versions`),
  researchSamples:(projectId:number,params:Record<string,string>={})=>request<SampleQueue>(`/projects/${projectId}/samples?${new URLSearchParams(params)}`),
  sample:(sampleId:number,assignmentId:number)=>request<SampleDetail>(`/samples/${sampleId}?assignment_id=${assignmentId}`),
  assignment:(id:number)=>request<Assignment>(`/assignments/${id}`),
  frames:(sampleId:number,assignmentId:number)=>request<FrameEvidence[]>(`/samples/${sampleId}/frames?assignment_id=${assignmentId}`),
  comments:(sampleId:number,assignmentId:number)=>request<CommentEvidence[]>(`/samples/${sampleId}/comments?assignment_id=${assignmentId}`),
  saveDraft:(id:number,payload:unknown)=>request<{status:string;locked:boolean;validation_errors:{path:string;message:string}[];saved_at:string}>(`/assignments/${id}/draft`,json('PATCH',payload)),
  submitAssignment:(id:number,payload:unknown)=>request<{status:string;locked:boolean;submitted_at:string}>(`/assignments/${id}/submit`,json('POST',payload)),
  researchExport:async(projectId:number)=>{const response=await fetch('/api/exports',json('POST',{project_id:projectId,anonymize_coders:false}));if(!response.ok)throw new Error('导出失败');return response.blob()},
}
