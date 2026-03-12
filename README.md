# sku-vision-mvp
Web app movil para reconocimiento de SKUs (FastAPI + CLIP + React/Vite PWA), enfocada en macOS.

## 1) Requisitos
- macOS
- Python 3.10+ (recomendado 3.11)
- Node 18+
- npm 9+
- Opcional para HTTPS: `mkcert` (si no, usa fallback con `openssl`)

## 2) Setup rapido
Desde la raiz del repo:

```bash
python3 scripts/setup_backend.py
python3 scripts/setup_frontend.py
```

Copia plantillas de entorno (si no existen):

```bash
cp backend/.env.example backend/.env.local
cp frontend/.env.example frontend/.env.local
```

## 3) Indexado dataset (DATASET_ROOT)
En `backend/.env.local` configura `DATASET_ROOT` apuntando a tu carpeta `Fotos` (SKU por carpeta):

```env
DATASET_ROOT=/Users/TU_USUARIO/ruta/a/Fotos
```

Para probar rapido al clonar (sin dataset real), usa la muestra incluida de 2 SKUs:

```env
DATASET_ROOT=./sample_data/Fotos
```

Construye el indice:

```bash
python3 scripts/build_index.py
```

Se generan/actualizan archivos en `backend/data/`.

## 4) Arranque HTTP (un comando)

```bash
./run_http.sh
```

Este comando prepara dependencias faltantes y levanta:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

## 5) Arranque HTTPS (un comando)

```bash
./run_https.sh
```

Este comando:
1. Comprueba dependencias
2. Genera certificados en `certs/` si faltan
3. Levanta frontend y backend en HTTPS

URLs:
- Frontend: `https://localhost:5173`
- Backend: `https://localhost:8443`

## 6) Acceso desde movil (misma Wi-Fi)
Saca la IP local del Mac:

```bash
ipconfig getifaddr en0
```

Si no devuelve IP (por interfaz distinta), prueba:

```bash
ipconfig getifaddr en1
```

Accede desde movil:
- HTTP: `http://IP_DEL_MAC:5173`
- HTTPS: `https://IP_DEL_MAC:5173`

En HTTPS movil, instala/confia la CA local (`certs/rootCA.pem`) en el dispositivo para que Live funcione sin bloqueos.

## 7) Troubleshooting (macOS)
### Diagnostico rapido

```bash
python3 scripts/doctor.py
python3 scripts/doctor.py --https
```

### Errores comunes
- Camara Live no disponible en iPhone:
  - Usa HTTPS (`./run_https.sh`).
  - Abre la URL HTTPS (no HTTP).
  - Confia `certs/rootCA.pem` en iOS.
- Error CORS:
  - Arranca con `./run_http.sh` o `./run_https.sh` (ajustan `ALLOW_ORIGINS` automaticamente para localhost e IP local).
- Puertos ocupados:
  - Cierra procesos previos en `5173`, `8000` o `8443`.
  - Revisa logs en `.run_logs/`.
- Firewall macOS bloquea movil:
  - Permite conexiones entrantes para Python y Node en red privada.

## Variables de entorno
### Backend (`backend/.env.local`)
- `DATASET_ROOT`: ruta al dataset `Fotos`
- `DATA_DIR`: por defecto `backend/data`
- `STORAGE_ROOT`: por defecto `backend/storage`
- `ALLOW_ORIGINS`: CORS
- `ADMIN_KEY`: clave del modulo Admin

### Frontend (`frontend/.env.local`)
- `VITE_BACKEND_URL`: opcional. Si no se define, la app usa automaticamente:
  - `http://<host>:8000` en HTTP
  - `https://<host>:8443` en HTTPS
- `VITE_ADMIN_KEY`: clave admin usada por la UI

## Notas de datos
- No subas a Git el dataset real `Fotos` ni imagenes sensibles.
- Para probar con tu dataset, basta con configurar `DATASET_ROOT` y ejecutar `python3 scripts/build_index.py`.
