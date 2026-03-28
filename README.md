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

| Método | Ruta                  | Descripción                     |
|--------|-----------------------|---------------------------------|
| GET    | `/api/v1/health/`     | Hola Mundo / estado de la API   |
| GET    | `/api/v1/health/db`   | Verifica conexión a PostgreSQL  |

---

## Estructura del proyecto

```
nomisalud-back-end/
├── app/
│   ├── main.py               # Punto de entrada de FastAPI
│   ├── core/
│   │   ├── config.py         # Configuración (pydantic-settings)
│   │   └── database.py       # Engine async y sesión de BD
│   ├── api/
│   │   └── v1/
│   │       ├── router.py     # Agrupador de rutas v1
│   │       └── routes/
│   │           └── health.py # Endpoints de health check
│   ├── models/               # Modelos SQLAlchemy
│   ├── schemas/              # Esquemas Pydantic (DTOs)
│   ├── services/             # Lógica de negocio
│   └── repositories/         # Capa de acceso a datos
├── alembic/                  # Migraciones de base de datos
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
# Ejecutar dentro del contenedor api
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head
```

---

## Desarrollo local (sin Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Asegurarse de que POSTGRES_HOST=localhost en .env
uvicorn app.main:app --reload
```
