import { App as AntdApp, Button, Card, Col, Empty, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd'
import { Download, PlayCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { DatasetVersion, ResearchSample } from '../types'

export function ResearchProjectPage(){
  const {message}=AntdApp.useApp()
  const {projectId}=useParams();const [search,setSearch]=useSearchParams();const navigate=useNavigate()
  const [versions,setVersions]=useState<DatasetVersion[]>([]);const [items,setItems]=useState<ResearchSample[]>([]);const [total,setTotal]=useState(0);const [counts,setCounts]=useState<Record<string,number>>({});const [loading,setLoading]=useState(true)
  const dataset=Number(search.get('dataset'))||versions[0]?.id
  useEffect(()=>{api.datasetVersions(Number(projectId)).then((rows)=>{setVersions(rows);if(!search.get('dataset')&&rows[0])setSearch({dataset:String(rows[0].id)},{replace:true})})},[projectId,search,setSearch])
  useEffect(()=>{if(!dataset)return;api.researchSamples(Number(projectId),{dataset_version_id:String(dataset)}).then((queue)=>{setItems(queue.items);setTotal(queue.total);setCounts(queue.status_counts)}).finally(()=>setLoading(false))},[dataset,projectId])
  const download=async()=>{try{const blob=await api.researchExport(Number(projectId));const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='codeflow_research_export.zip';anchor.click();URL.revokeObjectURL(url)}catch(e){message.error((e as Error).message)}}
  return <main className="page research-overview">
    <header className="page-header"><div><Typography.Text type="secondary">Schema 驱动 · 多表研究数据</Typography.Text><Typography.Title level={2}>标注任务队列</Typography.Title></div><Space><Select value={dataset} style={{width:220}} onChange={(value)=>{setLoading(true);setSearch({dataset:String(value)})}} options={versions.map((item)=>({value:item.id,label:`${item.dataset_version} · ${item.sample_count} 条`}))}/><Button icon={<Download size={16}/>} onClick={download}>研究导出</Button></Space></header>
    <Row gutter={16} style={{marginBottom:18}}><Col span={6}><Card><Statistic title="当前队列" value={total} suffix="条"/></Card></Col><Col span={6}><Card><Statistic title="待处理" value={counts.pending??0}/></Card></Col><Col span={6}><Card><Statistic title="进行中" value={counts.in_progress??0}/></Card></Col><Col span={6}><Card><Statistic title="已提交" value={counts.submitted??0}/></Card></Col></Row>
    <Card>{items.length?<Table rowKey="assignment_id" loading={loading} dataSource={items} pagination={{pageSize:25}} columns={[
      {title:'样本',dataIndex:'sample_id',render:(value)=><b>{value}</b>},{title:'阶段',dataIndex:'stage',render:(value)=><Tag>{value}</Tag>},{title:'实验组',dataIndex:'experiment_group'},
      {title:'状态',dataIndex:'status',render:(value)=><Tag color={value==='submitted'?'green':value==='in_progress'?'blue':'default'}>{value}</Tag>},
      {title:'可见证据',render:(_,row)=>Object.entries(row.sample).slice(0,3).map(([key,value])=><Tag key={key}>{key}: {String(value).slice(0,20)}</Tag>)},
      {title:'操作',render:(_,row)=><Button type="primary" icon={<PlayCircle size={16}/>} onClick={()=>navigate(`/research/assignment/${row.assignment_id}`)}>进入工作台</Button>},
    ]}/>:<Empty description="当前用户没有可处理任务"/>}</Card>
  </main>
}
