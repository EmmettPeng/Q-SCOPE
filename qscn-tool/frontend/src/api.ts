import { errorMessage } from './copy/en'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json() as { detail?: string | { code?: string; params?: Record<string, unknown> } }
      message = typeof payload.detail === 'string'
        ? errorMessage(undefined)
        : errorMessage(payload.detail?.code, payload.detail?.params)
    } catch { message = errorMessage(undefined) }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(url: string) => request<T>(url),
  post: <T>(url: string, body?: unknown) => request<T>(url, {
    method: 'POST',
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  }),
  patch: <T>(url: string, body: unknown) => request<T>(url, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  delete: (url: string) => request<void>(url, { method: 'DELETE' }),
}
