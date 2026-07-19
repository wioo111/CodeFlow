import { create } from 'zustand'
import { api } from '../api/client'
import type { DataRecord, ProjectSchema, ViewConfig } from '../types'

type WorkspaceState={batchId:number|null;projectId:number|null;records:DataRecord[];schema:ProjectSchema|null;view:ViewConfig|null;loading:boolean;load:(projectId:number,batchId:number,filters?:Record<string,string>)=>Promise<void>;refreshRecords:(filters?:Record<string,string>)=>Promise<void>;replaceRecord:(record:DataRecord)=>void}
export const useWorkspace=create<WorkspaceState>((set,get)=>({
  batchId:null,projectId:null,records:[],schema:null,view:null,loading:false,
  load:async(projectId,batchId,filters={})=>{set({loading:true,projectId,batchId});const [records,schema,view]=await Promise.all([api.records(batchId,filters),api.schema(projectId),api.view(projectId)]);set({records,schema,view,loading:false})},
  refreshRecords:async(filters={})=>{const batchId=get().batchId;if(!batchId)return;set({loading:true});const records=await api.records(batchId,filters);set({records,loading:false})},
  replaceRecord:(record)=>set((state)=>({records:state.records.map((item)=>item.id===record.id?record:item)})),
}))

