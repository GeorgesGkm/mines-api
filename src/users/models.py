from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from src.core.database import Base

# Table d'association Many-to-Many
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relation vers les rôles
    roles = relationship("Role", secondary=user_roles, back_populates="users")

    #user vers personnel
    agent = relationship("Agent", back_populates="user_rattache", uselist=False)

    
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False) # ex: "admin", "user"
    description = Column(String, nullable=True)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")