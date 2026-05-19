# NomiSalud — Backend API

API REST construida con **FastAPI**, **PostgreSQL** (async con SQLAlchemy) y **Docker**.

---

## Requisitos

- [Docker](https://www.docker.com/) y Docker Compose
- Python 3.12+ (solo para desarrollo local sin Docker)

---

## Levantar el proyecto con Docker

```bash
# 1. Copiar variables de entorno y ajustar valores (incl. GEMINI_API_KEY si quieres extracción IA real)
cp .env.example .env

# 2. Construir y levantar los contenedores
docker compose up --build

# 3. La API estará disponible en:
#    http://localhost:8000
#    Docs Swagger: http://localhost:8000/docs
#    Docs ReDoc:   http://localhost:8000/redoc
```

---

## Endpoints disponibles

| Método | Ruta                           | Auth | Descripción |
|--------|--------------------------------|------|-------------|
| GET    | `/api/v1/health/`              | No   | Estado básico de la API |
| GET    | `/api/v1/health/db`            | No   | Verifica conexión a PostgreSQL |
| POST   | `/api/v1/auth/login`           | No   | Autenticación (retorna JWT) |
| GET    | `/api/v1/incapacidades`        | Sí   | Listado paginado con filtros; incluye nombre y email del colaborador y campos de entidad desde extracción IA |
| GET    | `/api/v1/incapacidades/mias`   | Sí   | Mis trámites (solo `colaborador`): filtro estricto por JWT; cada ítem incluye `estado` y `updated_at` |
| GET    | `/api/v1/incapacidades/{id}`   | Sí   | Detalle del trámite: `extraccion_ia`, lista `inconsistencias` (hallazgos IA) y `archivo_url` |
| GET    | `/api/v1/incapacidades/{id}/archivo` | Sí | Descarga del documento adjunto (mismo JWT que el detalle; ruta validada bajo `UPLOAD_STORAGE_DIR`) |
| PUT    | `/api/v1/incapacidades/{id}/verificar` | Sí | Verificación humana RRHH/admin: `confirmar` o `rechazar` (actualiza extracción, estado e historial) |
| PATCH  | `/api/v1/incapacidades/{id}/estado` | Sí | Cambio de estado con máquina de estados + `historial_estados` (solo RRHH/admin) |
| PUT    | `/api/v1/incapacidades/{id}/documentacion-faltante` | Sí | Registra lista de documentos faltantes y pasa a `doc_incompleta` (RRHH/admin) |
| POST   | `/api/v1/incapacidades/upload` | Sí   | Carga PDF/JPG/PNG, crea trámite y encola extracción IA (Gemini 2.5 Flash) |
| GET    | `/api/v1/demo/me`              | Sí   | [DEMO] Payload del JWT decodificado |
| GET    | `/api/v1/demo/colaborador`     | Sí   | [DEMO] Acceso por cualquier rol |
| GET    | `/api/v1/demo/rrhh`            | Sí   | [DEMO] Acceso RRHH/admin |
| GET    | `/api/v1/demo/admin`           | Sí   | [DEMO] Acceso solo admin |

La lista canónica de rutas, esquemas y códigos HTTP está en **Swagger** (`/docs`) y **ReDoc** (`/redoc`).

### Respuesta `POST /api/v1/incapacidades/upload`

Cuerpo JSON (201 Created):

```json
{
  "radicado": "IN0123456789ABCDEF0",
  "estado": "procesando_ia"
}
```

- **`radicado`**: identificador único del trámite (máx. 20 caracteres).
- **`estado`**: al cerrar la petición el trámite queda en **`procesando_ia`**. La API **no espera** a Gemini: la extracción corre en **segundo plano** (`BackgroundTasks`).
- Tras un extracción **correcta** sin hallazgos estructurados, el estado pasa a **`en_verificacion`** y se crea la fila en **`extraccion_ia`** (`datos_extraidos`, `validaciones`, `raw_response`, `modelo`, etc.).
- Si Gemini reporta **inconsistencias** en el array `inconsistencias` del JSON (SCRUM-169), el estado queda en **`inconsistencia_detectada`**, se persisten filas en la tabla **`inconsistencias`** (`tipo`, `descripcion`) y también existe **`extraccion_ia`** con los datos extraídos.
- Si la extracción **falla** (archivo, API, JSON inválido…), el estado suele quedar en **`doc_incompleta`** con detalle en `documentacion_faltante`.

Roles permitidos en upload: `colaborador`, `auxiliar_rrhh`, `coordinador_rrhh`, `admin`. Un colaborador solo puede cargar para sí mismo salvo que RRHH/admin indiquen `colaborador_id` en el formulario.

### Respuesta `GET /api/v1/incapacidades`

Parámetros de consulta (todos opcionales; si omites filtros, se listan todos los trámites permitidos por rol):

#### `page`

- Entero **≥ 1**. Por defecto **`1`**.
- La API rechaza valores menores que 1 con error de validación.

#### `estado`

- Filtra por el estado persistido del trámite.
- Debe coincidir **exactamente** (tras normalizar espacios y minúsculas) con **uno** de estos valores:

`recibida` · `procesando_ia` · `en_verificacion` · `inconsistencia_detectada` · `doc_incompleta` · `transcrita` · `cobrada` · `rechazada` · `pagada`

- Cualquier otro valor produce **422** con mensaje de estado inválido.

#### `tipo`

Comportamiento según el texto enviado (se recorta espacio en blanco y se compara en minúsculas):

1. **`pdf`**, **`jpg`** o **`png`**  
   Filtra por el tipo de **archivo adjunto** (`incapacidades.archivo_tipo`). Solo estos tres valores activan este modo.

2. **Cualquier otro texto no vacío**  
   Filtra por **igualdad exacta** con el valor almacenado en el JSON `datos_extraidos.incapacidad.tipo` (el contenido lo define la extracción IA; no hay lista cerrada en la API). Solo aplica a trámites que tengan fila en **`extraccion_ia`** (la consulta hace `JOIN` con esa tabla).

#### `entidad`

- Texto libre: se busca como **subcadena** insensible a mayúsculas y minúsculas dentro de `datos_extraidos.entidad.nombre`.
- Solo afecta a trámites con fila en **`extraccion_ia`** (misma condición de `JOIN` que cuando usas el modo (2) de `tipo`).
- Puedes combinarlo con `tipo`: si usas `tipo=pdf` y `entidad=…`, ambos filtros se aplican a la vez (`AND`).

Cuerpo JSON (200 OK):

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "radicado": "IN0123456789ABCDEF0",
      "estado": "transcrita",
      "colaborador_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "colaborador_nombre": "Ana María Gómez",
      "colaborador_email": "ana@nomisalud.com",
      "archivo_tipo": "pdf",
      "fecha_recepcion": "2025-03-01T12:00:00Z",
      "entidad_nombre": "EPS Sura",
      "entidad_tipo": "EPS",
      "entidad_nit": "800123456-7",
      "entidad_ciudad": "Bogotá",
      "incapacidad_tipo_extraido": "enfermedad_general"
    }
  ],
  "total": 45,
  "pages": 3
}
```

- **`colaborador_nombre`**: `users.nombre_completo` del titular; puede ser `null` si el perfil no tiene nombre cargado (el front puede mostrar `colaborador_email` como respaldo).
- **`colaborador_email`**: `users.email` del titular.
- **`entidad_*`**, **`incapacidad_tipo_extraido`**: leídos de `extraccion_ia.datos_extraidos` cuando existe extracción; si aún no hay fila IA o el documento no trae el dato, suelen ser `null` (columna entidad en UI: usar `entidad_nombre` y campos relacionados).

- **`total`**: cantidad de registros que cumplen los filtros (sin depender de la página).
- **`pages`**: número de páginas según `INCAPACIDADES_PAGE_SIZE` (por defecto **20**; ver `.env.example`).
- Mismos roles que el upload. Un **colaborador** solo obtiene sus trámites; **RRHH** y **admin** ven el listado completo.

### `GET /api/v1/incapacidades/mias` (mis trámites)

- **Rol:** solo `colaborador`.
- Filtra **siempre** por el `user_id` del JWT (`colaborador_id` del titular).
- Parámetro **`page`** (≥ 1, por defecto 1); paginación con `INCAPACIDADES_PAGE_SIZE`.
- Cada ítem incluye **`estado`** (actual) y **`updated_at`** (última modificación del registro), más `id` y `radicado`.
- Orden: `updated_at` descendente (más recientes primero).

### `GET /api/v1/incapacidades/{id}` (detalle)

- **Roles:** `colaborador`, `auxiliar_rrhh`, `coordinador_rrhh`, `admin` (el colaborador solo puede consultar trámites donde él es el titular `colaborador_id`).
- **404** si el `id` no existe.
- **403** si un colaborador intenta ver el trámite de otra persona.

La respuesta incluye los campos del trámite (radicado, estado, colaborador, archivo, fechas, `documentacion_faltante`, …), nombre y email del colaborador desde `users`, el bloque anidado **`extraccion_ia`** con todos los campos persistidos en la tabla `extraccion_ia` (o `null` si aún no hay extracción), el array **`inconsistencias`** (registros de la tabla homónima: `id`, `tipo`, `descripcion`, `created_at`; vacío si no hay hallazgos persistidos), y **`archivo_url`**: URL absoluta hacia `GET /api/v1/incapacidades/{id}/archivo` cuando hay `archivo_path` guardado; si no, `null`.

En **`extraccion_ia.datos_extraidos`** la API fusiona el JSON del prompt de IA (`paciente`, `incapacidad`, `diagnostico` anidado, `entidad`, …) con campos pensados para el **dashboard**: objeto **`colaborador`** (`nombre_completo`, `documento` desde `paciente`) y en **`incapacidad`** strings **`dias`** (desde `total_dias`), **`origen`** (etiqueta legible según `tipo`), **`codigo_cie10`**, **`diagnostico`** (descripción) y **`diagnostico_principal`** (código y descripción combinados). Así el front puede enlazar campos simples sin renderizar el objeto `diagnostico` como `[object Object]`. Los bloques originales del modelo (`paciente`, `diagnostico`, …) se mantienen.

### `GET /api/v1/incapacidades/{id}/archivo` (descarga)

- Mismos **roles** y reglas de acceso que el detalle.
- **404** si la incapacidad no existe, si no hay permiso, si no hay ruta de archivo o si el fichero no está en disco dentro del directorio de uploads.
- El `Content-Type` se infiere del tipo de archivo del trámite o de la extensión del fichero en disco.

### Estados del trámite — cómo dejar cada solicitud en un estado

Valores posibles del campo `estado` en `incapacidades`:

`recibida` · `procesando_ia` · `en_verificacion` · `inconsistencia_detectada` · `doc_incompleta` · `transcrita` · `cobrada` · `rechazada` · `pagada`

```mermaid
stateDiagram-v2
    [*] --> recibida: POST upload
    recibida --> procesando_ia: automático
    procesando_ia --> en_verificacion: extracción OK sin inconsistencias
    procesando_ia --> inconsistencia_detectada: extracción OK con hallazgos
    procesando_ia --> doc_incompleta: extracción IA falla
    en_verificacion --> transcrita: PATCH estado
    en_verificacion --> doc_incompleta: PUT doc. faltante o PATCH
    en_verificacion --> rechazada: PUT verificar o PATCH
    inconsistencia_detectada --> en_verificacion: PATCH estado
    inconsistencia_detectada --> doc_incompleta: PUT doc. faltante o PATCH
    inconsistencia_detectada --> rechazada: PUT verificar o PATCH
    doc_incompleta --> en_verificacion: PATCH estado
    transcrita --> cobrada: PATCH estado
    cobrada --> pagada: PATCH estado
    rechazada --> [*]
    pagada --> [*]
