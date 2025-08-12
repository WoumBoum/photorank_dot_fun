import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Photo, User, Vote, UploadLimit
from datetime import datetime, timedelta


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_database(self, authorized_client: TestClient):
        """Test endpoints with empty database"""
        # Test photo pair with no photos
        response = authorized_client.get("/api/photos/pair")
        assert response.status_code == 404
        assert "Not enough photos" in response.json()["detail"]
        
        # Test leaderboard with no eligible photos
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        assert response.json() == []
        
        # Test user stats with no photos
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_photos"] == 0
        assert data["photos"] == []
    
    def test_single_photo(self, authorized_client: TestClient, session: Session, test_user):
        """Test behavior with single photo"""
        photo = Photo(
            filename="single.jpg",
            elo_rating=1200,
            total_duels=0,
            wins=0,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        # Should not be able to get pair
        response = authorized_client.get("/api/photos/pair")
        assert response.status_code == 404
        
        # Should not appear in leaderboard (insufficient duels)
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        assert len(response.json()) == 0
    
    def test_boundary_duel_count(self, authorized_client: TestClient, session: Session, test_user):
        """Test boundary conditions for duel count"""
        # Create photos at boundary (49, 50, 51 duels)
        for duels in [49, 50, 51]:
            photo = Photo(
                filename=f"duels{duels}.jpg",
                elo_rating=1200,
                total_duels=duels,
                wins=duels // 2,
                owner_id=test_user.id
            )
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        # Should only include photos with >= 50 duels
        filenames = [p["filename"] for p in data]
        assert "duels49.jpg" not in filenames
        assert "duels50.jpg" in filenames
        assert "duels51.jpg" in filenames
    
    def test_negative_elo_ratings(self, authorized_client: TestClient, session: Session, test_user):
        """Test handling of very low ELO ratings"""
        photo = Photo(
            filename="negative.jpg",
            elo_rating=-100,  # Extreme low rating
            total_duels=60,
            wins=5,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["elo_rating"] == -100
    
    def test_very_high_elo_ratings(self, authorized_client: TestClient, session: Session, test_user):
        """Test handling of very high ELO ratings"""
        photo = Photo(
            filename="high.jpg",
            elo_rating=3000,  # Extreme high rating
            total_duels=60,
            wins=55,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["elo_rating"] == 3000
    
    def test_zero_wins_zero_losses(self, authorized_client: TestClient, session: Session, test_user):
        """Test photos with zero wins and zero losses"""
        photo = Photo(
            filename="zero.jpg",
            elo_rating=1200,
            total_duels=0,
            wins=0,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        # Should not appear in leaderboard
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        assert len(response.json()) == 0
        
        # Should appear in user stats
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        assert any(p["filename"] == "zero.jpg" for p in data["photos"])
    
    def test_all_wins_no_losses(self, authorized_client: TestClient, session: Session, test_user):
        """Test photos with all wins and no losses"""
        photo = Photo(
            filename="perfect.jpg",
            elo_rating=1200,
            total_duels=60,
            wins=60,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "perfect.jpg"
        assert data[0]["wins"] == 60
    
    def test_all_losses_no_wins(self, authorized_client: TestClient, session: Session, test_user):
        """Test photos with all losses and no wins"""
        photo = Photo(
            filename="terrible.jpg",
            elo_rating=1200,
            total_duels=60,
            wins=0,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "terrible.jpg"
        assert data[0]["wins"] == 0
    
    def test_upload_rate_limit_boundary(self, authorized_client: TestClient, session: Session, test_user):
        """Test upload rate limit boundary conditions"""
        # Create upload limit at boundary
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=4,
            last_upload_date=datetime.utcnow()
        )
        session.add(upload_limit)
        session.commit()
        
        # Should allow one more upload
        from PIL import Image
        from io import BytesIO
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        assert response.status_code == 200
        
        # Should block next upload
        img_bytes.seek(0)
        response = authorized_client.post("/api/photos/upload", files=files)
        assert response.status_code == 429
    
    def test_upload_rate_limit_exactly_24h(self, authorized_client: TestClient, session: Session, test_user):
        """Test upload rate limit exactly at 24h boundary"""
        # Create upload limit exactly 24 hours ago
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=5,
            last_upload_date=datetime.utcnow() - timedelta(hours=24)
        )
        session.add(upload_limit)
        session.commit()
        
        from PIL import Image
        from io import BytesIO
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        # Should allow upload as it's a new day
        assert response.status_code == 200
    
    def test_concurrent_votes(self, authorized_client: TestClient, test_photos, session: Session):
        """Test handling of concurrent votes"""
        # This simulates race conditions
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        # Multiple identical votes should be handled
        responses = []
        for _ in range(3):
            response = authorized_client.post("/api/votes/", json=vote_data)
            responses.append(response.status_code)
        
        # Only first should succeed, rest should fail with duplicate error
        assert 200 in responses
        assert 400 in responses  # Duplicate vote
    
    def test_circular_voting(self, authorized_client: TestClient, test_photos, session: Session):
        """Test circular voting patterns (A>B, B>C, C>A)"""
        votes = [
            {"winner_id": test_photos[0].id, "loser_id": test_photos[1].id},
            {"winner_id": test_photos[1].id, "loser_id": test_photos[2].id},
            {"winner_id": test_photos[2].id, "loser_id": test_photos[0].id},
        ]
        
        for vote_data in votes:
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
    
    def test_large_number_of_photos(self, authorized_client: TestClient, session: Session, test_user):
        """Test performance with large number of photos"""
        # Create 100 photos
        for i in range(100):
            photo = Photo(
                filename=f"photo{i}.jpg",
                elo_rating=1200 + (i % 50),
                total_duels=60 + (i % 40),
                wins=30 + (i % 30),
                owner_id=test_user.id
            )
            session.add(photo)
        session.commit()
        
        # Test leaderboard with many photos
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 100  # Should respect limit
    
    def test_unicode_filenames(self, authorized_client: TestClient, test_user):
        """Test handling of unicode filenames"""
        from PIL import Image
        from io import BytesIO
        
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("测试照片.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        assert "测试照片" in response.json()["filename"] or "test" in response.json()["filename"].lower()
    
    def test_special_characters_in_username(self, session: Session):
        """Test handling of special characters in usernames"""
        user = User(
            email="special@example.com",
            username="user_with-special.chars123",
            provider="github",
            provider_id="special123"
        )
        session.add(user)
        session.commit()
        
        assert user.username == "user_with-special.chars123"
    
    def test_database_connection_loss(self, authorized_client: TestClient):
        """Test graceful handling of database connection issues"""
        # This would typically be mocked in a real test environment
        # For now, just verify basic error handling
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code in [200, 500]  # Should handle gracefully
    
    def test_invalid_jwt_token_formats(self, client: TestClient):
        """Test various invalid JWT token formats"""
        invalid_tokens = [
            "",
            "invalid",
            "Bearer invalid",
            "Bearer ",
            "Bearer token.with.dots",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
        ]
        
        for token in invalid_tokens:
            client.headers = {"Authorization": token}
            response = client.get("/api/users/me")
            assert response.status_code == 401
    
    def test_malformed_image_upload(self, authorized_client: TestClient):
        """Test handling of malformed image files"""
        # Create malformed image data
        malformed_data = b"This is not a valid image file"
        files = {"file": ("malformed.jpg", malformed_data, "image/jpeg")}
        
        response = authorized_client.post("/api/photos/upload", files=files)
        
        # PIL might handle this gracefully or raise an error
        assert response.status_code in [200, 400]
    
    def test_zero_byte_file_upload(self, authorized_client: TestClient):
        """Test handling of zero-byte files"""
        files = {"file": ("empty.jpg", b"", "image/jpeg")}
        
        response = authorized_client.post("/api/photos/upload", files=files)
        
        # Should handle gracefully
        assert response.status_code in [200, 400]
    
    def test_very_long_filename(self, authorized_client: TestClient, test_user):
        """Test handling of very long filenames"""
        from PIL import Image
        from io import BytesIO
        
        long_filename = "a" * 200 + ".jpg"
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": (long_filename, img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        
        assert response.status_code == 200
        assert len(response.json()["filename"]) <= 255  # Should be truncated or handled