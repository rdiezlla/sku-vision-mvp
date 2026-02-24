import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchSkuExamples, searchImage } from '../api'

const HISTORY_WINDOW = 8
const STABLE_COUNT = 6
const HYSTERESIS_MARGIN = 0.03
const HYSTERESIS_FRAMES = 3

function getLiveSupportStatus() {
  const isBrowser = typeof window !== 'undefined'
  if (!isBrowser) {
    return { supported: false, hint: 'Entorno sin navegador para usar Live.' }
  }

  const secure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  if (!secure) {
    return {
      supported: false,
      hint: 'Live por streaming en iPhone requiere HTTPS. En HTTP usa "Fallback cámara del sistema".',
    }
  }

  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
    return {
      supported: false,
      hint: 'getUserMedia no está disponible en este navegador/dispositivo.',
    }
  }

  return { supported: true, hint: '' }
}

function getNow() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

function toBlobAsync(canvas, quality) {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality)
  })
}

function getConstraintFromCamera(cameraSelection) {
  if (cameraSelection.startsWith('device:')) {
    return {
      deviceId: { exact: cameraSelection.slice('device:'.length) },
      width: { ideal: 1280 },
      height: { ideal: 720 },
    }
  }

  return {
    facingMode: { ideal: cameraSelection || 'environment' },
    width: { ideal: 1280 },
    height: { ideal: 720 },
  }
}

