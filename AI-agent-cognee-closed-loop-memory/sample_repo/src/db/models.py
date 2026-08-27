"""SQLAlchemy database models."""

class User:
    def __init__(self, id: int, username: str, tenant_id: int, email: str):
        self.id = id
        self.username = username
        self.tenant_id = tenant_id
        self.email = email
