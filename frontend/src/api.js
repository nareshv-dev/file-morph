function cookie(name) {
  return document.cookie.split('; ').find((item) => item.startsWith(`${name}=`))?.split('=').slice(1).join('=') || ''
}

let refreshPromise
async function refreshSession() {
  if (!cookie('filemorph_csrf')) return false
  if (!refreshPromise) {
    refreshPromise = fetch('/api/auth/refresh', { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': decodeURIComponent(cookie('filemorph_csrf')) } }).then((response) => response.ok).finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

export async function api(path, options = {}) {
  const { _retried, ...fetchOptions } = options
  const headers = new Headers(options.headers || {})
  const method = (options.method || 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRF-Token', decodeURIComponent(cookie('filemorph_csrf')))
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...fetchOptions, headers, credentials: 'include' })
  if (response.status === 401 && !_retried && !['/api/auth/login', '/api/auth/signup', '/api/auth/refresh'].includes(path)) {
    if (await refreshSession()) return api(path, { ...options, _retried: true })
  }
  if (response.status === 204) return null
  const type = response.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await response.json() : await response.blob()
  if (!response.ok) {
    const message = typeof data?.error === 'object' ? data.error.message : data?.detail || data?.error
    throw new Error(message || 'The request could not be completed.')
  }
  return data
}

export function navigate(path) {
  window.history.pushState(null, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function formatBytes(bytes) {
  if (bytes == null) return 'Not available'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