export function useLiveRecognition({ backendUrl, enabled = true }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const loopTimerRef = useRef(null)
  const abortControllerRef = useRef(null)

  const historyRef = useRef([])
  const stableSkuRef = useRef('')
  const switchCandidateRef = useRef({ sku: '', count: 0 })
  const examplesSkuRef = useRef('')
  const fpsTimestampsRef = useRef([])
  const runningRef = useRef(false)

  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState('')
  const [cameraSelection, setCameraSelection] = useState('environment')
  const [cameraDevices, setCameraDevices] = useState([])
  const [targetFps, setTargetFps] = useState(2)
  const [effectiveFps, setEffectiveFps] = useState(2)
  const [jpegQuality, setJpegQuality] = useState(0.7)
  const [maxSide, setMaxSide] = useState(512)
  const [autoCrop, setAutoCrop] = useState(true)

  const [latencyMs, setLatencyMs] = useState(0)
  const [fpsReal, setFpsReal] = useState(0)
  const [topResults, setTopResults] = useState([])
  const [topOne, setTopOne] = useState(null)
  const [stabilityState, setStabilityState] = useState('buscando...')
  const [examples, setExamples] = useState([])
  const [supportsLiveStream, setSupportsLiveStream] = useState(true)
  const [supportHint, setSupportHint] = useState('')

  const stopLive = useCallback(() => {
    runningRef.current = false
    setIsRunning(false)

    if (loopTimerRef.current) {
      clearInterval(loopTimerRef.current)
      loopTimerRef.current = null
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    historyRef.current = []
    switchCandidateRef.current = { sku: '', count: 0 }
    fpsTimestampsRef.current = []
    stableSkuRef.current = ''
    examplesSkuRef.current = ''

    setFpsReal(0)
    setLatencyMs(0)
    setStabilityState('buscando...')
    setTopResults([])
    setTopOne(null)
    setExamples([])
  }, [])

  const refreshCameras = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      const cameras = devices
        .filter((device) => device.kind === 'videoinput')
        .map((device, idx) => ({
          id: device.deviceId,
          label: device.label || `Camara ${idx + 1}`,
        }))
      setCameraDevices(cameras)
    } catch {
      // Algunos navegadores bloquean enumerateDevices sin permiso.
    }
  }, [])

  const captureFrameBlob = useCallback(async () => {
    const video = videoRef.current
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      return null
    }

    const canvas = canvasRef.current || document.createElement('canvas')
    canvasRef.current = canvas

    const srcW = video.videoWidth
    const srcH = video.videoHeight

    let sx = 0
    let sy = 0
    let sWidth = srcW
    let sHeight = srcH

    if (autoCrop) {
      const cropRatio = 0.8
      sWidth = Math.max(32, Math.floor(srcW * cropRatio))
      sHeight = Math.max(32, Math.floor(srcH * cropRatio))
      sx = Math.max(0, Math.floor((srcW - sWidth) / 2))
      sy = Math.max(0, Math.floor((srcH - sHeight) / 2))
    }

    const longest = Math.max(sWidth, sHeight)
    const scale = longest > maxSide ? maxSide / longest : 1
    const outW = Math.max(32, Math.round(sWidth * scale))
    const outH = Math.max(32, Math.round(sHeight * scale))

    canvas.width = outW
    canvas.height = outH

    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return null

    ctx.drawImage(video, sx, sy, sWidth, sHeight, 0, 0, outW, outH)
    return toBlobAsync(canvas, jpegQuality)
  }, [autoCrop, jpegQuality, maxSide])

  const updateAutoThrottle = useCallback(
    (latency) => {
      const recommendation = latency > 900 ? 1 : latency > 600 ? 2 : latency > 360 ? 3 : 4
      const nextFps = Math.min(targetFps, recommendation)
      setEffectiveFps((prev) => (prev === nextFps ? prev : nextFps))
    },
    [targetFps],
  )

  const updateRealFps = useCallback(() => {
    const now = getNow()
    fpsTimestampsRef.current.push(now)
    fpsTimestampsRef.current = fpsTimestampsRef.current.filter((ts) => now - ts <= 4000)

    if (fpsTimestampsRef.current.length <= 1) {
      setFpsReal(0)
      return
    }

    const first = fpsTimestampsRef.current[0]
    const last = fpsTimestampsRef.current[fpsTimestampsRef.current.length - 1]
    const seconds = Math.max((last - first) / 1000, 0.001)
    const fps = (fpsTimestampsRef.current.length - 1) / seconds
    setFpsReal(Number(fps.toFixed(1)))
  }, [])

  const requestExamplesForTop = useCallback(
    async (sku) => {
      if (!sku || sku === examplesSkuRef.current) return
      examplesSkuRef.current = sku

      try {
        const payload = await fetchSkuExamples({ backendUrl, sku, limit: 3 })
        if (examplesSkuRef.current === sku) {
          setExamples(payload.examples || [])
        }
      } catch {
        // No bloquea el stream live.
      }
    },
    [backendUrl],
  )

  const applySmoothing = useCallback(
    (results) => {
      if (!results || results.length === 0) {
        setStabilityState('buscando...')
        return
      }

      const topK = results.slice(0, 5)
      historyRef.current.push(topK)
      if (historyRef.current.length > HISTORY_WINDOW) {
        historyRef.current.shift()
      }

      const frames = historyRef.current
      const scoreMap = {}
      const top1Count = {}
      let weightTotal = 0

      for (let age = 0; age < frames.length; age += 1) {
        const frame = frames[frames.length - 1 - age]
        const weight = Math.pow(0.85, age)
        weightTotal += weight

        if (frame[0]?.sku) {
          top1Count[frame[0].sku] = (top1Count[frame[0].sku] || 0) + 1
        }

        frame.forEach((row) => {
          scoreMap[row.sku] = (scoreMap[row.sku] || 0) + row.score * weight
        })
      }

      const sorted = Object.entries(scoreMap)
        .map(([sku, score]) => ({ sku, score: score / Math.max(weightTotal, 1e-6) }))
        .sort((a, b) => b.score - a.score)

      if (sorted.length === 0) return

      const candidateSku = sorted[0].sku
      const candidateScore = sorted[0].score

      if (!stableSkuRef.current) {
        stableSkuRef.current = candidateSku
      } else if (candidateSku !== stableSkuRef.current) {
        const currentScore = sorted.find((row) => row.sku === stableSkuRef.current)?.score || 0

        if (candidateScore >= currentScore + HYSTERESIS_MARGIN) {
          stableSkuRef.current = candidateSku
          switchCandidateRef.current = { sku: '', count: 0 }
        } else {
          if (switchCandidateRef.current.sku === candidateSku) {
            switchCandidateRef.current.count += 1
          } else {
            switchCandidateRef.current = { sku: candidateSku, count: 1 }
          }

          if (switchCandidateRef.current.count >= HYSTERESIS_FRAMES) {
            stableSkuRef.current = candidateSku
            switchCandidateRef.current = { sku: '', count: 0 }
          }
        }
      } else {
        switchCandidateRef.current = { sku: '', count: 0 }
      }

      const stableSku = stableSkuRef.current
      const stableScore = sorted.find((row) => row.sku === stableSku)?.score || 0
      const stableThreshold = Math.min(STABLE_COUNT, Math.max(1, Math.ceil(frames.length * 0.75)))
      const isStable = (top1Count[stableSku] || 0) >= stableThreshold

      setTopResults(sorted.slice(0, 5))
      setTopOne({ sku: stableSku, score: stableScore })
      setStabilityState(isStable ? 'estable' : 'buscando...')

      if (isStable) {
        requestExamplesForTop(stableSku).catch(() => null)
      }
    },
    [requestExamplesForTop],
  )

  const inferOnce = useCallback(async () => {
    if (!runningRef.current || !enabled) return

    const blob = await captureFrameBlob()
    if (!blob) return

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const controller = new AbortController()
    abortControllerRef.current = controller

    const startedAt = getNow()

    try {
      const payload = await searchImage({
        backendUrl,
        blob,
        filename: 'live.jpg',
        k: 5,
        endpoint: '/search_live',
        enableMulticrop: autoCrop,
        signal: controller.signal,
      })

      const latency = getNow() - startedAt
      setLatencyMs(Math.round(latency))
      updateAutoThrottle(latency)
      updateRealFps()
      setError('')

      applySmoothing(payload.results || [])
    } catch (err) {
      if (err?.name === 'AbortError') return
      setError(err?.message || 'Error en reconocimiento Live')
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
      }
    }
  }, [enabled, captureFrameBlob, backendUrl, autoCrop, updateAutoThrottle, updateRealFps, applySmoothing])

  const startLive = useCallback(async () => {
    if (!enabled) return false
    setError('')
    const support = getLiveSupportStatus()
    setSupportsLiveStream(support.supported)
    setSupportHint(support.hint)
    if (!support.supported) {
      setError(support.hint || 'Live no disponible en este navegador')
      return false
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: getConstraintFromCamera(cameraSelection),
        audio: false,
      })

      streamRef.current = stream
      const video = videoRef.current
      if (!video) throw new Error('No se encontró el elemento de vídeo para Live')

      video.srcObject = stream
      await video.play()

      runningRef.current = true
      setIsRunning(true)
      setEffectiveFps(targetFps)
      await refreshCameras()
      return true
    } catch (err) {
      const name = err?.name || ''
      if (name === 'NotAllowedError') {
        setError('Permiso de cámara denegado. Habilítalo en ajustes del navegador.')
      } else if (name === 'NotFoundError') {
        setError('No se encontró una cámara disponible.')
      } else {
        setError(err?.message || 'No se pudo iniciar la cámara Live')
      }
      stopLive()
      return false
    }
  }, [enabled, cameraSelection, targetFps, refreshCameras, stopLive])

  const restartLive = useCallback(async () => {
    if (!isRunning) return
    stopLive()
    await startLive()
  }, [isRunning, startLive, stopLive])

  const runSingleFallback = useCallback(
    async (file) => {
      if (!file) return
      try {
        const startedAt = getNow()
        const payload = await searchImage({
          backendUrl,
          blob: file,
          filename: file.name || 'live-fallback.jpg',
          k: 5,
          endpoint: '/search_live',
          enableMulticrop: autoCrop,
        })

        setLatencyMs(Math.round(getNow() - startedAt))
        setError('')
        applySmoothing(payload.results || [])
      } catch (err) {
        setError(err?.message || 'No se pudo ejecutar fallback de cámara')
      }
    },
    [backendUrl, autoCrop, applySmoothing],
  )

  useEffect(() => {
    refreshCameras()
  }, [refreshCameras])

  useEffect(() => {
    const support = getLiveSupportStatus()
    setSupportsLiveStream(support.supported)
    setSupportHint(support.hint)
  }, [])

  useEffect(() => {
    if (!isRunning || !enabled) return undefined

    const intervalMs = Math.max(250, Math.round(1000 / Math.max(1, effectiveFps)))
    loopTimerRef.current = setInterval(() => {
      inferOnce()
    }, intervalMs)

    return () => {
      if (loopTimerRef.current) {
        clearInterval(loopTimerRef.current)
        loopTimerRef.current = null
      }
    }
  }, [isRunning, enabled, effectiveFps, inferOnce])

  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden && runningRef.current) {
        stopLive()
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [stopLive])

  useEffect(() => {
    if (!isRunning) return
    setEffectiveFps(targetFps)
  }, [targetFps, isRunning])

  useEffect(() => stopLive, [stopLive])

  const applyRecommendedConfig = useCallback(() => {
    setTargetFps(2)
    setEffectiveFps(2)
    setAutoCrop(true)
    setJpegQuality(0.7)
    setMaxSide(512)
  }, [])

  return {
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
  }
}
