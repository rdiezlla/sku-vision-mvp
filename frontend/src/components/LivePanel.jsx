import { useRef } from 'react'
import { useLiveRecognition } from '../hooks/useLiveRecognition'

export default function LivePanel({ backendUrl, absoluteUrl }) {
  const fallbackInputRef = useRef(null)

  const {
    videoRef,
    isRunning,
    error,
    supportsLiveStream,
    supportHint,
    topOne,
    topResults,
    examples,
    stabilityState,
    latencyMs,
    fpsReal,
    targetFps,
    effectiveFps,
    autoCrop,
    jpegQuality,
    maxSide,
    cameraSelection,
    cameraDevices,
    setTargetFps,
    setAutoCrop,
    setJpegQuality,
    setMaxSide,
    setCameraSelection,
    applyRecommendedConfig,
    startLive,
    stopLive,
    restartLive,
    runSingleFallback,
  } = useLiveRecognition({ backendUrl, enabled: true })

  async function onCameraChange(event) {
    const value = event.target.value
    setCameraSelection(value)
    if (isRunning) {
      await restartLive()
    }
  }

  function onModeQuick(mode) {
    if (mode === 'rapido') {
      setTargetFps(4)
      setJpegQuality(0.6)
      setMaxSide(512)
    } else {
      setTargetFps(2)
      setJpegQuality(0.8)
      setMaxSide(640)
    }
  }

  async function handleStartStop() {
    if (isRunning) {
      stopLive()
      return
    }

    await startLive()
  }

  function openFallbackCapture() {
    if (fallbackInputRef.current) {
      fallbackInputRef.current.click()
    }
  }

  function onFallbackFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) {
      runSingleFallback(file)
    }
  }

  return (
    <section className="panel live-panel">
      <div className="header-row">
        <h2>Live</h2>
        <button type="button" className={isRunning ? 'secondary' : ''} onClick={handleStartStop}>
          {isRunning ? 'Detener Live' : 'Iniciar Live'}
        </button>
      </div>

      <div className="live-controls">
        <div className="mode-row">
          <button type="button" className="secondary" onClick={applyRecommendedConfig}>
            Configuración recomendada
          </button>
        </div>

        <label>
          Cámara
          <select value={cameraSelection} onChange={onCameraChange}>
            <option value="environment">Trasera (environment)</option>
            <option value="user">Frontal (user)</option>
            {cameraDevices.map((camera) => (
              <option key={camera.id} value={`device:${camera.id}`}>
                {camera.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Frecuencia
          <select value={targetFps} onChange={(e) => setTargetFps(Number(e.target.value))}>
            <option value={1}>1 fps</option>
            <option value={2}>2 fps</option>
            <option value={3}>3 fps</option>
            <option value={4}>4 fps</option>
          </select>
        </label>

        <div className="mode-row">
          <button type="button" className="secondary" onClick={() => onModeQuick('preciso')}>
            Modo preciso
          </button>
          <button type="button" className="secondary" onClick={() => onModeQuick('rapido')}>
            Modo rápido
          </button>
        </div>

        <label className="toggle-row">
          <input type="checkbox" checked={autoCrop} onChange={(e) => setAutoCrop(e.target.checked)} />
          Auto-crop
        </label>

        <label>
          Calidad JPEG
          <input
            type="range"
            min="0.4"
            max="0.9"
            step="0.05"
            value={jpegQuality}
            onChange={(e) => setJpegQuality(Number(e.target.value))}
          />
          <small>{Math.round(jpegQuality * 100)}%</small>
        </label>

        <label>
          Lado máximo
          <select value={maxSide} onChange={(e) => setMaxSide(Number(e.target.value))}>
            <option value={512}>512 px</option>
            <option value={640}>640 px</option>
          </select>
        </label>
      </div>

      <div className="live-video-wrap">
        <video ref={videoRef} autoPlay muted playsInline />
        <div className="live-overlay">
          <p className="live-label">Top-1</p>
          <h3>{topOne?.sku || '---'}</h3>
          <p>Score: {topOne ? `${(topOne.score * 100).toFixed(1)}%` : '--'}</p>
          <p className={stabilityState === 'estable' ? 'live-stable' : 'live-unstable'}>
            Estado: {stabilityState}
          </p>
          <p>
            Latencia: {latencyMs} ms · FPS real: {fpsReal} · FPS objetivo: {targetFps} · FPS efectivo: {effectiveFps}
          </p>
        </div>
      </div>

      {examples.length > 0 && (
        <div>
          <p className="live-section-title">Miniaturas SKU top-1</p>
          <div className="thumb-grid">
            {examples.map((url, idx) => (
              <img key={`${url}-${idx}`} src={absoluteUrl(url)} alt={`Ejemplo top-1 ${idx + 1}`} loading="lazy" />
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="live-section-title">Top-5 (suavizado)</p>
        {topResults.length === 0 ? (
          <p className="empty">Buscando resultados...</p>
        ) : (
          <div className="live-top-list">
            {topResults.map((row, idx) => (
              <div key={`${row.sku}-${idx}`} className="live-top-item">
                <span>
                  #{idx + 1} {row.sku}
                </span>
                <span>{(row.score * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="live-fallback">
        <button type="button" className="secondary" onClick={openFallbackCapture}>
          Fallback cámara del sistema
        </button>
        <input ref={fallbackInputRef} type="file" accept="image/*" capture="environment" hidden onChange={onFallbackFile} />
      </div>

      {!supportsLiveStream && supportHint ? <p className="status warn">{supportHint}</p> : null}
      {error && <p className="status error">{error}</p>}
    </section>
  )
}
