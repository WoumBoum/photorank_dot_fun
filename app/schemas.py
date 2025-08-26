from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional, List
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


class CategoryCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    question: constr(strip_whitespace=True, min_length=4, max_length=200)


class CategoryUpdate(BaseModel):
    name: Optional[constr(strip_whitespace=True, min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")]
    question: Optional[constr(strip_whitespace=True, min_length=4, max_length=200)]
    description: Optional[constr(strip_whitespace=True, max_length=200)] = None


class CategoryOut(CategoryBase):
    id: int
    created_at: datetime
    question: str
    owner_id: Optional[int] = None

    class Config:
        orm_mode = True


class CategoryDetail(CategoryBase):
    id: int
    created_at: datetime
    total_votes: int
    owner_id: Optional[int] = None
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
    photos: List[PhotoOut]
    progress: Optional[str] = None
    progress_percentage: Optional[float] = None
    votes_until_important: Optional[int] = None
    is_important_match: Optional[bool] = None
    photo1_rank: Optional[int] = None
    photo2_rank: Optional[int] = None


class LeaderboardEntry(BaseModel):
    id: int
    filename: str
    elo_rating: float
    total_duels: int
    wins: int
    owner_username: str
    rank: int
    category_name: str


class UsernameUpdate(BaseModel):
    username: constr(strip_whitespace=True, min_length=3, max_length=20, pattern=r"^[a-z0-9_-]+$")


class UserStats(BaseModel):
    photos: List[LeaderboardEntry]
    total_photos: int
    total_votes: int