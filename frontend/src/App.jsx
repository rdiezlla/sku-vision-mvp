import { useEffect, useMemo, useRef, useState } from 'react'
import LivePanel from './components/LivePanel'
import {
  checkSkuExists,
  deleteAdminSkuImages,
  fetchAdminSkuImages,
  parseApiError,
  postFeedback,
  resolveBackendUrl,
  searchImage,
  toAbsoluteBackendUrl,
} from './api'

const BACKEND_URL = resolveBackendUrl()
const DEFAULT_ADMIN_KEY = import.meta.env.VITE_ADMIN_KEY ?? ''

function absoluteUrl(path) {
  return toAbsoluteBackendUrl(path, BACKEND_URL)
}

function App() {
  const galleryInputRef = useRef(null)
  const cameraInputRef = useRef(null)
  const adminSkuCheckTimerRef = useRef(null)
  const adminSkuCheckAbortRef = useRef(null)
  const adminImagesAbortRef = useRef(null)

  const [screen, setScreen] = useState('capture')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const [selectedBlob, setSelectedBlob] = useState(null)
  const [selectedName, setSelectedName] = useState('capture.jpg')
  const [previewUrl, setPreviewUrl] = useState('')

  const [queryId, setQueryId] = useState('')
  const [results, setResults] = useState([])

  const [adminSku, setAdminSku] = useState('')
  const [adminKey, setAdminKey] = useState(DEFAULT_ADMIN_KEY)
  const [adminFiles, setAdminFiles] = useState([])
  const [adminSkuExists, setAdminSkuExists] = useState(null)
  const [isCheckingAdminSku, setIsCheckingAdminSku] = useState(false)
  const [adminSkuCheckError, setAdminSkuCheckError] = useState('')
  const [showAdminConfirmModal, setShowAdminConfirmModal] = useState(false)
  const [adminSkuImages, setAdminSkuImages] = useState([])
  const [adminSelectedDeletePaths, setAdminSelectedDeletePaths] = useState([])
  const [isLoadingAdminImages, setIsLoadingAdminImages] = useState(false)
  const [adminImagesError, setAdminImagesError] = useState('')
  const [showAdminDeleteModal, setShowAdminDeleteModal] = useState(false)

  const hasPreview = useMemo(() => Boolean(selectedBlob && previewUrl), [selectedBlob, previewUrl])
  const isRecognitionScreen = screen === 'capture' || screen === 'results'

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      if (adminSkuCheckTimerRef.current) {
        clearTimeout(adminSkuCheckTimerRef.current)
        adminSkuCheckTimerRef.current = null
      }
      if (adminSkuCheckAbortRef.current) {
        adminSkuCheckAbortRef.current.abort()
        adminSkuCheckAbortRef.current = null
      }
      if (adminImagesAbortRef.current) {
        adminImagesAbortRef.current.abort()
        adminImagesAbortRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    setError('')
    setStatus('')
  }, [screen])

  function clearStatus() {
    setError('')
    setStatus('')
  }

  function setPreviewFromBlob(blob) {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    const nextUrl = URL.createObjectURL(blob)
    setPreviewUrl(nextUrl)
  }

  function setSelectedFile(file) {
    if (!file) return
    setSelectedBlob(file)
    setSelectedName(file.name || 'upload.jpg')
    setPreviewFromBlob(file)
  }

  function buildFileKey(file) {
    return `${file.name}__${file.size}__${file.lastModified}`
  }

  function mergeUniqueFiles(previousFiles, incomingFiles) {
    const map = new Map(previousFiles.map((file) => [buildFileKey(file), file]))
    incomingFiles.forEach((file) => {
      map.set(buildFileKey(file), file)
    })
    return Array.from(map.values())
  }

  function openGalleryPicker() {
    clearStatus()
    if (galleryInputRef.current) {
      galleryInputRef.current.click()
    }
  }

  function openCameraPicker() {
    clearStatus()
    cameraInputRef.current?.click()
  }

  function onGalleryFileSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    clearStatus()
    setSelectedFile(file)
  }

  function onAdminFilesSelected(event) {
    const incoming = Array.from(event.target.files || [])
    event.target.value = ''
    if (incoming.length === 0) return

    setAdminFiles((previous) => mergeUniqueFiles(previous, incoming))
  }

  function removeAdminFile(fileToRemove) {
    const targetKey = buildFileKey(fileToRemove)
    setAdminFiles((previous) => previous.filter((file) => buildFileKey(file) !== targetKey))
  }

  function clearAdminFiles() {
    setAdminFiles([])
  }

  function toggleAdminDeletePath(filepath) {
    setAdminSelectedDeletePaths((previous) => {
      if (previous.includes(filepath)) {
        return previous.filter((item) => item !== filepath)
      }
      return [...previous, filepath]
    })
  }

  function clearAdminDeleteSelection() {
    setAdminSelectedDeletePaths([])
  }

  async function loadAdminSkuImages() {
    const sku = adminSku.trim()
    const key = adminKey.trim()
    if (!sku || !key || adminSkuExists !== true) {
      setAdminSkuImages([])
      setAdminSelectedDeletePaths([])
      setAdminImagesError('')
      return
    }

    if (adminImagesAbortRef.current) {
      adminImagesAbortRef.current.abort()
      adminImagesAbortRef.current = null
    }

    const controller = new AbortController()
    adminImagesAbortRef.current = controller
    setIsLoadingAdminImages(true)
    setAdminImagesError('')

    try {
      const payload = await fetchAdminSkuImages({
        backendUrl: BACKEND_URL,
        sku,
        adminKey: key,
        signal: controller.signal,
      })
      const images = Array.isArray(payload.images) ? payload.images : []
      setAdminSkuImages(images)
      setAdminSelectedDeletePaths((previous) => {
        const available = new Set(images.map((image) => image.filepath))
        return previous.filter((path) => available.has(path))
      })
    } catch (err) {
      if (err?.name === 'AbortError') return
      setAdminSkuImages([])
      setAdminSelectedDeletePaths([])
      setAdminImagesError(err?.message || 'No se pudieron cargar las imágenes del SKU')
    } finally {
      if (adminImagesAbortRef.current === controller) {
        adminImagesAbortRef.current = null
      }
      setIsLoadingAdminImages(false)
    }
  }

  async function runSearch(blob, filename) {
    if (!blob) {
      setError('Selecciona o captura una imagen primero.')
      return
    }

    clearStatus()
    setIsLoading(true)

    try {
      const payload = await searchImage({
        backendUrl: BACKEND_URL,
        blob,
        filename,
        k: 5,
        endpoint: '/search',
      })
      setQueryId(payload.query_id)
      setResults(payload.results || [])
      setScreen('results')
    } catch (err) {
      setError(err.message || 'No se pudo buscar')
    } finally {
      setIsLoading(false)
    }
  }

  async function onCameraShotSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    clearStatus()
    setSelectedFile(file)
    await runSearch(file, file.name || 'camera.jpg')
  }

  async function searchSku() {
    await runSearch(selectedBlob, selectedName)
  }

  async function sendFeedback(sku) {
    if (!queryId) return

    try {
      await postFeedback({
        backendUrl: BACKEND_URL,
        queryId,
        chosenSku: sku,
      })
      setStatus(`Feedback enviado para SKU ${sku}`)
    } catch (err) {
      setError(err.message || 'No se pudo enviar feedback')
    }
  }

  async function saveAdminItems() {
    if (!adminSku || adminFiles.length === 0) {
      setError('Completa SKU y sube al menos una imagen.')
      return
    }

    if (!adminKey) {
      setError('Falta la clave admin.')
      return
    }

    if (adminSkuExists === true) {
      setShowAdminConfirmModal(true)
      return
    }

    await submitAdminItems()
  }

  async function submitAdminItems() {
    clearStatus()
    setIsLoading(true)

    try {
      const body = new FormData()
      body.append('sku', adminSku.trim())
      body.append('admin_key', adminKey)
      adminFiles.forEach((file) => body.append('files[]', file, file.name))

      const response = await fetch(`${BACKEND_URL}/admin/items`, {
        method: 'POST',
        body,
      })

      if (!response.ok) {
        throw new Error(await parseApiError(response, 'Error guardando SKU'))
      }

      const payload = await response.json()
      setStatus(`SKU ${payload.sku} guardado con ${payload.added_images} imágenes.`)
      setAdminSku('')
      setAdminFiles([])
      setAdminSkuExists(null)
      setAdminSkuCheckError('')
      setShowAdminConfirmModal(false)
      setShowAdminDeleteModal(false)
      setAdminSkuImages([])
      setAdminSelectedDeletePaths([])
      setAdminImagesError('')
    } catch (err) {
      setError(err.message || 'No se pudo guardar el SKU')
    } finally {
      setIsLoading(false)
    }
  }

  async function deleteSelectedAdminImages() {
    const sku = adminSku.trim()
    if (!sku || adminSelectedDeletePaths.length === 0) {
      setError('Selecciona al menos una imagen para eliminar.')
      return
    }
    if (!adminKey.trim()) {
      setError('Falta la clave admin.')
      return
    }

    clearStatus()
    setIsLoading(true)

    try {
      const payload = await deleteAdminSkuImages({
        backendUrl: BACKEND_URL,
        sku,
        adminKey,
        filepaths: adminSelectedDeletePaths,
      })

      setShowAdminDeleteModal(false)
      setAdminSelectedDeletePaths([])
      setStatus(
        `Eliminadas ${payload.removed_images} imagen(es) del SKU ${payload.sku}. Restantes en SKU: ${payload.remaining_sku_images}.`,
      )
      await loadAdminSkuImages()
    } catch (err) {
      setError(err?.message || 'No se pudieron eliminar las imágenes')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (screen !== 'admin') return undefined

    const sku = adminSku.trim()
    const key = adminKey.trim()

    if (adminSkuCheckTimerRef.current) {
      clearTimeout(adminSkuCheckTimerRef.current)
      adminSkuCheckTimerRef.current = null
    }
    if (adminSkuCheckAbortRef.current) {
      adminSkuCheckAbortRef.current.abort()
      adminSkuCheckAbortRef.current = null
    }

    if (!sku || !key) {
      setIsCheckingAdminSku(false)
      setAdminSkuExists(null)
      setAdminSkuCheckError('')
      return undefined
    }

    setIsCheckingAdminSku(true)
    setAdminSkuCheckError('')

    adminSkuCheckTimerRef.current = setTimeout(async () => {
      const controller = new AbortController()
      adminSkuCheckAbortRef.current = controller

      try {
        const payload = await checkSkuExists({
          backendUrl: BACKEND_URL,
          sku,
          adminKey: key,
          signal: controller.signal,
        })
        setAdminSkuExists(Boolean(payload.exists))
      } catch (err) {
        if (err?.name === 'AbortError') return
        setAdminSkuExists(null)
        setAdminSkuCheckError(err?.message || 'No se pudo comprobar el SKU')
      } finally {
        if (adminSkuCheckAbortRef.current === controller) {
          adminSkuCheckAbortRef.current = null
        }
        setIsCheckingAdminSku(false)
      }
    }, 400)

    return () => {
      if (adminSkuCheckTimerRef.current) {
        clearTimeout(adminSkuCheckTimerRef.current)
        adminSkuCheckTimerRef.current = null
      }
      if (adminSkuCheckAbortRef.current) {
        adminSkuCheckAbortRef.current.abort()
        adminSkuCheckAbortRef.current = null
      }
    }
  }, [screen, adminSku, adminKey])

  useEffect(() => {
    if (screen !== 'admin') return undefined

    if (adminSkuExists !== true) {
      setAdminSkuImages([])
      setAdminSelectedDeletePaths([])
      setAdminImagesError('')
      setShowAdminDeleteModal(false)
      if (adminImagesAbortRef.current) {
        adminImagesAbortRef.current.abort()
        adminImagesAbortRef.current = null
      }
      setIsLoadingAdminImages(false)
      return undefined
    }

    loadAdminSkuImages()

    return () => {
      if (adminImagesAbortRef.current) {
        adminImagesAbortRef.current.abort()
        adminImagesAbortRef.current = null
      }
    }
  }, [screen, adminSkuExists, adminSku, adminKey])

  function renderCaptureScreen() {
    return (
      <section className="panel">
        <h2>Pantalla 1 · Captura</h2>
        <div className="button-row">
          <button type="button" onClick={openCameraPicker} disabled={isLoading}>
            Hacer foto
          </button>
          <button type="button" className="upload-label" onClick={openGalleryPicker} disabled={isLoading}>
            Subir foto
          </button>
          <input ref={galleryInputRef} type="file" accept="image/*" onChange={onGalleryFileSelected} hidden />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={onCameraShotSelected}
            hidden
          />
        </div>

        {hasPreview && (
          <div className="preview-wrap">
            <p>Vista previa</p>
            <img src={previewUrl} alt="Vista previa de consulta" />
          </div>
        )}

        <div className="button-row">
          <button type="button" onClick={searchSku} disabled={isLoading || !selectedBlob}>
            Buscar
          </button>
        </div>
      </section>
    )
  }

  function renderResultsScreen() {
    return (
      <section className="panel">
        <div className="header-row">
          <h2>Resultados Top-5</h2>
          <button type="button" className="secondary" onClick={() => setScreen('capture')}>
            Nueva búsqueda
          </button>
        </div>

        {results.length === 0 && <p className="empty">Sin resultados.</p>}

        {results.map((result, index) => (
          <article className="result-card" key={`${result.sku}-${index}`}>
            <h3>
              #{index + 1} · SKU {result.sku}
            </h3>
            <p>Score: {(result.score * 100).toFixed(2)}%</p>
            <div className="thumb-grid">
              {(result.examples || []).map((url, idx) => (
                <a key={`${result.sku}-${idx}`} href={absoluteUrl(url)} target="_blank" rel="noreferrer">
                  <img src={absoluteUrl(url)} alt={`Ejemplo ${idx + 1} SKU ${result.sku}`} loading="lazy" />
                </a>
              ))}
            </div>
            <button type="button" className="secondary" onClick={() => sendFeedback(result.sku)}>
              Correcto
            </button>
          </article>
        ))}
      </section>
    )
  }

  function renderAdminScreen() {
    const showSkuExistsWarning = adminSku.trim().length > 0 && adminSkuExists === true && !adminSkuCheckError
    const showSkuIsNew = adminSku.trim().length > 0 && adminSkuExists === false && !adminSkuCheckError

    return (
      <section className="panel">
        <h2>Admin SKU (MVP)</h2>
        <p>Protegido por clave simple para altas rápidas de SKU.</p>
        <label>
          Clave admin
          <input type="password" value={adminKey} onChange={(e) => setAdminKey(e.target.value)} />
        </label>
        <label>
          SKU
          <input type="text" value={adminSku} onChange={(e) => setAdminSku(e.target.value)} placeholder="Ej: 011110" />
        </label>
        {isCheckingAdminSku ? <p className="admin-hint muted">Comprobando SKU...</p> : null}
        {showSkuExistsWarning ? <p className="admin-hint warning">Este SKU ya existe</p> : null}
        {showSkuIsNew ? <p className="admin-hint ok">SKU nuevo</p> : null}
        {adminSkuCheckError ? <p className="admin-hint muted">{adminSkuCheckError}</p> : null}

        <label>
          Imágenes
          <input type="file" accept="image/*" multiple onChange={onAdminFilesSelected} />
        </label>

        {adminFiles.length > 0 ? (
          <div className="admin-files-wrap">
            <div className="admin-files-head">
              <p>{adminFiles.length} archivo(s) seleccionado(s)</p>
              <button type="button" className="secondary" onClick={clearAdminFiles}>
                Limpiar
              </button>
            </div>
            <div className="admin-files-list">
              {adminFiles.map((file) => (
                <div className="admin-file-item" key={buildFileKey(file)}>
                  <span>{file.name}</span>
                  <button type="button" className="secondary" onClick={() => removeAdminFile(file)}>
                    Quitar
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {adminSkuExists === true ? (
          <div className="admin-existing-wrap">
            <div className="admin-files-head">
              <p>Imágenes subidas del SKU (storage)</p>
              <button type="button" className="secondary" onClick={loadAdminSkuImages} disabled={isLoadingAdminImages}>
                Recargar
              </button>
            </div>

            {isLoadingAdminImages ? <p className="admin-hint muted">Cargando imágenes...</p> : null}
            {adminImagesError ? <p className="admin-hint muted">{adminImagesError}</p> : null}

            {!isLoadingAdminImages && !adminImagesError && adminSkuImages.length === 0 ? (
              <p className="admin-hint muted">No hay imágenes subidas para este SKU.</p>
            ) : null}

            {adminSkuImages.length > 0 ? (
              <div className="admin-existing-grid">
                {adminSkuImages.map((image) => {
                  const selected = adminSelectedDeletePaths.includes(image.filepath)
                  return (
                    <label className={`admin-existing-item ${selected ? 'selected' : ''}`} key={image.filepath}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleAdminDeletePath(image.filepath)}
                      />
                      <img src={absoluteUrl(image.url)} alt={image.filename} loading="lazy" />
                      <span>{image.filename}</span>
                    </label>
                  )
                })}
              </div>
            ) : null}

            <div className="button-row">
              <button
                type="button"
                className="secondary"
                onClick={clearAdminDeleteSelection}
                disabled={adminSelectedDeletePaths.length === 0}
              >
                Limpiar selección
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => setShowAdminDeleteModal(true)}
                disabled={adminSelectedDeletePaths.length === 0 || isLoading}
              >
                Eliminar seleccionadas
              </button>
            </div>
          </div>
        ) : null}

        <button type="button" onClick={saveAdminItems} disabled={isLoading}>
          Guardar
        </button>
      </section>
    )
  }

  return (
    <main className="app">
      <header className="hero">
        <h1>SKU Vision MVP</h1>
        <p>Reconocimiento de SKUs desde móvil con CLIP + FastAPI.</p>
      </header>

      <nav className="tabs">
        <button type="button" className={isRecognitionScreen ? 'active' : ''} onClick={() => setScreen('capture')}>
          Reconocimiento
        </button>
        <button type="button" className={screen === 'live' ? 'active' : ''} onClick={() => setScreen('live')}>
          Live
        </button>
        <button type="button" className={screen === 'admin' ? 'active' : ''} onClick={() => setScreen('admin')}>
          Admin
        </button>
      </nav>

      {screen === 'admin' ? renderAdminScreen() : null}
      {screen === 'live' ? <LivePanel backendUrl={BACKEND_URL} absoluteUrl={absoluteUrl} /> : null}
      {screen === 'capture' ? renderCaptureScreen() : null}
      {screen === 'results' ? renderResultsScreen() : null}

      {isLoading && <p className="status">Procesando...</p>}
      {status && <p className="status ok">{status}</p>}
      {error && <p className="status error">{error}</p>}

      {showAdminConfirmModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="admin-confirm-title">
          <div className="modal-card">
            <h3 id="admin-confirm-title">Confirmar subida</h3>
            <p>
              Este SKU ya existe. ¿Quieres añadir estas {adminFiles.length} imágenes al SKU {adminSku.trim()}?
            </p>
            <div className="button-row">
              <button type="button" className="secondary" onClick={() => setShowAdminConfirmModal(false)}>
                Cancelar
              </button>
              <button type="button" onClick={submitAdminItems} disabled={isLoading}>
                Sí, añadir
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showAdminDeleteModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="admin-delete-title">
          <div className="modal-card">
            <h3 id="admin-delete-title">Eliminar imágenes</h3>
            <p>
              Vas a eliminar {adminSelectedDeletePaths.length} imagen(es) del SKU {adminSku.trim()}. Esta acción
              actualizará embeddings e índices. ¿Quieres continuar?
            </p>
            <div className="button-row">
              <button type="button" className="secondary" onClick={() => setShowAdminDeleteModal(false)}>
                Cancelar
              </button>
              <button type="button" className="danger" onClick={deleteSelectedAdminImages} disabled={isLoading}>
                Sí, eliminar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

export default App
