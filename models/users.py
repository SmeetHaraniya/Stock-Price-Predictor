from pydantic import BaseModel

class Users(BaseModel):
    username: str
    email: str
    password_hash: str
    cash: float = 10000.00