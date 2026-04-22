from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class User(BaseModel):
    id: str = Field(default_factory=lambda: None)
    name: str
    email: EmailStr
    password_hash: str
    
    # Personal API Credentials
    search_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

class UserInDB(User):
    pass

class UserPublic(BaseModel):
    name: str
    email: str
    has_keys: bool
