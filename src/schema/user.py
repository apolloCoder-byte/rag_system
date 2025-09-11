"""This file contains the user model for the application."""

import bcrypt
from sqlmodel import Field
from src.schema.base import BaseModel


class User(BaseModel, table=True):
    """User model for storing user accounts.

    Attributes:
        id: The primary key
        email: User's email (unique)
        hashed_password: Bcrypt hashed password
        created_at: When the user was created
    """

    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str

    def verify_password(self, password: str) -> bool:
        """Verify if the provided password matches the hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
