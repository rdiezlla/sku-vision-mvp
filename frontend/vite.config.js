import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = (env.VITE_BACKEND_URL || env.BACKEND_URL || '').trim()
  const sslKeyFile = (env.DEV_SSL_KEY_FILE || '').trim()
  const sslCertFile = (env.DEV_SSL_CERT_FILE || '').trim()
  const enableDevHttps = (env.DEV_HTTPS || '').trim().toLowerCase() === 'true'

  const define = {}
  if (backendUrl.length > 0) {
    define['import.meta.env.VITE_BACKEND_URL'] = JSON.stringify(backendUrl)
  }

  let httpsConfig
  if (enableDevHttps && sslKeyFile && sslCertFile && fs.existsSync(sslKeyFile) && fs.existsSync(sslCertFile)) {
    httpsConfig = {
      key: fs.readFileSync(sslKeyFile),
      cert: fs.readFileSync(sslCertFile),
    }
  }

  return {
    plugins: [react()],
    define,
    server: {
      https: httpsConfig,
    },
  }
})
