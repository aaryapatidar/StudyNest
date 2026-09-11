const RAW_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000/api'

// Normalize the base URL so the final request is always `<origin>/api/<path>`
// whether VITE_API_URL is `http://localhost:8000` or `http://localhost:8000/api`.
// Without this, a bare origin would produce `/auth/...` (missing prefix -> 404)
// and appending `/api/...` paths would produce `/api/api/...` (double prefix -> 404).
const API_URL = (() => {
  const trimmed = RAW_BASE_URL.trim().replace(/\/+$/, '')
  return trimmed.endsWith('/api') ? trimmed : `${trimmed}/api`
})()

export type User = { id: string; full_name: string; email: string; college: string; course: string; semester: number }
export type Subject = { id: string; name: string; code: string; description: string; semester: number; notes_count: number; tasks_count: number; progress: number }
export type Note = { id: string; title: string; content: string; subject_id: string; tags: string[]; favorite: boolean; archived: boolean; updated_at: string }
export type Task = { id: string; title: string; description: string; subject_id: string | null; due_date: string | null; priority: 'Low' | 'Medium' | 'High'; task_type: string; status: 'Pending' | 'In Progress' | 'Completed' }
export type Resource = { id: string; title: string; url: string; subject_id: string | null; description: string; resource_type: string }
export type Revision = { id: string; topic: string; subject_id: string | null; status: 'Needs Revision' | 'Reviewed' | 'Mastered'; next_review_at: string | null }

export class ApiError extends Error {}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('studynest_token')
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body.detail || 'Something went wrong. Please try again.')
  }
  return response.status === 204 ? undefined as T : response.json()
}
export async function signIn(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ username: email, password }) })
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new ApiError(body.detail || 'Unable to sign in.') }
  const token = (await response.json()).access_token as string
  localStorage.setItem('studynest_token', token)
}
