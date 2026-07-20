import type { ReactNode } from 'react'
import { Space, Tag, Typography } from 'antd'
import type { Option, ProjectSchema, SchemaField, ViewConfig } from '../../types'
import { childFields, fieldMap } from '../../utils/data'
import './AIAnnotationView.css'

const {Text}=Typography

function optionLabel(options:Option[]|undefined,value:unknown){
  return options?.find((option)=>option.value===value)?.label??String(value)
}

function structuredValue(value:Record<string,unknown>,field:SchemaField){
  const children=childFields(field)
  const labels=new Map(children.map((child)=>[child.key,child.label]))
  return <div className="ai-object-value">{Object.entries(value).map(([key,item])=><div key={key}><span>{labels.get(key)??key}</span><b>{String(item??'—')}</b></div>)}</div>
}

function ReadonlyValue({field,value}:{field:SchemaField;value:unknown}):ReactNode{
  if(value===undefined||value===null||value==='')return <span className="ai-empty">AI 未提供</span>
  if(field.type==='boolean')return <Tag color={value?'green':'default'}>{value?'是':'否'}</Tag>
  if(field.type==='enum')return <Tag color="blue">{optionLabel(field.options,value)}</Tag>
  if(['multi_enum','string_array'].includes(field.type)&&Array.isArray(value))return <Space size={[4,4]} wrap>{value.map((item,index)=><Tag key={`${String(item)}-${index}`}>{field.type==='multi_enum'?optionLabel(field.options,item):String(item)}</Tag>)}</Space>
  if(field.type==='time_span'&&typeof value==='object'&&!Array.isArray(value)){
    const span=value as Record<string,unknown>
    return <span>{String(span.start??'—')} 秒 → {String(span.end??'—')} 秒</span>
  }
  if(field.type==='object'&&typeof value==='object'&&!Array.isArray(value))return structuredValue(value as Record<string,unknown>,field)
  if(field.type==='object_array'&&Array.isArray(value))return <div className="ai-object-list">{value.map((item,index)=><div key={index}><Text type="secondary">{field.label} {index+1}</Text>{typeof item==='object'&&item?structuredValue(item as Record<string,unknown>,field):String(item)}</div>)}</div>
  if(Array.isArray(value))return <Space size={[4,4]} wrap>{value.map((item,index)=><Tag key={`${String(item)}-${index}`}>{String(item)}</Tag>)}</Space>
  return <span>{String(value)}</span>
}

export function AIAnnotationView({data,schema,view}:{data:Record<string,unknown>;schema:ProjectSchema;view:ViewConfig}){
  const fields=fieldMap(schema.fields)
  const sections=view.form?.sections?.length?view.form.sections:[{title:'AI 标注字段',fields:schema.fields.map((field)=>field.key)}]
  return <div className="ai-annotation-view">
    {sections.map((section)=><section className="ai-readonly-section" key={section.title}>
      <div className="ai-section-title">{section.title}</div>
      {section.description&&<Text type="secondary">{section.description}</Text>}
      <div className="ai-field-list">{section.fields.map((key)=>fields[key]).filter(Boolean).map((field)=><div className="ai-readonly-field" key={field.key}>
        <label>{field.label}</label>
        {field.description&&<Text type="secondary">{field.description}</Text>}
        <div className={`ai-readonly-value ai-value-${field.type}`} role="textbox" aria-readonly="true"><ReadonlyValue field={field} value={data[field.key]}/></div>
      </div>)}</div>
    </section>)}
  </div>
}
