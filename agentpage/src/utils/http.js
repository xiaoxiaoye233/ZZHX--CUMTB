const baseURL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

export default async function request({ url, method = 'GET', params = {}, data, keepalive = false }) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') query.set(key, value)
  }
  const search = query.toString()
  const options = { method, credentials: 'include', keepalive }

  if (data instanceof FormData) {
    options.body = data
  } else if (data !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(data)
  }

  const response = await fetch(`${baseURL}${url}${search ? `?${search}` : ''}`, options)
  if (response.status === 204) return

  const isJSON = response.headers.get('content-type')?.includes('application/json')
  const result = isJSON ? await response.json() : await response.text()
  if (response.ok) {
    if (!isJSON) throw new Error('接口未返回 JSON，请检查 API 地址')
    return result
  }

  const message =
    result?.message ||
    result?.error?.message ||
    result?.detail?.error?.message ||
    (typeof result?.detail === 'string' ? result.detail : '') ||
    `请求失败（${response.status}）`
  const error = new Error(message)
  error.status = response.status
  error.code = result?.error?.code || result?.detail?.error?.code
  error.data = result
  throw error
}
