import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { SchemaForm } from './SchemaForm'
import type { ProjectSchema } from '../types'

const schema: ProjectSchema = {
  version: 'test-v1',
  fields: [
    { id: 'title', label: '标题', type: 'short_text', required: true },
    { id: 'kind', label: '类型', type: 'single_select', options: [{ value: 'A', label: '选项 A' }] },
    { id: 'flag', label: '是否明确', type: 'boolean' },
    { id: 'score', label: '信心', type: 'scale', min: 1, max: 3 },
  ],
}

function Harness() {
  const [data, setData] = useState<Record<string, string | number | boolean | string[] | null>>({})
  return <><SchemaForm schema={schema} data={data} disabled={false} errors={{}} onChange={setData} /><output>{JSON.stringify(data)}</output></>
}

describe('SchemaForm', () => {
  it('renders fields from schema and updates normalized values', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('标题'), { target: { value: '动态字段' } })
    fireEvent.click(screen.getByText('选项 A'))
    fireEvent.click(screen.getByText('是'))
    fireEvent.click(screen.getByText('3'))
    expect(screen.getByRole('status')).toHaveTextContent('"title":"动态字段"')
    expect(screen.getByRole('status')).toHaveTextContent('"kind":"A"')
    expect(screen.getByRole('status')).toHaveTextContent('"flag":true')
    expect(screen.getByRole('status')).toHaveTextContent('"score":3')
  })
})

