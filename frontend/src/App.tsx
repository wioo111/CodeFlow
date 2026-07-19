import { DatabaseOutlined, FileAddOutlined, FolderOpenOutlined } from '@ant-design/icons'
import { Layout, Menu } from 'antd'
import { Braces } from 'lucide-react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { ExportPage } from './pages/ExportPage'
import { ImportPage } from './pages/ImportPage'
import { ProjectListPage } from './pages/ProjectListPage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import { RecordEditorPage } from './pages/RecordEditorPage'
import { TableWorkspacePage } from './pages/TableWorkspacePage'
import { ValidationPage } from './pages/ValidationPage'

export default function App(){const navigate=useNavigate();const location=useLocation();const selected=location.pathname.includes('/import')?'import':location.pathname==='/'||location.pathname==='/project'?'projects':'workspace';return <Layout className="app-layout"><Layout.Sider width={224} theme="dark" className="main-sider"><Link to="/project" className="brand-v2"><Braces/><span>Code<strong>Flow</strong></span></Link><Menu theme="dark" mode="inline" selectedKeys={[selected]} onClick={({key})=>{if(key==='projects')navigate('/project');if(key==='import')navigate('/project/import')}} items={[{key:'projects',icon:<FolderOpenOutlined/>,label:'项目列表'},{key:'import',icon:<FileAddOutlined/>,label:'导入项目'},{key:'workspace',icon:<DatabaseOutlined/>,label:'数据工作区',disabled:selected!=='workspace'}]}/><div className="sider-foot"><span>Local MVP</span><small>Schema-driven review</small></div></Layout.Sider><Layout.Content className="main-content"><Routes><Route path="/" element={<Navigate to="/project" replace/>}/><Route path="/project" element={<ProjectListPage/>}/><Route path="/project/import" element={<ImportPage/>}/><Route path="/project/:projectId" element={<ProjectOverviewPage/>}/><Route path="/project/:projectId/table" element={<TableWorkspacePage/>}/><Route path="/project/:projectId/record/:recordId" element={<RecordEditorPage/>}/><Route path="/project/:projectId/validation" element={<ValidationPage/>}/><Route path="/project/:projectId/export" element={<ExportPage/>}/></Routes></Layout.Content></Layout>}
