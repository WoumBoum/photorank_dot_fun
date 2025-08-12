from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    provider: str
    provider_id: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryOut(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class CategoryDetail(CategoryBase):
    id: int
    created_at: datetime
    total_votes: int
    current_leader_filename: Optional[str] = None
    current_leader_elo: Optional[float] = None
    current_leader_owner: Optional[str] = None

    class Config:
        orm_mode = True


class PhotoBase(BaseModel):
    filename: str


class PhotoCreate(PhotoBase):
    category_id: int


class PhotoOut(PhotoBase):
    id: int
    elo_rating: float
    total_duels: int
    wins: int
    created_at: datetime
    owner_id: int
    owner_username: str
    category_id: int
    category_name: str

    class Config:
        orm_mode = True


class VoteCreate(BaseModel):
    winner_id: int
    loser_id: int


class VoteOut(BaseModel):
    id: int
    user_id: int
    winner_id: int
    loser_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class PhotoPair(BaseModel):
    photos: list[PhotoOut]


class LeaderboardEntry(BaseModel):
    id: int
    filename: str
    elo_rating: float
    total_duels: int
    wins: int
    owner_username: str
    rank: int
    category_name: str


class UserStats(BaseModel):
    photos: list[LeaderboardEntry]
    total_photos: int
    total_votes: int