```

| Estado | Qué significa | Cómo llegar (acción) | Quién / endpoint |
|--------|----------------|----------------------|------------------|
| **`recibida`** | Trámite recién creado en BD | Ocurre un instante al registrar el upload; en la práctica la API responde ya en el siguiente estado | Automático (`POST …/upload`) |
| **`procesando_ia`** | Archivo guardado; extracción Gemini + OCR en segundo plano | Respuesta inmediata del upload (`201` con `"estado":"procesando_ia"`) | Automático |
| **`en_verificacion`** | Extracción IA terminó bien y sin inconsistencias estructuradas; RRHH debe revisar | Job en background tras upload (Gemini devuelve `inconsistencias: []`) | Automático |
| **`inconsistencia_detectada`** | La IA encontró anomalías de negocio (fechas, días, género/tipo, identificación, legibilidad, datos faltantes) | Job de extracción con array `inconsistencias` no vacío; se guardan filas en tabla **`inconsistencias`** | Automático |
| **`doc_incompleta`** | Faltan documentos o falló la lectura del archivo | **A)** Job de extracción falla → `extraccion_ia:…` en `documentacion_faltante` · **B)** RRHH registra pendientes desde `en_verificacion` o `inconsistencia_detectada` · **C)** `PATCH` manual | Automático o **RRHH** |
| **`transcrita`** | Trámite aprobado para el flujo de cobro | RRHH aprueba después de revisar datos | **RRHH** → `PATCH …/estado` con `"estado":"transcrita"` (solo desde `en_verificacion`) |
| **`cobrada`** | Cobro registrado ante la entidad | Avance administrativo post-transcripción | **RRHH** → `PATCH …/estado` con `"estado":"cobrada"` (solo desde `transcrita`) |
| **`pagada`** | Pago al colaborador completado | Estado terminal del ciclo de pago | **RRHH** → `PATCH …/estado` con `"estado":"pagada"` (solo desde `cobrada`) |
| **`rechazada`** | Trámite no procede | RRHH rechaza en verificación o cambia estado manualmente | **RRHH** → `PUT …/verificar` con `"accion":"rechazar"` **o** `PATCH …/estado` con `"estado":"rechazada"` (desde `en_verificacion`; `observacion` obligatoria en PATCH) |

**Notas:**

- Los cambios manuales de estado (`PATCH`, `PUT verificar`, `PUT documentacion-faltante`) requieren rol **`auxiliar_rrhh`**, **`coordinador_rrhh`** o **`admin`**.
- Cada cambio de estado manual (salvo `confirmar` sin cambio de estado) deja rastro en **`historial_estados`**.
- Desde **`rechazada`**, **`pagada`**, **`cobrada`** o **`transcrita`** no se puede volver atrás con los endpoints actuales.
- Para **documentación incompleta con lista explícita** de pendientes, preferir **`PUT …/documentacion-faltante`** (rellena `documentacion_faltante` y pasa a `doc_incompleta`).

**Secuencias típicas:**  
- Sin hallazgos: `upload` → `procesando_ia` → `en_verificacion` → `PATCH` `transcrita` → `cobrada` → `pagada`.  
- Con hallazgos IA: `upload` → `procesando_ia` → `inconsistencia_detectada` → (RRHH corrige/revisa) → `PATCH` `en_verificacion` → `transcrita` → …

### Flujo RRHH: verificar (aceptar/rechazar datos) vs cambio de estado

Dos endpoints complementarios; no son equivalentes:

| Intención | Endpoint | Efecto principal |
|-----------|----------|------------------|
| **Aceptar datos extraídos por IA** (revisión del JSON) | `PUT …/verificar` con `accion: confirmar` | Marca `verificado_por` / `verificado_en`; el trámite queda o vuelve a **`en_verificacion`**. No pasa a `transcrita`. |
| **Aprobar el trámite** (listo para cobro) | `PATCH …/estado` con `estado: transcrita` | Solo desde **`en_verificacion`**; registra historial. |
| **Rechazar el trámite** | `PUT …/verificar` con `rechazar` **o** `PATCH …/estado` con `rechazada` | Estado **`rechazada`**; el motivo va en `documentacion_faltante` (`motivo_rechazo` o `observacion` obligatoria en PATCH). |
| **Pedir documentos al colaborador** | `PUT …/documentacion-faltante` | Lista en `documentacion_faltante` y estado **`doc_incompleta`**. |
| **Revisar hallazgos de la IA** | Consultar `GET …/{id}` → `inconsistencias[]` | Trámite en **`inconsistencia_detectada`** tras extracción con anomalías. |
| **Continuar tras corregir hallazgos** | `PATCH …/estado` con `en_verificacion` | Desde **`inconsistencia_detectada`** o **`doc_incompleta`**. |
| **Colaborador subsanó** | `PATCH …/estado` con `en_verificacion` | Solo desde **`doc_incompleta`**. |

Secuencia típica de **aceptación completa**: extracción IA → `en_verificacion` → `PUT verificar` `confirmar` → `PATCH estado` `transcrita`.

### `PUT /api/v1/incapacidades/{id}/verificar` (revisión RRHH)

- **Roles:** solo `auxiliar_rrhh`, `coordinador_rrhh` y `admin` (un colaborador recibe **403**).
- Cuerpo JSON:

| Campo | Obligatorio | Descripción |
|-------|-------------|---------------|
| `accion` | Sí | `confirmar` o `rechazar` |
| `motivo_rechazo` | Sí si `rechazar` | Texto no vacío (se normaliza con trim); se guarda en `documentacion_faltante` como lista de un elemento |
| `datos_extraidos` | No | Si se envía con `confirmar`, **reemplaza** el JSON en `extraccion_ia` y se **enriquece** con los mismos campos UI que en el detalle (colaborador, `dias`, `origen`, diagnóstico plano) antes de persistir |

Comportamiento:

- Requiere que exista fila **`extraccion_ia`** para ese trámite; si no, **422**.
- Solo admite verificación si el estado es **`en_verificacion`**, **`inconsistencia_detectada`**, **`doc_incompleta`** o **`procesando_ia`**; en **`transcrita`**, **`cobrada`**, **`pagada`**, **`rechazada`** o **`recibida`** responde **409**.
- **`confirmar`:** actualiza metadatos de verificación; estado → **`en_verificacion`**. Si ya estaba en ese estado, **no** duplica fila en `historial_estados`.
- **`rechazar`:** estado → **`rechazada`**; persiste el motivo; historial solo si hubo cambio de estado.
- Tras **`rechazada`**, no se puede volver a verificar ni transcribir por PATCH.

Respuesta **200** (JSON): `id`, `radicado`, `estado`.

### `PATCH /api/v1/incapacidades/{id}/estado` (cambio de estado)

- **Roles:** solo `auxiliar_rrhh`, `coordinador_rrhh` y `admin`.
- Cuerpo JSON: `estado` (valor del enum del trámite) y `observacion` (auditoría; **obligatoria** si `estado` es `rechazada`).
- **400** si el trámite ya está en el estado solicitado.
- **409** si la transición no está permitida por la máquina de estados.
- **422** si se pide `rechazada` sin `observacion`.
- **404** si el `id` no existe.
- Al pasar a **`rechazada`**, `observacion` se guarda también en `documentacion_faltante` (un elemento).

Transiciones permitidas (origen → destinos):

| Estado actual | Puede pasar a |
|---------------|----------------|
| `en_verificacion` | `transcrita`, `doc_incompleta`, `rechazada` |
| `inconsistencia_detectada` | `en_verificacion`, `doc_incompleta`, `rechazada` |
| `doc_incompleta` | `en_verificacion` |
| `transcrita` | `cobrada` |
| `cobrada` | `pagada` |

Se inserta **`historial_estados`** con `estado_anterior`, `estado_nuevo`, `user_id` del actor y `timestamp` en UTC (explícito en la fila).

Respuesta **200** (JSON): `id`, `radicado`, `estado`, `estado_anterior`.

### `PUT /api/v1/incapacidades/{id}/documentacion-faltante`

- **Roles:** `auxiliar_rrhh`, `coordinador_rrhh`, `admin`.
- **Cuerpo:** `documentos` (lista de strings, al menos un ítem con texto no vacío); `observacion` opcional para auditoría.
- Persiste el listado en **`documentacion_faltante`** y deja el trámite en **`doc_incompleta`** cuando el estado actual es **`en_verificacion`** o **`inconsistencia_detectada`** (con registro en **`historial_estados`**).
- Si el trámite **ya** está en **`doc_incompleta`**, solo actualiza la lista (sin nuevo historial de cambio de estado).
- **404** si el `id` no existe; **409** si el estado no admite esta operación; **422** si la lista queda vacía tras normalizar.

Respuesta **200** (JSON): `id`, `radicado`, `estado`, `estado_anterior`, `documentacion_faltante`.

### Extracción IA (configuración)

El prompt versionado vive en **`app/prompts/Nomisalud_prompt_extraccion.md`**. Antes de llamar a Gemini, el job de extracción ejecuta **OCR local** (`ocr_processor`); si hay texto, se inyecta en la sección **«CONTEXTO ADICIONAL — TEXTO OCR»** del prompt (`build_extraction_prompt`). Sin OCR disponible, esa sección se omite.

#### Validación e inconsistencias (SCRUM-169 / SCRUM-170)

Gemini debe devolver, además de `validaciones`, el array obligatorio **`inconsistencias`**: objetos con `tipo` y `descripcion`. Categorías evaluadas en el prompt:

| `tipo` | Qué detecta |
|--------|-------------|
| `fechas` | Fechas incoherentes o futuras sin justificación |
| `dias` | `total_dias` no coincide con el rango declarado |
| `genero_tipo` | Incompatibilidad maternidad/paternidad vs género |
| `identificacion` | Documento inválido o formato atípico |
| `legibilidad` | Documento ilegible o campos críticos dudosos |
| `dato_faltante` | Campo crítico ausente cuando debería estar visible |

El backend parsea ese array (`parse_inconsistencias_desde_extraccion` en `ai_extractor.py`). Si hay al menos un ítem válido tras la extracción:

1. Inserta filas en **`inconsistencias`** (FK a `incapacidades`).
2. Deja el trámite en **`inconsistencia_detectada`**.
3. Guarda igualmente **`extraccion_ia`** con `datos_extraidos` y `validaciones`.

Si el array viene vacío, el flujo sigue en **`en_verificacion`**. El detalle HTTP expone `inconsistencias[]` para el front.

Variables relevantes (ver **`.env.example`**):

| Variable | Uso |
|----------|-----|
| `GEMINI_API_KEY` | Obligatoria para que la tarea en segundo plano llame a Google AI |
| `GEMINI_MODEL` | Valor por defecto en settings; el código de extracción usa fijo **`gemini-2.5-flash`** |
| `GEMINI_EXTRACTION_MAX_ATTEMPTS` | Reintentos ante 429 / 5xx / red |
| `GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS` | Backoff exponencial entre reintentos |
| `GEMINI_HTTP_TIMEOUT_SECONDS` | Timeout HTTP hacia la API de Gemini |

Además, para el listado de trámites: **`INCAPACIDADES_PAGE_SIZE`** (por defecto `20`) controla cuántos ítems devuelve cada página en `GET /api/v1/incapacidades`.

Sin `GEMINI_API_KEY`, el archivo se guarda y el trámite puede quedar en flujo de error de extracción al ejecutarse el job.

### OCR con Tesseract (SCRUM-165)

Dependencias Python: **`Pillow`** y **`pytesseract`** (`requirements.txt`). En Docker, el `Dockerfile` instala los paquetes de sistema **`tesseract-ocr`**, **`tesseract-ocr-eng`** y **`tesseract-ocr-spa`**.

| Variable | Uso |
|----------|-----|
| `TESSERACT_LANG` | Idiomas OCR (por defecto `spa+eng`) |
| `TESSERACT_CMD` | Ruta al binario `tesseract` si no está en `PATH` (opcional; útil en Windows) |

Servicios:

| Módulo | Uso |
|--------|-----|
| `ocr_tesseract.py` | OCR sobre una imagen (`extraer_texto_de_imagen`) |
| `ocr_processor.py` | Flujo completo (SCRUM-166): clasifica PDF nativo/escaneado, pre-procesa imágenes (gris + contraste) y devuelve `ResultadoProcesamientoOcr` |

Variables adicionales: `OCR_CONTRAST_FACTOR` (default `2.0`), `OCR_PDF_RENDER_DPI` (`200`), `OCR_MIN_CHARS_PDF_NATIVO` (`40`). En Docker también se instala **`poppler-utils`** (render de PDF escaneado vía `pdf2image`).

Validar en contenedor:

```bash
docker compose build api
docker compose run --rm api python -m pytest tests/services/test_ocr_tesseract.py -m integration -q
```

Los tests `@pytest.mark.integration` se omiten en hosts sin Tesseract; en la imagen Docker deben ejecutarse correctamente.

### Ejemplos `curl`

#### Health

```bash
curl -s http://localhost:8000/api/v1/health/
curl -s http://localhost:8000/api/v1/health/db
```

#### Login (obtener JWT)

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nomisalud.com","password":"Admin123!"}'
```

