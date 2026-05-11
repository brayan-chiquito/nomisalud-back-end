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
- Tras un extracción **correcta**, el estado pasa a **`en_verificacion`** y se crea la fila en **`extraccion_ia`** (`datos_extraidos`, `validaciones`, `raw_response`, modelo, etc.).
- Si la extracción **falla** (archivo, API, JSON inválido…), el estado suele quedar en **`doc_incompleta`** con detalle en `documentacion_faltante`.

Roles permitidos en upload: `colaborador`, `auxiliar_rrhh`, `coordinador_rrhh`, `admin`. Un colaborador solo puede cargar para sí mismo salvo que RRHH/admin indiquen `colaborador_id` en el formulario.

### Extracción IA (configuración)

El prompt versionado vive en **`app/prompts/Nomisalud_prompt_extraccion.md`**. Variables relevantes (ver **`.env.example`**):

| Variable | Uso |
|----------|-----|
| `GEMINI_API_KEY` | Obligatoria para que la tarea en segundo plano llame a Google AI |
| `GEMINI_MODEL` | Valor por defecto en settings; el código de extracción usa fijo **`gemini-2.5-flash`** |
| `GEMINI_EXTRACTION_MAX_ATTEMPTS` | Reintentos ante 429 / 5xx / red |
| `GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS` | Backoff exponencial entre reintentos |
| `GEMINI_HTTP_TIMEOUT_SECONDS` | Timeout HTTP hacia la API de Gemini |

Sin `GEMINI_API_KEY`, el archivo se guarda y el trámite puede quedar en flujo de error de extracción al ejecutarse el job.

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

Respuesta típica: `{"radicado":"IN…","estado":"procesando_ia"}`. Consulta el trámite en base de datos (o un futuro endpoint de detalle) para ver `en_verificacion` / `doc_incompleta` cuando termine el job.

Si RRHH/admin carga para un colaborador específico:

```bash
COLABORADOR_ID="00000000-0000-0000-0000-000000000000"

curl -s -X POST http://localhost:8000/api/v1/incapacidades/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "colaborador_id=$COLABORADOR_ID" \
  -F "archivo=@./mi_incapacidad.png;type=image/png"
```


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
│   │           └── incapacidades.py  # POST upload + BackgroundTasks
│   ├── models/
│   │   ├── user.py
│   │   ├── incapacidad.py
│   │   ├── extraccion_ia.py  # Resultado IA (JSONB + raw_response)
│   │   └── historial_estado.py
│   ├── prompts/
│   │   └── Nomisalud_prompt_extraccion.md  # Prompt Gemini (versionado en git)
│   ├── schemas/              # Esquemas Pydantic (DTOs)
│   ├── services/
│   │   ├── ai_extractor.py           # Llamada REST Gemini + normalización JSON
│   │   ├── incapacidad_extraction_jobs.py  # Job post-upload (BD + extracción)
│   │   ├── incapacidad_storage.py
│   │   └── incapacidad_upload_service.py
│   └── repositories/
├── alembic/                  # Migraciones de base de datos
│   └── versions/             # users, dominio incapacidades, extraccion_ia, raw_response, …
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

El historial incluye dominio de usuarios, **incapacidades**, **extraccion_ia** (incl. columna **`raw_response`**), **historial_estados**, etc. Tras clonar o actualizar código, ejecuta siempre `upgrade head` antes de probar uploads con IA.

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
