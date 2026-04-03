import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    COLABORADOR = "colaborador"
    AUXILIAR_RRHH = "auxiliar_rrhh"
    COORDINADOR_RRHH = "coordinador_rrhh"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    # Mapped[T] (no Optional) ya implica NOT NULL en SQLAlchemy 2.x
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        # values_callable fuerza a SQLAlchemy a usar .value ("colaborador")
        # en vez del .name ("COLABORADOR") al persistir en PostgreSQL.
        Enum(
            UserRole,
            name="userrole",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
