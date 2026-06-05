/**
 * @typedef {{ sku: string, score: number, examples?: string[] }} SearchResult
 * @typedef {{ query_id: string, results: SearchResult[], index_engine?: string }} SearchResponsePayload
 */

export function resolveBackendUrl() {
  const envValue = String(import.meta.env.VITE_BACKEND_URL ?? import.meta.env.BACKEND_URL ?? '').trim()
  if (!envValue) {
    if (typeof window === 'undefined') return 'http://localhost:8000'
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
    const host = window.location.hostname || 'localhost'
    const port = protocol === 'https:' ? '8443' : '8000'
    return `${protocol}//${host}:${port}`
  }
  if (envValue === '/') {
    return ''
  }
  return envValue.replace(/\/$/, '')
}

export function toAbsoluteBackendUrl(path, backendUrl = resolveBackendUrl()) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (!backendUrl || backendUrl === '/api') return path
  return `${backendUrl}${path.startsWith('/') ? path : `/${path}`}`
}

export async function parseApiError(response, fallbackMessage = 'Error de API') {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => ({}))
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
  }

  const text = await response.text().catch(() => '')
  if (text.trim()) {
    return text.slice(0, 220)
  }

  return `${fallbackMessage} (HTTP ${response.status})`
}

/**
 * Reutilizable para /search y /search_live.
 * @param {{backendUrl: string, blob: Blob, filename?: string, k?: number, endpoint?: string, enableMulticrop?: boolean, signal?: AbortSignal}} params
 * @returns {Promise<SearchResponsePayload>}
 */
export async function searchImage(params) {
  const { backendUrl, blob, filename = 'image.jpg', k = 5, endpoint = '/search', enableMulticrop, signal } = params

  const body = new FormData()
  body.append('file', blob, filename)
  body.append('k', String(k))
  if (typeof enableMulticrop === 'boolean') {
    body.append('enable_multicrop', String(enableMulticrop))
  }

  const response = await fetch(`${backendUrl}${endpoint}`, {
    method: 'POST',
    body,
    signal,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error en la búsqueda'))
  }

  return response.json()
}

export async function fetchSkuExamples({ backendUrl, sku, limit = 3 }) {
  const response = await fetch(`${backendUrl}/sku/${encodeURIComponent(sku)}/examples?limit=${limit}`)
  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error obteniendo ejemplos'))
  }
  return response.json()
}

export async function postFeedback({ backendUrl, queryId, chosenSku, timestamp = new Date().toISOString() }) {
  const response = await fetch(`${backendUrl}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query_id: queryId,
      chosen_sku: chosenSku,
      timestamp,
    }),
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'No se pudo enviar feedback'))
  }

  return response.json()
}

export async function addAdminItems({ backendUrl, sku, adminKey, files }) {
  const body = new FormData()
  body.append('sku', String(sku || '').trim())
  body.append('admin_key', String(adminKey || '').trim())
  ;(Array.isArray(files) ? files : []).forEach((file) => {
    body.append('files[]', file, file.name || 'correction.jpg')
  })

  const response = await fetch(`${backendUrl}/admin/items`, {
    method: 'POST',
    body,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error guardando SKU'))
  }

  return response.json()
}

export async function checkSkuExists({ backendUrl, sku, adminKey, signal }) {
  const params = new URLSearchParams({
    sku: String(sku || '').trim(),
    admin_key: String(adminKey || '').trim(),
  })

  const response = await fetch(`${backendUrl}/admin/sku_exists?${params.toString()}`, {
    method: 'GET',
    signal,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error comprobando SKU'))
  }

  return response.json()
}

export async function fetchAdminSkuImages({ backendUrl, sku, adminKey, signal }) {
  const params = new URLSearchParams({
    sku: String(sku || '').trim(),
    admin_key: String(adminKey || '').trim(),
  })

  const response = await fetch(`${backendUrl}/admin/sku_images?${params.toString()}`, {
    method: 'GET',
    signal,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error cargando imágenes del SKU'))
  }

  return response.json()
}

export async function deleteAdminSkuImages({ backendUrl, sku, adminKey, filepaths }) {
  const response = await fetch(`${backendUrl}/admin/sku_images/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sku: String(sku || '').trim(),
      admin_key: String(adminKey || '').trim(),
      filepaths: Array.isArray(filepaths) ? filepaths : [],
    }),
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Error eliminando imágenes del SKU'))
  }

  return response.json()
}
