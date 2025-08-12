import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pathlib import Path
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta

from app.models import Photo, User, UploadLimit


class TestPhotoUpload:
    """Test photo upload functionality"""
    
    def test_upload_photo_success(self, authorized_client: TestClient, test_user):
        """Test successful photo upload"""
        # Create test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"].endswith(".jpg")
        assert data["elo_rating"] == 1200.0
        assert data["total_duels"] == 0
        assert data["wins"] == 0
        assert data["owner_id"] == test_user.id
    
    def test_upload_invalid_file_type(self, authorized_client: TestClient):
        """Test upload with invalid file type"""
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 400
        assert "must be an image" in response.json()["detail"]
    
    def test_upload_without_auth(self, client: TestClient):
        """Test upload without authentication"""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 401
    
    def test_upload_rate_limiting(self, authorized_client: TestClient, test_user, session: Session):
        """Test upload rate limiting (5 per day)"""
        # Create upload limit record
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=5,
            last_upload_date=datetime.utcnow()
        )
        session.add(upload_limit)
        session.commit()
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 429
        assert "Daily upload limit reached" in response.json()["detail"]
    
    def test_upload_rate_limit_reset(self, authorized_client: TestClient, test_user, session: Session):
        """Test rate limit reset after 24 hours"""
        # Create upload limit record from yesterday
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=5,
            last_upload_date=datetime.utcnow() - timedelta(days=2)
        )
        session.add(upload_limit)
        session.commit()
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200  # Should succeed as it's a new day
    
    def test_upload_increment_counter(self, authorized_client: TestClient, test_user, session: Session):
        """Test upload counter increment"""
        # Check initial upload limit
        upload_limit = session.query(UploadLimit).filter(
            UploadLimit.user_id == test_user.id
        ).first()
        initial_count = upload_limit.upload_count if upload_limit else 0
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        
        # Check counter incremented
        upload_limit = session.query(UploadLimit).filter(
            UploadLimit.user_id == test_user.id
        ).first()
        assert upload_limit.upload_count == initial_count + 1
    
    def test_upload_large_file(self, authorized_client: TestClient):
        """Test upload with large file"""
        # Create large image (1MB)
        img = Image.new('RGB', (1000, 1000), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG', quality=95)
        img_bytes.seek(0)
        
        files = {"file": ("large.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200


class TestPhotoRetrieval:
    """Test photo retrieval functionality"""
    
    def test_get_photo_pair(self, authorized_client: TestClient, test_photos):
        """Test getting random photo pair"""
        response = authorized_client.get("/api/photos/pair")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["photos"]) == 2
        
        for photo in data["photos"]:
            assert "id" in photo
            assert "filename" in photo
            assert "elo_rating" in photo
            assert "owner_username" in photo
    
    def test_get_photo_pair_insufficient_photos(self, authorized_client: TestClient):
        """Test getting pair with insufficient photos"""
        response = authorized_client.get("/api/photos/pair")
        
        assert response.status_code == 404
        assert "Not enough photos" in response.json()["detail"]
    
    def test_get_photo_by_filename(self, authorized_client: TestClient, test_photos):
        """Test retrieving photo by filename"""
        filename = test_photos[0].filename
        response = authorized_client.get(f"/api/photos/{filename}")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
    
    def test_get_nonexistent_photo(self, authorized_client: TestClient):
        """Test retrieving non-existent photo"""
        response = authorized_client.get("/api/photos/nonexistent.jpg")
        
        assert response.status_code == 404


class TestPhotoProperties:
    """Test photo properties and defaults"""
    
    def test_default_elo_rating(self, authorized_client: TestClient, test_user):
        """Test default ELO rating is 1200"""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        assert response.json()["elo_rating"] == 1200.0
    
    def test_default_duel_counts(self, authorized_client: TestClient, test_user):
        """Test default duel counts are 0"""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        assert response.json()["total_duels"] == 0
        assert response.json()["wins"] == 0
    
    def test_filename_uniqueness(self, authorized_client: TestClient, test_user):
        """Test filename uniqueness constraint"""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response1 = authorized_client.post("/api/photos/upload", files=files)
        assert response1.status_code == 200
        
        # Upload same filename - should still succeed (UUID will make it unique)
        img_bytes.seek(0)
        response2 = authorized_client.post("/api/photos/upload", files=files)
        assert response2.status_code == 200
        assert response1.json()["filename"] != response2.json()["filename"]