import { Button, Checkbox, InputNumber, Slider, Space, Switch, Tag, Typography } from 'antd'
import { Crosshair, Plus, RotateCcw, Trash2 } from 'lucide-react'
import type { EvidenceSpan } from '../../types'

type Props={spans:EvidenceSpan[];duration:number;currentTime:number;onSeek:(seconds:number)=>void;onChange:(spans:EvidenceSpan[])=>void;loop:boolean;onLoop:(value:boolean)=>void}

export function EvidenceTimeline({spans,duration,currentTime,onSeek,onChange,loop,onLoop}:Props){
  const update=(index:number,patch:Partial<EvidenceSpan>)=>onChange(spans.map((item,i)=>i===index?{...item,...patch}:item))
  const makePrimary=(index:number)=>onChange(spans.map((item,i)=>({...item,primary:i===index})))
  return <div className="evidence-timeline"><Space wrap style={{marginBottom:12}}><Button icon={<Plus size={15}/>} onClick={()=>onChange([...spans,{start:Math.max(0,currentTime),end:Math.min(duration,currentTime+1),primary:spans.length===0}])}>添加候选区间</Button><Switch checked={loop} onChange={onLoop}/><span>循环主区间</span><Tag>{spans.length} 个区间</Tag></Space>
    {spans.map((span,index)=><div className="span-editor" key={index}>
      <Space wrap><b>区间 {index+1}</b><Checkbox checked={span.primary} onChange={()=>makePrimary(index)}>主区间</Checkbox><Checkbox checked={span.unlocatable} onChange={(event)=>update(index,{unlocatable:event.target.checked})}>无法准确定位</Checkbox><Button danger type="text" icon={<Trash2 size={14}/>} onClick={()=>onChange(spans.filter((_,i)=>i!==index))}>删除</Button></Space>
      {!span.unlocatable&&<><Slider range min={0} max={Math.max(duration,.1)} step={.1} value={[span.start??0,span.end??Math.min(duration,1)]} onChange={([start,end])=>update(index,{start,end})}/><Space wrap><span>开始</span><InputNumber min={0} max={duration} step={.1} value={span.start} onChange={(value)=>update(index,{start:value??0})}/><Button icon={<Crosshair size={14}/>} onClick={()=>update(index,{start:Number(currentTime.toFixed(1))})}>取当前</Button><span>结束</span><InputNumber min={0} max={duration} step={.1} value={span.end} onChange={(value)=>update(index,{end:value??0})}/><Button icon={<Crosshair size={14}/>} onClick={()=>update(index,{end:Number(currentTime.toFixed(1))})}>取当前</Button><Button icon={<RotateCcw size={14}/>} onClick={()=>onSeek(span.start??0)}>播放区间</Button></Space></>}
    </div>)}
    {!spans.length&&<Typography.Text type="secondary">播放到证据出现的位置，然后添加候选区间并精确调整边界。</Typography.Text>}
  </div>
}