#### Upload de incapacidad (multipart)

Guarda el token y úsalo en el `Authorization: Bearer ...`.

```bash
TOKEN="PEGA_AQUI_EL_ACCESS_TOKEN"

curl -s -X POST http://localhost:8000/api/v1/incapacidades/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@./mi_incapacidad.pdf;type=application/pdf"
```

Respuesta típica: `{"radicado":"IN…","estado":"procesando_ia"}`. Cuando termine el job, revisa el detalle: `en_verificacion`, `inconsistencia_detectada` (con `inconsistencias[]`) o `doc_incompleta` si falló la extracción.

Si RRHH/admin carga para un colaborador específico:

```bash
COLABORADOR_ID="00000000-0000-0000-0000-000000000000"

curl -s -X POST http://localhost:8000/api/v1/incapacidades/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "colaborador_id=$COLABORADOR_ID" \
  -F "archivo=@./mi_incapacidad.png;type=image/png"
```

#### Listado de incapacidades (paginado)

```bash
curl -s "http://localhost:8000/api/v1/incapacidades?page=1&estado=transcrita" \
  -H "Authorization: Bearer $TOKEN"
```

Ejemplo con filtro por tipo de archivo y búsqueda por entidad (usa datos extraídos):

```bash
curl -s "http://localhost:8000/api/v1/incapacidades?tipo=pdf&entidad=sura" \
  -H "Authorization: Bearer $TOKEN"
```

