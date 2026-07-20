import { Table, Tag } from 'antd'
import type { DataRecord } from '../../types'
import { displayValue } from '../../utils/data'

export function DiffViewer({record}:{record:DataRecord}){const rows=record.change_logs??[];return <Table rowKey="id" pagination={false} dataSource={rows} locale={{emptyText:'当前记录尚无修改'}} columns={[{title:'字段',dataIndex:'field_path',render:(value)=><Tag color="gold">{value}</Tag>},{title:'修改前',dataIndex:'old_value',render:displayValue},{title:'修改后',dataIndex:'new_value',render:displayValue},{title:'操作人',dataIndex:'operator'},{title:'时间',dataIndex:'changed_at',render:(value)=>new Date(value).toLocaleString('zh-CN')}]} />}

