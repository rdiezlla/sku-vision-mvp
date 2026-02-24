# sku-vision-mvp
Web app móvil para reconocimiento de SKUs por imagen (FastAPI + CLIP + React PWA).

## Estructura
```text
sku-vision-mvp/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── main.py
│   │   └── schemas.py
│   ├── index/
│   │   ├── __init__.py
│   │   ├── build.py
│   │   ├── evaluate.py
│   │   ├── clip_embedder.py
│   │   └── store.py
│   ├── data/
│   └── storage/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── LivePanel.jsx
│   │   ├── hooks/
│   │   │   └── useLiveRecognition.js
│   │   └── api.js
│   ├── public/
│   ├── package.json
│   └── .env.example
└── scripts/
    ├── setup_backend.sh
    ├── setup_https.sh
    ├── build_index.sh
    ├── run_backend.sh
    ├── run_backend_https.sh
    ├── setup_frontend.sh
    ├── run_frontend.sh
    ├── run_frontend_https.sh
    ├── dev_up.sh
    └── dev_up_https.sh
```

## Qué implementa
- Indexado offline con CLIP normalizado L2.
- Persistencia de:
  - `backend/data/sku_prototypes.npy`
  - `backend/data/image_embeddings.npy`
  - `backend/data/mapping.json`
  - `backend/data/sku_index.faiss` (si FAISS está disponible)
  - `backend/data/image_index.faiss` (si FAISS está disponible)
- Retrieval en 2 fases:
  1. Top-50 SKUs por prototipo.
  2. Re-ranking por imágenes de esos SKUs candidatos.
- Score por SKU: `max(sim)` (coseno/IP sobre embeddings normalizados).
- Mejoras de similitud fina:
  - Multi-crop (`ENABLE_MULTICROP`)
  - Tie-break por color (`ENABLE_COLOR_TIEBREAK`, umbral `COLOR_TIE_THRESHOLD`)
- Endpoint admin para alta incremental de SKU sin reconstrucción total.
- Admin permite eliminar imágenes subidas por error y reindexa asociaciones/embeddings al instante.
- Módulo `Live` con cámara en directo:
  - stream + inferencia continua
  - smoothing temporal + hysteresis para estabilizar top-1
  - auto-throttle por latencia y cancelación de requests en vuelo
  - overlay con top-1, top-5, estado, latencia y FPS

## API
- `POST /search` (alias `POST /api/search`)
  - Multipart: `file`, `k` (default `5`)
- `GET /sku/{sku}/examples?limit=3`
- `POST /search_live` (alias `POST /api/search_live`)
  - Multipart: `file`, `k` (default `5`), `enable_multicrop` (opcional)
  - Respuesta ligera: SKU + score (sin examples)
- `POST /feedback`
  - JSON: `{ "query_id": "...", "chosen_sku": "011110", "timestamp": "ISO8601" }`
- `POST /admin/items`
  - Multipart: `sku`, `admin_key`, `files[]`
- `GET /admin/sku_exists?sku=011110&admin_key=...`
  - Respuesta: `{ "sku": "011110", "exists": true|false }` para validación en tiempo real del formulario Admin
- En Admin: si el SKU ya existe se muestra warning y al guardar se pide confirmación; la carga múltiple acumula selecciones (sin duplicados) y permite quitar/limpiar antes de enviar.
- `GET /admin/sku_images?sku=011110&admin_key=...`
  - Lista las imágenes subidas en `storage` para ese SKU (usado por Admin para seleccionar borrado).
- `POST /admin/sku_images/delete`
  - JSON: `{ "sku": "...", "admin_key": "...", "filepaths": ["..."] }`
  - Elimina archivos del storage y actualiza mapping, embeddings, prototipos e índices sin reconstrucción completa.
- `POST /admin/reindex`
  - JSON: `{ "admin_key": "..." }`

## Instalación (Mac)
### 1) Backend
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/setup_backend.sh
```

Opcional FAISS (recomendado):
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp/backend
source .venv/bin/activate
pip install faiss-cpu
```

### 2) Frontend
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/setup_frontend.sh
```

## Indexar dataset
Comando exacto solicitado:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
source backend/.venv/bin/activate
python -m backend.index.build --data_dir "/Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/Fotos/" --out_dir backend/data
```

También disponible como script:
```bash
./scripts/build_index.sh
```

## Arrancar backend en red local
Comando exacto solicitado:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
source backend/.venv/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Con script:
```bash
./scripts/run_backend.sh
```

## Arrancar frontend
Comandos exactos solicitados:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Con script:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/run_frontend.sh
```

## Arranque en un solo comando
Si ya tienes dependencias instaladas, puedes levantar backend + frontend con:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/dev_up.sh
```