#### Detalle, descarga y verificación

```bash
INCAPACIDAD_ID="550e8400-e29b-41d4-a716-446655440000"

# Detalle (JSON con extraccion_ia y archivo_url)
curl -s "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID" \
  -H "Authorization: Bearer $TOKEN"

# Descargar el PDF/imagen (guardar a disco)
curl -s -L -o incapacidad.pdf \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/archivo"

# Verificar con RRHH: confirmar datos (opcional: enviar datos_extraidos corregidos)
curl -s -X PUT "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/verificar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"accion":"confirmar"}'

# Rechazar (motivo obligatorio)
curl -s -X PUT "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/verificar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"accion":"rechazar","motivo_rechazo":"Documento ilegible"}'
```

Usa un token de usuario **auxiliar_rrhh**, **coordinador_rrhh** o **admin** para `PUT .../verificar`, `PUT .../documentacion-faltante` y `PATCH .../estado`.

```bash
# --- doc_incompleta (desde en_verificacion): lista de documentos pendientes ---
curl -s -X PUT "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/documentacion-faltante" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"documentos":["Certificado médico","Historia clínica"],"observacion":"Pendiente de subsanar"}'

# --- transcrita (aprobar trámite; solo desde en_verificacion) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"transcrita","observacion":"Aprobado en revisión"}'

# --- doc_incompleta (alternativa solo con PATCH, sin lista detallada) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"doc_incompleta","observacion":"Falta documentación"}'

# --- en_verificacion (desde doc_incompleta o inconsistencia_detectada) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"en_verificacion","observacion":"Hallazgos revisados / documentos recibidos"}'

# --- rechazada (desde en_verificacion; observacion obligatoria) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"rechazada","observacion":"No cumple requisitos"}'

# --- cobrada (solo desde transcrita) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"cobrada","observacion":"Radicado ante EPS"}'

# --- pagada (solo desde cobrada) ---
curl -s -X PATCH "http://localhost:8000/api/v1/incapacidades/$INCAPACIDAD_ID/estado" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"estado":"pagada","observacion":"Pago realizado al colaborador"}'
```

