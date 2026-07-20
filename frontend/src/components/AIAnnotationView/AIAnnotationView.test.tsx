import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AIAnnotationView } from './AIAnnotationView'
import type { ProjectSchema, ViewConfig } from '../../types'

const schema:ProjectSchema={schema_id:'test',version:'1',primary_key:'id',fields:[
  {key:'literal_content',label:'画面事实',type:'long_text'},
  {key:'final_type',label:'最终类别',type:'enum',options:[{value:'controversy',label:'争议'}]},
  {key:'requires_context',label:'需要外部语境',type:'boolean'},
]}
const view:ViewConfig={form:{sections:[{title:'内容理解',fields:['literal_content']},{title:'分类与质量',fields:['final_type','requires_context']}]}}

describe('AIAnnotationView',()=>{
  it('按人工表单的分组和字段展示 AI 值，而不是输出 JSON',()=>{
    const {container}=render(<AIAnnotationView data={{literal_content:'球员向裁判申诉',final_type:'controversy',requires_context:false}} schema={schema} view={view}/>)
    expect(screen.getByText('内容理解')).toBeVisible()
    expect(screen.getByText('画面事实')).toBeVisible()
    expect(screen.getByText('球员向裁判申诉')).toBeVisible()
    expect(screen.getByText('争议')).toBeVisible()
    expect(screen.getByText('否')).toBeVisible()
    expect(screen.queryByText('final_type')).not.toBeInTheDocument()
    expect(container.querySelectorAll('[role="textbox"]')).toHaveLength(3)
    expect(container.textContent).not.toContain('{"')
  })
})
