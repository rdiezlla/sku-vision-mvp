# sku-vision-mvp
Web app móvil para reconocimiento de SKUs (FastAPI + CLIP + React/Vite PWA).

## Requisitos
- Python 3.10+ (recomendado 3.11)
- Node 18+
- npm 9+
- Opcional HTTPS local: `mkcert` (preferido) u `openssl`

## Demo incluida (fotos reales)
El repo incluye una muestra mínima con fotos reales de 2 SKUs:
- `042132`
- `042128`

Ruta:
- `sample_data/Fotos/042132/*`
- `sample_data/Fotos/042128/*`

## Setup rápido (universal: macOS + Windows)
1. Clona y entra al repo.
2. Crea tus `.env.local`:

macOS/Linux:
```bash
cp backend/.env.example backend/.env.local
cp frontend/.env.example frontend/.env.local
```

Windows PowerShell:
```powershell
Copy-Item backend/.env.example backend/.env.local
Copy-Item frontend/.env.example frontend/.env.local
```

3. En `backend/.env.local`, para probar rápido deja:
```env
DATASET_ROOT=./sample_data/Fotos
```

4. Instala dependencias e indexa:

macOS/Linux:
```bash
python3 scripts/setup_backend.py
python3 scripts/setup_frontend.py
python3 scripts/build_index.py
```

Windows PowerShell:
```powershell
python scripts/setup_backend.py
python scripts/setup_frontend.py
python scripts/build_index.py
```

## Arranque HTTP
Universal (recomendado):
```bash
python scripts/dev_up.py
```

macOS atajo:
```bash
./run_http.sh
```

Windows PowerShell atajo:
```powershell
.\scripts\dev_up.ps1
```

URLs:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

## Arranque HTTPS (Live recomendado en móvil)
Universal:
```bash
python scripts/dev_up_https.py
```

macOS atajo:
```bash
./run_https.sh
```

Windows PowerShell atajo:
```powershell
.\scripts\setup_https.ps1
.\scripts\dev_up_https.ps1
```

URLs:
- Frontend: `https://localhost:5173`
- Backend: `https://localhost:8443`

## Acceso desde móvil (misma Wi‑Fi)
Abre en el móvil:
- HTTP: `http://IP_DEL_PC:5173`
- HTTPS: `https://IP_DEL_PC:5173`

IP local:
- macOS: `ipconfig getifaddr en0` (o `en1`)
- Windows: `ipconfig`

Para evitar bloqueos de cámara en Live con HTTPS, instala/confía `certs/rootCA.pem` en el móvil.

## Scripts disponibles
- Python (cross-platform): `setup_backend.py`, `setup_frontend.py`, `build_index.py`, `dev_up.py`, `setup_https.py`, `dev_up_https.py`, `doctor.py`
- macOS bash wrappers: `*.sh`
- Windows PowerShell wrappers: `*.ps1`

## Troubleshooting
- Diagnóstico:
  - `python scripts/doctor.py`
  - `python scripts/doctor.py --https`
- Si un puerto está ocupado (`5173`, `8000`, `8443`), cierra procesos previos.
- Si Live no abre cámara en iPhone, usa HTTPS y certificado confiado.
- Si PowerShell bloquea scripts:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Variables importantes
Backend (`backend/.env.local`):
- `DATASET_ROOT`
- `DATA_DIR`
- `STORAGE_ROOT`
- `ALLOW_ORIGINS`
- `ADMIN_KEY`

Frontend (`frontend/.env.local`):
- `VITE_BACKEND_URL` (opcional; si vacío se calcula automático)
- `VITE_ADMIN_KEY`
