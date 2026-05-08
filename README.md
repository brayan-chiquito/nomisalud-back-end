# NomiSalud — Backend API

API REST construida con **FastAPI**, **PostgreSQL** (async con SQLAlchemy) y **Docker**.

---

## Requisitos

- [Docker](https://www.docker.com/) y Docker Compose
- Python 3.12+ (solo para desarrollo local sin Docker)

---

## Levantar el proyecto con Docker

```bash
# 1. Copiar variables de entorno
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

| Método | Ruta                           | Descripción |
|--------|--------------------------------|-------------|
| GET    | `/api/v1/health/`              | Estado básico de la API |
| GET    | `/api/v1/health/db`            | Verifica conexión a PostgreSQL |
| POST   | `/api/v1/auth/login`           | Autenticación (retorna JWT) |
| POST   | `/api/v1/incapacidades/upload` | Carga multipart (archivo) y crea trámite |
| GET    | `/api/v1/demo/me`              | [DEMO] Payload del JWT decodificado |
| GET    | `/api/v1/demo/colaborador`     | [DEMO] Acceso por cualquier rol |
| GET    | `/api/v1/demo/rrhh`            | [DEMO] Acceso RRHH/admin |
| GET    | `/api/v1/demo/admin`           | [DEMO] Acceso solo admin |

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
│   │   └── security.py       # Hash y verificación de contraseñas (bcrypt)
│   ├── api/
│   │   └── v1/
│   │       ├── router.py     # Agrupador de rutas v1
│   │       └── routes/
│   │           └── health.py # Endpoints de health check
│   ├── models/
│   │   └── user.py           # Modelo User + enum UserRole
│   ├── schemas/              # Esquemas Pydantic (DTOs)
│   ├── services/             # Lógica de negocio
│   └── repositories/         # Capa de acceso a datos
├── alembic/                  # Migraciones de base de datos
│   └── versions/
│       └── 3f8a9c12b4e7_create_users_table.py
├── scripts/
│   └── seed.py               # Seed de usuarios de prueba
├── tests/                    # Pruebas unitarias e integración
├── .env                      # Variables de entorno (no subir a git)
├── .env.example              # Plantilla de variables de entorno
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Migraciones con Alembic

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
