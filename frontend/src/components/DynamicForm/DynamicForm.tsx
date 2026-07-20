import { Button, Card, Checkbox, Input, InputNumber, Select, Space, Typography } from 'antd'
import { Controller, useFieldArray, useFormContext } from 'react-hook-form'
import type { ProjectSchema, SchemaField, ViewConfig } from '../../types'
import { childFields, fieldMap } from '../../utils/data'

const {Text}=Typography
type Props={schema:ProjectSchema;view:ViewConfig;errors?:Record<string,string>;changedFields?:string[]}

function ObjectArray({field,name}:{field:SchemaField;name:string}){const {control}=useFormContext();const {fields,append,remove}=useFieldArray({control,name});const children=childFields(field);return <div className="object-array"><Space orientation="vertical" style={{width:'100%'}}>{fields.map((item,index)=><Card key={item.id} size="small" title={`${field.label} ${index+1}`} extra={<Button danger type="text" onClick={()=>remove(index)}>删除</Button>}><FieldList fields={children} prefix={`${name}.${index}`} /></Card>)}</Space><Button style={{marginTop:10}} onClick={()=>append({})}>添加{field.label}</Button></div>}

function FieldControl({field,name}:{field:SchemaField;name:string}){const {control}=useFormContext();if(field.type==='object')return <Card size="small"><FieldList fields={childFields(field)} prefix={name}/></Card>;if(field.type==='object_array')return <ObjectArray field={field} name={name}/>;return <Controller name={name} control={control} render={({field:input})=>{
  if(field.type==='long_text')return <Input.TextArea {...input} value={(input.value as string)??''} rows={4} disabled={field.readonly}/>
  if(['number','integer','time_point'].includes(field.type))return <InputNumber {...input} value={input.value as number|null} min={field.min} max={field.max} precision={field.type==='integer'?0:undefined} disabled={field.readonly} style={{width:'100%'}}/>
  if(field.type==='boolean')return <Checkbox checked={Boolean(input.value)} onChange={(e)=>input.onChange(e.target.checked)} disabled={field.readonly}>是</Checkbox>
  if(field.type==='enum')return <Select {...input} value={input.value} options={field.options} allowClear disabled={field.readonly}/>
  if(field.type==='multi_enum')return <Select {...input} value={input.value??[]} mode="multiple" options={field.options} disabled={field.readonly}/>
  if(field.type==='string_array')return <Select {...input} value={input.value??[]} mode="tags" tokenSeparators={[',']} disabled={field.readonly}/>
  return <Input {...input} value={(input.value as string)??''} disabled={field.readonly||field.type==='computed_readonly'}/>
}}/>}

function FieldList({fields,prefix='',errors={},changedFields=[]}:{fields:SchemaField[];prefix?:string;errors?:Record<string,string>;changedFields?:string[]}){return <>{fields.map((field)=>{const name=prefix?`${prefix}.${field.key}`:field.key;return <div className={`dynamic-field ${errors[name]?'has-error':''}`} key={name}><label>{field.label}{field.required&&<b> *</b>}{changedFields.includes(name)&&<span className="changed-badge">已修改</span>}</label>{field.description&&<Text type="secondary">{field.description}</Text>}<FieldControl field={field} name={name}/>{errors[name]&&<div className="field-error-text">{errors[name]}</div>}</div>})}</>}

export function DynamicForm({schema,view,errors={},changedFields=[]}:Props){const map=fieldMap(schema.fields);const sections=view.form?.sections?.length?view.form.sections:[{title:'记录字段',fields:schema.fields.map((field)=>field.key)}];return <Space orientation="vertical" size={16} style={{width:'100%'}}>{sections.map((section)=><Card className="form-section" key={section.title} title={section.title}>{section.description&&<Text type="secondary">{section.description}</Text>}<FieldList fields={section.fields.map((path)=>map[path]).filter(Boolean)} errors={errors} changedFields={changedFields}/></Card>)}</Space>}
