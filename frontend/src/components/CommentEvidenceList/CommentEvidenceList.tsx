import { Empty, Tag, Typography } from 'antd'
import { Heart, MessageCircle } from 'lucide-react'
import type { CommentEvidence } from '../../types'

const typeLabels:Record<string,string>={
  text:'文字',image:'图片',video:'视频',sticker:'表情',mixed:'混合',empty:'空评论',unknown:'未知',
}

export function CommentEvidenceList({comments}:{comments:CommentEvidence[]}){
  if(!comments.length)return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="评论未授权或不存在"/>
  return <div className="comment-stream" aria-label="评论证据列表">
    {comments.map((comment)=><article className="comment-item" key={comment.comment_id}>
      <div className="comment-item-head">
        <span className="comment-rank">#{comment.rank_by_like}</span>
        <span className="comment-count"><Heart size={13} aria-hidden/> {comment.like_count}</span>
        {comment.reply_count!==undefined&&<span className="comment-count"><MessageCircle size={13} aria-hidden/> {comment.reply_count}</span>}
        <Tag variant="filled">{typeLabels[comment.comment_type]??comment.comment_type}</Tag>
      </div>
      <Typography.Paragraph className="comment-text">{comment.text||'（无文字内容）'}</Typography.Paragraph>
      {comment.created_at&&<time className="comment-time">{comment.created_at}</time>}
    </article>)}
  </div>
}
