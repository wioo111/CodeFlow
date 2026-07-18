import type { Project, ProjectSchema, ResultRow, Task } from '../types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败，请稍后重试' }))
    throw new Error(error.detail || '请求失败')
  }
  return response.json() as Promise<T>
}

export const api = {
  projects: () => request<Project[]>('/projects'),
  schema: (projectId: number) => request<ProjectSchema>(`/projects/${projectId}/schema`),
  tasks: (projectId: number) => request<Task[]>(`/tasks?project_id=${projectId}`),
  task: (taskId: number) => request<Task>(`/tasks/${taskId}`),
  nextTask: (projectId: number, afterId = 0) => request<Task | null>(`/tasks/next?project_id=${projectId}&after_id=${afterId}`),
  saveDraft: (taskId: number, data: Record<string, unknown>, duration: number) =>
    request<{ status: string; updated_at: string }>(`/annotations/${taskId}/draft`, {
      method: 'PUT', body: JSON.stringify({ annotation_data: data, duration_seconds: duration }),
    }),
  submit: (taskId: number, data: Record<string, unknown>, duration: number) =>
    request<{ status: string; submitted_at: string }>(`/annotations/${taskId}/submit`, {
      method: 'POST', body: JSON.stringify({ annotation_data: data, duration_seconds: duration }),
    }),
  results: (projectId: number, status = '') => request<ResultRow[]>(`/results?project_id=${projectId}${status ? `&status=${status}` : ''}`),
}

