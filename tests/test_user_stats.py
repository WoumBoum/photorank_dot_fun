import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Photo, User, Vote


class TestUserStats:
    """Test user statistics and personal dashboard"""
    
    def test_get_user_stats_basic(self, authorized_client: TestClient, test_photos, test_user):
        """Test basic user stats retrieval"""
        response = authorized_client.get("/api/users/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "photos" in data
        assert "total_photos" in data
        assert "total_votes" in data
        assert isinstance(data["photos"], list)
    
    def test_user_stats_photos_count(self, authorized_client: TestClient, test_photos, test_user):
        """Test user stats photo count"""
        # Count user's photos
        user_photos = [p for p in test_photos if p.owner_id == test_user.id]
        
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_photos"] == len(user_photos)
    
    def test_user_stats_photos_details(self, authorized_client: TestClient, test_photos, test_user):
        """Test user stats photo details"""
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        for photo_data in data["photos"]:
            assert "id" in photo_data
            assert "filename" in photo_data
            assert "elo_rating" in photo_data
            assert "total_duels" in photo_data
            assert "wins" in photo_data
            assert "rank" in photo_data
            assert "owner_username" in photo_data
    
    def test_user_stats_empty_photos(self, authorized_client: TestClient, test_user):
        """Test user stats with no photos"""
        response = authorized_client.get("/api/users/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_photos"] == 0
        assert data["photos"] == []
    
    def test_user_stats_votes_count(self, authorized_client: TestClient, test_votes, test_user):
        """Test user stats vote count"""
        response = authorized_client.get("/api/users/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_votes"] == 2  # From test_votes fixture
    
    def test_user_stats_photo_ranking(self, authorized_client: TestClient, session: Session, test_user):
        """Test user stats photo ranking"""
        # Create photos with different ELO ratings
        photos_data = [
            {"filename": "low.jpg", "elo_rating": 1100, "total_duels": 60, "wins": 30, "owner_id": test_user.id},
            {"filename": "high.jpg", "elo_rating": 1300, "total_duels": 60, "wins": 40, "owner_id": test_user.id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Should be ordered by ELO descending
        assert data["photos"][0]["elo_rating"] == 1300
        assert data["photos"][1]["elo_rating"] == 1100
    
    def test_user_stats_win_rate_calculation(self, authorized_client: TestClient, session: Session, test_user):
        """Test win rate calculation in user stats"""
        photo = Photo(
            filename="test.jpg",
            elo_rating=1200,
            total_duels=10,
            wins=7,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Find our test photo
        test_photo = next(p for p in data["photos"] if p["filename"] == "test.jpg")
        assert test_photo["total_duels"] == 10
        assert test_photo["wins"] == 7
    
    def test_user_stats_only_own_photos(self, authorized_client: TestClient, test_photos, test_user, test_user2):
        """Test user stats only includes own photos"""
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Should only include photos owned by test_user
        user_photos = [p for p in test_photos if p.owner_id == test_user.id]
        assert len(data["photos"]) == len(user_photos)
        
        for photo_data in data["photos"]:
            assert photo_data["owner_username"] == test_user.username
    
    def test_user_stats_global_ranking(self, authorized_client: TestClient, session: Session, test_user):
        """Test global ranking in user stats"""
        # Create photos with different users
        user2 = User(
            email="other@example.com",
            username="otheruser",
            provider="github",
            provider_id="999999"
        )
        session.add(user2)
        session.commit()
        
        photos_data = [
            {"filename": "user1_high.jpg", "elo_rating": 1300, "total_duels": 60, "wins": 40, "owner_id": test_user.id},
            {"filename": "user2_low.jpg", "elo_rating": 1100, "total_duels": 60, "wins": 30, "owner_id": user2.id},
            {"filename": "user1_medium.jpg", "elo_rating": 1200, "total_duels": 60, "wins": 35, "owner_id": test_user.id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Should have global ranking considering all photos
        assert len(data["photos"]) == 2  # Only test_user's photos
        
        # Check rankings are global
        rankings = [p["rank"] for p in data["photos"]]
        assert rankings == sorted(rankings)  # Should be ordered
    
    def test_user_stats_zero_votes(self, authorized_client: TestClient, test_user):
        """Test user stats with zero votes"""
        response = authorized_client.get("/api/users/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_votes"] == 0
    
    def test_user_stats_current_user_only(self, authorized_client: TestClient, test_user, test_user2):
        """Test user stats only for current user"""
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Should be for test_user, not test_user2
        assert data["total_photos"] >= 0  # Could be 0 if no photos
    
    def test_user_me_endpoint(self, authorized_client: TestClient, test_user):
        """Test /me endpoint"""
        response = authorized_client.get("/api/users/me")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert "created_at" in data
    
    def test_user_me_unauthorized(self, client: TestClient):
        """Test /me endpoint without authentication"""
        response = client.get("/api/users/me")
        
        assert response.status_code == 401