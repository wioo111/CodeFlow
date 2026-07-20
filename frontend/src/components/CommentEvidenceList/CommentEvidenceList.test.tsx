import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CommentEvidenceList } from './CommentEvidenceList'

describe('CommentEvidenceList',()=>{
  it('直接按排名展示全部评论正文，无需逐条展开',()=>{
    render(<CommentEvidenceList comments={[
      {comment_id:'C1',sample_id:'V1',text:'第一条评论',like_count:32,rank_by_like:1,comment_type:'text'},
      {comment_id:'C2',sample_id:'V1',text:'第二条评论',like_count:18,rank_by_like:2,comment_type:'text'},
    ]}/>)
    expect(screen.getByText('第一条评论')).toBeVisible()
    expect(screen.getByText('第二条评论')).toBeVisible()
    expect(screen.getByText('#1')).toBeVisible()
    expect(screen.getByText('#2')).toBeVisible()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })
})