Para forzar **`doc_incompleta`** en pruebas sin RRHH: sube un archivo con extracción fallida (por ejemplo sin `GEMINI_API_KEY` en `.env`) o espera el error del job; el detalle/listado mostrará `estado: doc_incompleta`.

---

## Estructura del proyecto

```
nomisalud-back-end/
├── app/
│   ├── main.py               # Punto de entrada de FastAPI
│   ├── core/
│   │   ├── config.py         # Configuración (pydantic-settings)
│   │   ├── database.py       # Engine async y sesión de BD
│   │   ├── dependencies.py   # JWT y dependencias de rutas
│   │   └── security.py       # JWT, hash de contraseñas (bcrypt)
│   ├── api/
│   │   └── v1/
│   │       ├── router.py     # Agrupador de rutas v1
│   │       └── routes/
│   │           ├── auth.py
│   │           ├── demo.py
│   │           ├── health.py
│   │           └── incapacidades.py  # listado, detalle, archivo, verificar, patch estado, upload
│   ├── models/
│   │   ├── user.py
│   │   ├── incapacidad.py
│   │   ├── extraccion_ia.py  # Resultado IA (JSONB + raw_response)
│   │   ├── inconsistencia.py # Hallazgos IA (tipo + descripcion, FK incapacidad)
│   │   └── historial_estado.py
│   ├── prompts/
│   │   └── Nomisalud_prompt_extraccion.md  # Prompt Gemini (versionado en git)
│   ├── schemas/              # Esquemas Pydantic (DTOs)
│   ├── services/
│   │   ├── ocr_tesseract.py            # OCR con Pillow + pytesseract
│   │   ├── ocr_processor.py            # Clasificación nativo/escaneado + pre-procesado
│   │   ├── ai_extractor.py           # Llamada REST Gemini + normalización JSON
│   │   ├── incapacidad_extraction_jobs.py  # Job post-upload (BD + extracción)
│   │   ├── datos_extraidos_ui.py          # Enriquece datos_extraidos para contrato UI + IA
│   │   ├── incapacidad_list_service.py     # Consulta paginada y filtros (listado)
│   │   ├── incapacidad_detail_service.py   # Detalle + validación de ruta de adjunto
│   │   ├── incapacidad_estado_service.py   # PATCH estado + máquina de estados
│   │   ├── incapacidad_documentacion_service.py  # PUT documentación faltante
│   │   ├── incapacidad_verify_service.py   # Verificación manual RRHH (PUT verificar)
│   │   ├── incapacidad_storage.py
│   │   └── incapacidad_upload_service.py
│   └── repositories/
├── alembic/                  # Migraciones de base de datos
│   └── versions/             # users, incapacidades, extraccion_ia, inconsistencias, …
├── scripts/
│   └── seed.py               # Seed de usuarios de prueba
├── tests/
├── .env
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Migraciones con Alembic

El historial de migraciones cubre el dominio de usuarios, las tablas **incapacidades**, **extraccion_ia**, **inconsistencias**, **historial_estados** (incl. estado `inconsistencia_detectada` en el enum) y demás cambios en `alembic/versions`. Tras clonar o actualizar código, ejecuta siempre `upgrade head` antes de probar uploads con IA.

```bash
# Aplicar todas las migraciones pendientes
docker compose exec api alembic upgrade head

