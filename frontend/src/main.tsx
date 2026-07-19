import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter><ConfigProvider locale={zhCN} theme={{token:{colorPrimary:'#244d3c',borderRadius:6,fontFamily:"'Noto Sans SC', sans-serif"}}}><App /></ConfigProvider></BrowserRouter></StrictMode>)