Notas:
- Si falta el índice, `dev_up.sh` lo construye automáticamente.
- Para parar todo, pulsa `Ctrl + C`.
- Logs backend: `/tmp/sku_backend.log`

Comando recomendado para recordar:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp && ./scripts/dev_up.sh
```

## HTTPS local para Live en iPhone
`getUserMedia` en iPhone necesita HTTPS para stream en directo.

1. Generar certificados locales:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/setup_https.sh
```

2. Levantar todo en HTTPS (backend + frontend):
s```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
./scripts/dev_up_https.sh
```

3. Abrir en iPhone:
- `https://<IP_DEL_MAC>:5173`

4. Confiar la CA en iPhone:
- Usa `certs/rootCA.pem` (AirDrop/email) e instálalo en el iPhone.
- Activa confianza en:
  `Ajustes > General > Información > Ajustes de confianza de certificados`.

## Abrir desde el móvil (misma WiFi)
1. Obtener IP local del Mac:
```bash
ipconfig getifaddr en0
```
2. Abrir en el móvil:
- `http://<IP_DEL_MAC>:5173`

El frontend llama al backend en `http://<IP_DEL_MAC>:8000` (o el valor de `VITE_BACKEND_URL`).

## Uso del modo Live
1. En la app abre pestaña **Live**.
2. Pulsa **Iniciar Live**.
   - En modo stream real no tienes que hacer foto manual: el SKU se actualiza automáticamente sobre el vídeo.
3. Ajusta:
   - Frecuencia (recomendado: `2 fps`)
   - `Auto-crop` (activado por defecto)
   - Botón **Configuración recomendada** para reset rápido.
4. Lee el overlay:
   - Top-1 (grande)
   - Estado (`estable` / `buscando...`)
   - Latencia y FPS real
5. Miniaturas: se cargan solo para el SKU top-1 cuando se estabiliza o cambia.
6. Pantalla encendida:
   - En este MVP no se fuerza Wake Lock; evita bloquear la pantalla durante Live.

### Configuración recomendada Live (móvil)
- Frecuencia: `2 fps`
- Auto-crop: `ON`
- Calidad JPEG: `70%`
- Lado máximo: `512 px`
- Modo: `preciso` para estabilidad / `rápido` si necesitas reacción más ágil

## Configuración
### Backend (`backend/.env`)
- `DATASET_ROOT`
- `DATA_DIR`
- `STORAGE_ROOT`
- `CLIP_MODEL_ID`
- `ENABLE_MULTICROP`
- `ENABLE_COLOR_TIEBREAK`
- `COLOR_TIE_THRESHOLD`
- `ADMIN_KEY`

### Frontend (`frontend/.env`)
- `BACKEND_URL=http://<IP_DEL_MAC>:8000` (o `VITE_BACKEND_URL`)
- `VITE_ADMIN_KEY=sku-admin-dev`
- (opcional) `VITE_BACKEND_URL=http://<IP_DEL_MAC>:8000`

## Evaluación rápida
Script para validar ranking con una muestra:
```bash
cd /Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/sku-vision-mvp
source backend/.venv/bin/activate
python -m backend.index.evaluate --data_dir "/Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/Fotos/" --out_dir backend/data --sample 50 --k 5
```

## Troubleshooting
- Permisos cámara en iOS:
  - En Safari, permite cámara para la URL del frontend.
  - iOS puede requerir interacción de usuario antes de abrir cámara.
  - En HTTP algunos navegadores limitan `getUserMedia`: usa el fallback de captura del sistema dentro de Live.
  - Si ves `getUserMedia no disponible` en iPhone con URL `http://<IP>:5173`, es esperado por política del navegador (contexto no seguro).
  - Solución rápida: usar **Fallback cámara del sistema** (semi-live).
  - Solución para stream real Live: abrir la app desde un origen HTTPS confiable.
  - Si al pulsar `Iniciar Live` se abre cámara nativa y te pide sacar foto, estás en fallback (no stream en directo).
- CORS:
  - Si falla, usa `ALLOW_ORIGINS=*` en `backend/.env` para entorno local.
- Firewall macOS:
  - En Ajustes > Red > Firewall, permite conexiones entrantes para Python/Node.
- Tamaño de imagen / rendimiento:
  - Reducir `BATCH_SIZE` si hay falta de memoria.
  - Primera indexación tarda más por descarga inicial de CLIP.
  - Con FAISS la búsqueda escala mejor que solo Numpy.
  - En Live, baja frecuencia a `1-2 fps` si hay latencia alta o consumo de batería.
