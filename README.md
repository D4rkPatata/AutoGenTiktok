# GenVideosAuto (MVP local)

Aplicacion web local para generar automaticamente videos verticales tipo TikTok a partir de clips cortos.

## 1) Arquitectura final

- Frontend: SPA simple en `frontend/static` (HTML + CSS + JS moderno).
- Backend: FastAPI en `app/`.
- Motor de edicion: FFmpeg invocado desde Python con heuristicas.
- Caption IA: Gemini (free tier) opcional via `GEMINI_API_KEY`; fallback local cuando no hay clave.
- Almacenamiento: filesystem local (`data/jobs` y `data/music_presets`).
- Base de datos: no se usa (MVP sin login ni cuentas).

### Flujo de alto nivel

1. Usuario sube hasta 10 clips o usa una carpeta de Google Drive, y opcionalmente musica.
2. Usuario configura versiones (1-10) y estilo.
3. Frontend envia `multipart/form-data` a `POST /api/generate`.
4. Backend valida archivos y guarda temporalmente.
5. Motor genera variantes (orden, fragmentos, ritmo, transiciones).
6. Backend genera caption por cada variante.
7. API devuelve lista de resultados con `download_url`.
8. Frontend muestra captions y boton de descarga de cada video.

## 2) Estructura de carpetas

```text
.
|-- app/
|   |-- api/
|   |   |-- __init__.py
|   |   `-- routes.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- captioner.py
|   |   |-- editor.py
|   |   |-- pipeline.py
|   |   |-- probe.py
|   |   `-- storage.py
|   |-- utils/
|   |   `-- ffmpeg.py
|   |-- __init__.py
|   |-- config.py
|   |-- main.py
|   `-- schemas.py
|-- data/
|   |-- jobs/                 # temporal, auto generado
|   `-- music_presets/        # coloca musica predefinida aqui
|-- frontend/
|   `-- static/
|       |-- app.js
|       |-- index.html
|       `-- styles.css
|-- .env.example
|-- .gitignore
|-- requirements.txt
`-- README.md
```

## 3) Endpoints del backend

- `GET /api/health`
  - Health check.

- `GET /api/music-presets`
  - Lista de archivos de `data/music_presets` (mp3/wav/m4a/aac).

- `POST /api/generate`
  - `multipart/form-data`
  - Campos:
    - `clips`: lista de videos (1-10, mp4/mov) cuando no se usa Drive
    - `drive_folder_id`: ID de carpeta de Drive (opcional, alternativo a `clips`)
    - `versions`: entero (1-10)
    - `style`: `clean_fast | aggressive | smooth`
    - `centered_text`: texto opcional centrado durante todo el video principal
    - `music_preset`: nombre de archivo preset (opcional)
    - `music_file`: archivo de audio (opcional)
  - Retorna:
    - `job_id`
    - `results[]` con `filename`, `download_url`, `caption`

- `GET /api/download/{job_id}/{filename}`
  - Descarga MP4 final.

- `POST /api/download-zip/{job_id}`
  - Body JSON: `{ "filenames": ["video_01.mp4", ...] }`
  - Si `filenames` esta vacio, descarga todos los MP4 del job.

- `GET /api/tiktok/status`
  - Estado de conexion contra variables TikTok.

- `POST /api/tiktok/drafts/{job_id}`
  - Body JSON: `{ "filenames": ["video_01.mp4", ...] }`
  - Envia seleccion a endpoint de borradores de TikTok.

## 4) Estrategias del motor de generacion

### 4.1 Variantes

Cada variante cambia al menos en:
- orden de clips
- puntos de inicio de fragmentos
- duracion de cortes
- ritmo segun estilo

Se usa una semilla distinta por variante para evitar resultados casi identicos.

### 4.2 Fragmentacion automatica

- Se elige un fragmento inicial fuerte entre 1 y 2 segundos (hook).
- Luego se agregan cortes hasta duracion objetivo del estilo.
- Se evita repetir el mismo clip consecutivamente cuando hay alternativas.
- Se evita usar extremos del clip cuando sea posible (zonas centrales prioritarias).

### 4.3 Composicion vertical 9:16

En cada segmento:
- `scale` con `force_original_aspect_ratio=increase`
- `crop` a `1080x1920`
- `fps=30`
- `setsar=1`

Con esto se evitan bordes negros y se mantiene formato TikTok.

### 4.4 Transiciones

- Se usan transiciones simples `xfade=fade` entre segmentos.
- Audio entre segmentos con `acrossfade`.
- Duracion de transicion depende del estilo.

### 4.5 Mezcla de audio

Si hay musica seleccionada:
- musica en loop hasta la duracion final
- `fade in` y `fade out`
- `sidechaincompress` para bajar musica cuando hay voz/audio original
- mezcla final con limitador

Si no hay musica, se conserva audio del montaje base.

## 5) Estrategia de captions

- Opcion IA gratuita: Gemini con free tier (requiere `GEMINI_API_KEY`).
- Prompt corto orientado a TikTok (emojis + hashtags).
- Fallback local si no hay API key o falla la llamada.


## 6) Requisitos previos

1. Python 3.11+.
2. FFmpeg y FFprobe instalados y disponibles en PATH.
3. (Opcional) API key de Gemini free tier.

## 7) Como correr local

1. Crear entorno virtual:

```bash
python -m venv .venv
```

2. Activar entorno en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Configurar variables:

```bash
copy .env.example .env
```

5. Editar `.env` (solo local, no se sube a git):

- `FFMPEG_BIN` y `FFPROBE_BIN`:
  - si FFmpeg esta en PATH, deja `ffmpeg` y `ffprobe`
  - si no esta en PATH, usa la ruta absoluta a los ejecutables
- `GEMINI_API_KEY` (opcional): pega tu API key si quieres captions con IA
- `ENDING_CLIP_PATH`: por defecto `data/logo/ending.mp4`

6. (Opcional) agregar musica preset en:

- `data/music_presets/mi_base.mp3`

7. Iniciar servidor:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

8. Abrir navegador:

- `http://127.0.0.1:8000`

## 8) API key (Gemini)

1. Crea una key en Google AI Studio (free tier).
2. Abre tu archivo `.env` local.
3. Configura:

```env
GEMINI_API_KEY=tu_api_key_aqui
GEMINI_MODEL=gemini-1.5-flash
```

4. No subas tu `.env` al repo. Este proyecto ignora `.env` por `.gitignore`.

## 9) Variables de configuracion principales

Revisar `.env.example`:
- limites de cantidad y tamano
- binarios ffmpeg/ffprobe
- resolucion/fps objetivo
- limpieza de temporales
- claves de captions IA
- credenciales opcionales de Google Drive/TikTok

## 10) Notas operativas

- Los outputs quedan en `data/jobs/<job_id>/outputs` para descarga.
- Se limpian jobs antiguos en startup segun `CLEANUP_AFTER_HOURS`.
- El directorio temporal `work` se elimina al terminar cada generacion.
