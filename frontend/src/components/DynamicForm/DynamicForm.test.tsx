import { fireEvent, render, screen } from '@testing-library/react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { describe, expect, it } from 'vitest'
import type { ProjectSchema, ViewConfig } from '../../types'
import { DynamicForm } from './DynamicForm'

const schema:ProjectSchema={schema_id:'inventory',version:'1',primary_key:'sku',fields:[
  {key:'sku',label:'SKU',type:'string',required:true,readonly:true},
  {key:'name',label:'商品名称',type:'string',required:true},
  {key:'warehouse',label:'仓储信息',type:'object',properties:[{key:'zone',label:'库区',type:'string',required:true}]},
  {key:'tags',label:'标签',type:'string_array'},
]}
const view:ViewConfig={form:{sections:[{title:'商品信息',fields:['sku','name','tags']},{title:'仓储位置',fields:['warehouse']}]}}

function Harness(){const methods=useForm<Record<string,unknown>>({defaultValues:{sku:'SKU-1',name:'键盘',warehouse:{zone:'A'},tags:['办公']}});const values=useWatch({control:methods.control});return <FormProvider {...methods}><DynamicForm schema={schema} view={view} changedFields={['name']}/><output>{JSON.stringify(values)}</output></FormProvider>}

describe('DynamicForm',()=>{it('renders fields and nested objects from Schema/View without business code',()=>{render(<Harness/>);expect(screen.getByText('商品信息')).toBeInTheDocument();expect(screen.getByText('仓储位置')).toBeInTheDocument();expect(screen.getByText('库区')).toBeInTheDocument();expect(screen.getByText('已修改')).toBeInTheDocument();fireEvent.change(screen.getByDisplayValue('键盘'),{target:{value:'机械键盘'}});expect(screen.getByRole('status')).toHaveTextContent('"name":"机械键盘"')})})