# Generar una nueva migración automática
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Revertir la última migración
docker compose exec api alembic downgrade -1
```

---

## Seed de datos de prueba

Inserta un usuario por cada rol disponible (idempotente: omite los que ya existen).

```bash
docker compose exec api python -m scripts.seed
```

Usuarios generados:

| Email                          | Rol               | Contraseña              |
|--------------------------------|-------------------|-------------------------|
| colaborador@nomisalud.com      | colaborador       | Colaborador123!         |
| auxiliar.rrhh@nomisalud.com    | auxiliar_rrhh     | AuxiliarRRHH123!        |
| coordinador.rrhh@nomisalud.com | coordinador_rrhh  | CoordinadorRRHH123!     |
| admin@nomisalud.com            | admin             | Admin123!               |

---

## Comandos Docker útiles

```bash
# Levantar en segundo plano
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f api

# Abrir shell dentro del contenedor api
docker compose exec api bash

# Parar contenedores sin borrar datos
docker compose down

# Parar contenedores Y borrar volúmenes (reset total de la BD)
docker compose down -v
```

> **Importante:** `docker compose down -v` elimina todos los datos de la base de datos.
> Después de usarlo debes volver a ejecutar la migración y el seed.

---

## Conexión a la base de datos (pgAdmin u otro cliente)

El puerto de PostgreSQL está mapeado al `5433` del host para evitar conflictos
con instalaciones locales de PostgreSQL que usan el `5432` por defecto.

| Campo          | Valor               |
|----------------|---------------------|
| Host           | `localhost`         |
| Puerto         | `5433`              |
| Base de datos  | `nomisalud_db`      |
| Usuario        | `nomisalud`         |
| Contraseña     | `nomisalud_password`|

### pgAdmin (escritorio)

1. Clic derecho en **Servers → Register → Server**
2. Tab **General** → Nombre: `NomiSalud Dev`
3. Tab **Conexión** → completa los campos de la tabla anterior
4. **Guardar**

### psql desde terminal (sin instalar nada extra)

```bash
# Entrar al contenedor de la BD directamente
docker compose exec db psql -U nomisalud -d nomisalud_db

# Comandos útiles dentro de psql:
\dt                            -- listar tablas
\d users                       -- estructura de la tabla users
\d extraccion_ia               -- extracción IA vinculada a incapacidades (1:1)
\d inconsistencias             -- hallazgos por incapacidad (1:N)
SELECT id, estado FROM incapacidades ORDER BY created_at DESC LIMIT 5;
SELECT tipo, descripcion FROM inconsistencias WHERE incapacidad_id = 'UUID-del-tramite';
SELECT * FROM users;           -- ver registros
SELECT * FROM alembic_version; -- ver migraciones aplicadas
\q                             -- salir
```

---

## Tests y cobertura

```bash
# Ejecutar suite completa con reporte de cobertura
.venv\Scripts\python.exe -m pytest

# Solo los tests nuevos sin cobertura (más rápido)
.venv\Scripts\python.exe -m pytest tests/core tests/models -v --no-cov
```

La cobertura mínima requerida es **80%** (configurada en `pyproject.toml`).

---

## Desarrollo local (sin Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Asegurarse de que POSTGRES_HOST=localhost en .env
uvicorn app.main:app --reload
```
