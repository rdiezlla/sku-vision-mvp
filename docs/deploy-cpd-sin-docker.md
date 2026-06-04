# Despliegue CPD sin Docker

Este flujo evita construir el indice en el servidor. El trabajo pesado se hace en un equipo con mas potencia y el servidor solo ejecuta la app.

## Idea general

1. En el equipo potente se genera el indice completo desde todas las fotos.
2. Se comprime la carpeta del indice.
3. En el servidor se clona el repositorio.
4. En el servidor se instalan Python y Node.js.
5. En el servidor se descomprime el indice ya generado.
6. La app se arranca en modo single-server: FastAPI sirve backend y frontend en la misma URL.

## En el equipo potente

Editar `.env.docker` para que apunte a la carpeta real de fotos:

```env
HOST_DATASET_ROOT=C:/ruta/a/FOTOS MATERIAL
HTTP_PORT=8000
ADMIN_KEY=cambia-esta-clave
```

Generar el indice:

```powershell
docker compose --env-file .env.docker --profile tools run --build --rm indexer
```

Comprimir el indice:

```powershell
Compress-Archive -Path runtime_data/data/* -DestinationPath sku-index-prebuild.zip -Force
```

El zip generado contiene los embeddings y el mapping. No contiene las fotos originales.

## En el servidor

Instalar requisitos:

- Python 3.11
- Node.js 20 LTS
- Git

Clonar el repositorio y entrar en la carpeta:

```powershell
git clone <URL_DEL_REPO>
cd sku-vision-mvp
```

Crear entorno Python e instalar dependencias:

```powershell
python scripts/setup_backend.py --upgrade-pip
```

Este script instala PyTorch en version CPU-only para evitar descargar paquetes CUDA innecesarios en servidores sin GPU.

Instalar dependencias del frontend y compilarlo:

```powershell
python scripts/setup_frontend.py
python scripts/build_static_frontend.py
```

Crear `backend/.env.local`:

```env
DATASET_ROOT=D:/sku-vision/Fotos
DATA_DIR=backend/data
STORAGE_ROOT=backend/storage
FEEDBACK_FILE=backend/data/feedback/feedback.jsonl
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
ALLOW_ORIGINS=*
ADMIN_KEY=cambia-esta-clave
```

Copiar las fotos originales al servidor en la ruta indicada en `DATASET_ROOT`.

Descomprimir el indice en `backend/data`. Si `backend/data` no existe, crearlo:

```powershell
New-Item -ItemType Directory -Force backend/data
Expand-Archive -Path sku-index-prebuild.zip -DestinationPath backend/data -Force
```

Arrancar la app:

```powershell
backend/.venv/Scripts/python scripts/run_backend_single.py --host 0.0.0.0 --port 8000
```

Abrir desde la red corporativa:

```text
http://IP_O_DNS_DEL_SERVIDOR:8000
```

## Cosas importantes

- El indice evita recalcular embeddings de todas las fotos.
- Las fotos originales siguen siendo necesarias para mostrar ejemplos y miniaturas.
- Si el servidor no tiene salida a Internet, hay que preparar tambien el modelo CLIP en modo offline.
- Si se actualizan muchas fotos de referencia, repetir el proceso: generar indice en el equipo potente, comprimirlo y reemplazar `backend/data` en el servidor.
