from pydantic import BaseModel


class AuthUser(BaseModel):
    """Authenticated user identity derived from a verified Google ID token."""

    id: str  # Google's stable subject identifier ("sub")
    email: str = ""
    name: str = ""
    picture: str = ""
