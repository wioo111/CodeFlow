import { Alert, Button, Card, Col, Descriptions, Form, Input, List, Row, Space, Steps, Tabs, Tag, Typography, Upload } from 'antd'
import { Archive, FileJson, FolderOpen, UploadCloud } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { UploadFile } from 'antd'
import { api } from '../api/client'
import type { PackageReport } from '../types'

function PackageImport(){
  const [files,setFiles]=useState<UploadFile[]>([])
  const [report,setReport]=useState<PackageReport|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const [form]=Form.useForm()
  const navigate=useNavigate()
  const payload=()=>{const data=new FormData();const file=files[0]?.originFileObj;if(!file)throw new Error('请选择一个标准数据包 ZIP');data.append('package_file',file);const root=form.getFieldValue('media_root');if(root)data.append('media_root',root);return data}
  const preflight=async()=>{setLoading(true);setError('');try{setReport(await api.preflightPackage(payload()))}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  const importNow=async()=>{setLoading(true);setError('');try{const result=await api.importPackage(payload());navigate(`/research/project/${result.project_id}?dataset=${result.dataset_version_id}`)}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  return <div>
    <Typography.Paragraph type="secondary">上传包含 <code>codeflow_project.json</code>、多张 JSONL 表和 Schema/View/Codebook 的完整归档。系统先预检，全部通过后才事务化导入。</Typography.Paragraph>
    <Steps current={report?.valid?1:0} items={[{title:'选择数据包'},{title:'预检通过'},{title:'整体导入'}]}/>
    {error&&<Alert type="error" showIcon message={error} style={{marginTop:16}}/>}
    <Form form={form} layout="vertical" style={{marginTop:20}}>
      <Row gutter={20}>
        <Col span={14}><Upload.Dragger fileList={files} accept=".zip" maxCount={1} beforeUpload={()=>false} onChange={({fileList})=>{setFiles(fileList.slice(-1));setReport(null)}}><Archive/><p>标准数据包 ZIP</p><small>一次选择，自动读取入口与全部声明表</small></Upload.Dragger></Col>
        <Col span={10}><Card title={<Space><FolderOpen size={17}/>媒体根目录绑定</Space>}><Form.Item name="media_root" label="本机媒体根目录"><Input placeholder="例如 D:\research\media" onChange={()=>setReport(null)}/></Form.Item><Typography.Text type="secondary">仅保存为项目级授权绑定，不写回研究数据；所有媒体请求都进行路径逃逸检查。</Typography.Text></Card></Col>
      </Row>
      <Button type="primary" size="large" block loading={loading} onClick={preflight} style={{marginTop:20}}>运行导入预检</Button>
    </Form>
    {report&&<Card title={<Space>预检报告<Tag color={report.valid?'green':'red'}>{report.valid?'可导入':'存在错误'}</Tag>{report.duplicate&&<Tag color="orange">版本已存在</Tag>}</Space>} style={{marginTop:20}}>
      <Descriptions size="small" column={3} items={[{key:'project',label:'项目 ID',children:report.project_id},{key:'version',label:'数据版本',children:report.dataset_version},{key:'samples',label:'样本数',children:report.sample_count},{key:'tables',label:'数据表',children:Object.entries(report.tables).map(([name,count])=><Tag key={name}>{name} · {count}</Tag>)},{key:'digest',label:'数据摘要',span:2,children:<code>{report.digest.slice(0,20)}…</code>}]}/>
      {report.errors.length>0?<List header="必须修复" dataSource={report.errors} renderItem={(item)=><List.Item><Alert type="error" showIcon message={item.message} description={[item.file,item.line&&`第 ${item.line} 行`,item.table,item.field].filter(Boolean).join(' · ')}/></List.Item>}/>:null}
      {report.warnings.length>0?<List header="提醒" dataSource={report.warnings} renderItem={(item)=><List.Item>{item.message}</List.Item>}/>:null}
      <Button type="primary" size="large" block disabled={!report.valid||report.duplicate} loading={loading} onClick={importNow}>{report.duplicate?'该版本已导入':'确认整体导入'}</Button>
    </Card>}
  </div>
}

function LegacyImport(){
  const [schema,setSchema]=useState<UploadFile[]>([]);const [view,setView]=useState<UploadFile[]>([]);const [data,setData]=useState<UploadFile[]>([]);const [loading,setLoading]=useState(false);const [error,setError]=useState('');const navigate=useNavigate()
  const submit=async(values:Record<string,string>)=>{if(!schema[0]?.originFileObj||!data[0]?.originFileObj){setError('请选择 Schema 与 JSON/JSONL 数据文件');return}setLoading(true);setError('');try{const form=new FormData();Object.entries(values).forEach(([key,value])=>form.append(key,value));form.append('schema_file',schema[0].originFileObj);form.append('data_file',data[0].originFileObj);if(view[0]?.originFileObj)form.append('view_file',view[0].originFileObj);const result=await api.importProject(form);navigate(`/project/${result.project_id}/table?batch=${result.batch_id}`)}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  const uploadProps=(files:UploadFile[],setter:(files:UploadFile[])=>void,accept:string)=>({fileList:files,accept,beforeUpload:()=>false,onChange:({fileList}:{fileList:UploadFile[]})=>setter(fileList.slice(-1))})
  return <div>{error&&<Alert type="error" showIcon message={error}/>}<Form layout="vertical" onFinish={submit} initialValues={{batch_name:'首批数据',data_version:'v1'}}><Card title="旧版单表项目信息"><Row gutter={16}><Col span={12}><Form.Item name="project_name" label="项目名称" rules={[{required:true}]}><Input/></Form.Item></Col><Col span={12}><Form.Item name="batch_name" label="批次名称"><Input/></Form.Item></Col><Col span={12}><Form.Item name="data_version" label="数据版本"><Input/></Form.Item></Col><Col span={24}><Form.Item name="description" label="项目说明"><Input.TextArea/></Form.Item></Col></Row></Card><Row gutter={16}><Col span={8}><Upload.Dragger {...uploadProps(schema,setSchema,'.json')}><FileJson/><p>Schema JSON</p></Upload.Dragger></Col><Col span={8}><Upload.Dragger {...uploadProps(view,setView,'.json')}><FileJson/><p>View JSON（可选）</p></Upload.Dragger></Col><Col span={8}><Upload.Dragger {...uploadProps(data,setData,'.json,.jsonl')}><UploadCloud/><p>数据 JSON / JSONL</p></Upload.Dragger></Col></Row><Button type="primary" htmlType="submit" size="large" loading={loading} block style={{marginTop:24}}>按旧格式导入</Button></Form></div>
}

export function ImportPage(){return <main className="page narrow-page"><Typography.Title>导入研究数据</Typography.Title><Tabs defaultActiveKey="package" items={[{key:'package',label:'标准多表数据包',children:<PackageImport/>},{key:'legacy',label:'旧版 Schema + 单表',children:<LegacyImport/>}]}/></main>}
