# sku-vision-mvp
Web app móvil para reconocimiento de SKUs (FastAPI + CLIP + React/Vite PWA).

## Qué problema resuelve este repo
- Reconocimiento de SKUs por foto (`/search`) y en directo (`/search_live`).
- Admin para alta/baja de imágenes SKU.
- Índice local persistente (`backend/data`) con dataset en carpeta local (`DATASET_ROOT`).

## Demo incluida (fotos reales)
Muestra mínima con fotos reales:
- `sample_data/Fotos/042132/042132.jpeg`
- `sample_data/Fotos/042128/042128.jpg`

---

## Requisitos
- Python 3.10+ (recomendado 3.11)
- Node 18+ y npm 9+ (solo para desarrollo frontend o para construir estáticos)
- Opcional HTTPS local: `mkcert` (preferido) u `openssl`
- Opcional despliegue corporativo: Docker Desktop

---

## Variables clave
Backend (`backend/.env.local`):
- `DATASET_ROOT` (carpeta Fotos SKU)
- `DATA_DIR` (índices)
- `STORAGE_ROOT` (uploads admin)
- `ALLOW_ORIGINS`
- `ADMIN_KEY`

Frontend (`frontend/.env.local`):
- `VITE_BACKEND_URL` (opcional; si vacío se calcula automática según host/protocolo)
- `VITE_ADMIN_KEY`

---

## Desarrollo normal (Mac/Windows, con Node)
1. Crear `.env.local` desde ejemplos.
2. Configurar `DATASET_ROOT`.
3. Instalar dependencias.
4. Construir índice.
5. Levantar app.

macOS/Linux:
```bash
cp backend/.env.example backend/.env.local
cp frontend/.env.example frontend/.env.local
python3 scripts/setup_backend.py
python3 scripts/setup_frontend.py
python3 scripts/build_index.py
python3 scripts/dev_up.py
```

Windows PowerShell:
```powershell
Copy-Item backend/.env.example backend/.env.local
Copy-Item frontend/.env.example frontend/.env.local
python scripts/setup_backend.py
python scripts/setup_frontend.py
python scripts/build_index.py
python scripts/dev_up.py
```

HTTPS dev:
```bash
python scripts/dev_up_https.py
```

---

## Opción A: Runtime sin Node en el PC de trabajo (Python-only)
Este modo sirve frontend compilado desde FastAPI en la misma URL.

### A.1 En un equipo con Node (build machine)
Compilar frontend estático y copiarlo a backend:
```bash
python3 scripts/build_static_frontend.py
```
Esto genera:
- `backend/static_dist/index.html`
- `backend/static_dist/assets/*`

Sube esos archivos al repo.

### A.2 En el PC de trabajo (sin Node)
1) Clonar repo.
2) Crear venv e instalar backend:
```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```
3) Configurar `backend/.env.local` (`DATASET_ROOT` apuntando a Fotos local).
4) Construir índice:
```bash
backend/.venv/Scripts/python scripts/build_index.py
```
5) Arrancar single-server:
```bash
backend/.venv/Scripts/python scripts/run_backend_single.py --host 0.0.0.0 --port 8000
```

Abrir:
- PC: `http://localhost:8000`
- LAN: `http://IP_DEL_PC:8000`

---

## Opción B: Docker (recomendada en entorno corporativo)
No necesita Node instalado en host. El build frontend se hace dentro de Docker.

### B.1 Preparación
1) Copiar plantilla:
```bash
cp .env.docker.example .env.docker
```
2) Editar `.env.docker`:
- `HOST_DATASET_ROOT` (ruta local del host al dataset Fotos)
  - En Windows usa formato con `/`: `C:/ruta/Fotos`

### B.2 Levantar HTTP
```bash
docker compose --env-file .env.docker up --build app
```

La primera vez puede tardar por build + indexado.

### B.3 Levantar HTTPS
```bash
docker compose --env-file .env.docker --profile https up --build app_https
```
Requiere certificados en `certs/dev-cert.pem` y `certs/dev-key.pem`.

### B.4 Reindex manual (tooling)
```bash
docker compose --env-file .env.docker --profile tools run --rm indexer
```

### B.5 Rutas de datos en Docker
- Dataset host (solo lectura): `HOST_DATASET_ROOT -> /datasets/Fotos`
- Índices persistentes: `./runtime_data/data -> /app/backend/data`
- Storage persistente: `./runtime_data/storage -> /app/backend/storage`

---

## Acceso desde otros dispositivos (misma Wi‑Fi)
- HTTP: `http://IP_DEL_PC:8000`
- HTTPS: `https://IP_DEL_PC:8443`

Si no abre desde otros terminales:
1. Arrancar backend en `0.0.0.0` (ya configurado en scripts/compose).
2. Publicar puerto Docker (`0.0.0.0:8000:8000` / `8443:8443`).
3. Firewall del equipo: permitir entrada TCP a 8000/8443 en red privada.
4. Verificar que todos los dispositivos están en la misma subred.

---

## Live camera en móvil
- iPhone/Safari necesita HTTPS para `getUserMedia` en red local.
- Instala/confía `certs/rootCA.pem` en el móvil para evitar bloqueo TLS.
- Si no hay HTTPS, usa flujo de foto subida (no stream directo).

---

## Scripts útiles
Python (cross-platform):
- `scripts/setup_backend.py`
- `scripts/setup_frontend.py`
- `scripts/build_index.py`
- `scripts/build_static_frontend.py`
- `scripts/dev_up.py`
- `scripts/dev_up_https.py`
- `scripts/run_backend_single.py`
- `scripts/doctor.py`

Wrappers:
- bash (`*.sh`)
- PowerShell (`*.ps1`)

---

## Troubleshooting rápido
Diagnóstico:
```bash
python scripts/doctor.py
python scripts/doctor.py --https
```

PowerShell policy (si bloquea scripts):
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
