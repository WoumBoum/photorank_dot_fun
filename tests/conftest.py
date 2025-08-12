import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
import tempfile
import shutil

from pathlib import Path
from app import models
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.oauth2 import create_access_token

# Test database URL
SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}_test'

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine)

# Create test upload directory
test_upload_dir = tempfile.mkdtemp()


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    
    db = TestingSessionLocal(bind=connection)
    
    yield db
    
    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    
    # Override upload directory for tests
    from app.routers import photos
    original_upload_dir = photos.UPLOAD_DIR
    photos.UPLOAD_DIR = Path(test_upload_dir)
    
    yield TestClient(app)
    
    # Cleanup
    app.dependency_overrides.clear()
    photos.UPLOAD_DIR = original_upload_dir


@pytest.fixture
def test_user(session):
    """Create a test user"""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "provider": "github",
        "provider_id": "123456"
    }
    
    user = models.User(**user_data)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


@pytest.fixture
def test_user2(session):
    """Create a second test user"""
    user_data = {
        "email": "test2@example.com",
        "username": "testuser2",
        "provider": "google",
        "provider_id": "789012"
    }
    
    user = models.User(**user_data)
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


@pytest.fixture
def token(test_user):
    """Create JWT token for test user"""
    return create_access_token({"user_id": test_user.id})


@pytest.fixture
def authorized_client(client, token):
    """Client with authorization header"""
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {token}"
    }
    return client


@pytest.fixture
def test_photos(session, test_user, test_user2):
    """Create test photos"""
    photos_data = [
        {
            "filename": "photo1.jpg",
            "elo_rating": 1200.0,
            "total_duels": 0,
            "wins": 0,
            "owner_id": test_user.id
        },
        {
            "filename": "photo2.jpg",
            "elo_rating": 1250.0,
            "total_duels": 10,
            "wins": 7,
            "owner_id": test_user.id
        },
        {
            "filename": "photo3.jpg",
            "elo_rating": 1150.0,
            "total_duels": 5,
            "wins": 2,
            "owner_id": test_user2.id
        },
        {
            "filename": "photo4.jpg",
            "elo_rating": 1300.0,
            "total_duels": 60,
            "wins": 45,
            "owner_id": test_user2.id
        }
    ]
    
    photos = []
    for photo_data in photos_data:
        photo = models.Photo(**photo_data)
        session.add(photo)
        session.commit()
        session.refresh(photo)
        photos.append(photo)
    
    return photos


@pytest.fixture
def test_votes(session, test_user, test_photos):
    """Create test votes"""
    votes_data = [
        {
            "user_id": test_user.id,
            "winner_id": test_photos[1].id,
            "loser_id": test_photos[0].id
        },
        {
            "user_id": test_user.id,
            "winner_id": test_photos[3].id,
            "loser_id": test_photos[2].id
        }
    ]
    
    votes = []
    for vote_data in votes_data:
        vote = models.Vote(**vote_data)
        session.add(vote)
        session.commit()
        session.refresh(vote)
        votes.append(vote)
    
    return votes


@pytest.fixture
def test_upload_limits(session, test_user):
    """Create test upload limits"""
    upload_limit = models.UploadLimit(
        user_id=test_user.id,
        upload_count=2,
        last_upload_date=datetime.utcnow() - timedelta(hours=12)
)
    session.add(upload_limit)
    session.commit()
    session.refresh(upload_limit)
    return upload_limit


from pathlib import Path