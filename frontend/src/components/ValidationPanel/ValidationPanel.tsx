import { Alert, List, Tag } from 'antd'
import type { ValidationError } from '../../types'

export function ValidationPanel({errors}:{errors:ValidationError[]}){return errors.length?<List bordered dataSource={errors} renderItem={(error)=><List.Item><Tag color="red">{error.path}</Tag><span>{error.message}</span><Tag>{error.code}</Tag></List.Item>}/>:<Alert type="success" showIcon message="Schema 校验通过"/>}

