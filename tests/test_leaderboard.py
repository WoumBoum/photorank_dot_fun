import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Photo, User


class TestLeaderboard:
    """Test leaderboard and ranking system"""
    
    def test_get_leaderboard_basic(self, authorized_client: TestClient, test_photos):
        """Test basic leaderboard retrieval"""
        response = authorized_client.get("/api/photos/leaderboard")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Should only include photos with >= 50 duels
        eligible_photos = [p for p in test_photos if p.total_duels >= 50]
        assert len(data) == len(eligible_photos)
    
    def test_leaderboard_ordering(self, authorized_client: TestClient, session: Session):
        """Test leaderboard is ordered by ELO rating"""
        # Create photos with specific ELO ratings
        users = session.query(User).all()
        photos_data = [
            {"filename": "low.jpg", "elo_rating": 1100, "total_duels": 60, "wins": 30, "owner_id": users[0].id},
            {"filename": "medium.jpg", "elo_rating": 1200, "total_duels": 60, "wins": 35, "owner_id": users[0].id},
            {"filename": "high.jpg", "elo_rating": 1300, "total_duels": 60, "wins": 40, "owner_id": users[1].id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        # Should be ordered by ELO descending
        elos = [p["elo_rating"] for p in data]
        assert elos == sorted(elos, reverse=True)
    
    def test_leaderboard_limit_parameter(self, authorized_client: TestClient, session: Session):
        """Test leaderboard limit parameter"""
        # Create many photos
        user = session.query(User).first()
        for i in range(10):
            photo = Photo(
                filename=f"photo{i}.jpg",
                elo_rating=1200 + i * 10,
                total_duels=60,
                wins=30 + i,
                owner_id=user.id
            )
            session.add(photo)
        session.commit()
        
        # Test limit parameter
        response = authorized_client.get("/api/photos/leaderboard?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
    
    def test_leaderboard_excludes_insufficient_duels(self, authorized_client: TestClient, session: Session):
        """Test leaderboard excludes photos with < 50 duels"""
        user = session.query(User).first()
        
        # Create photos with different duel counts
        photos_data = [
            {"filename": "eligible.jpg", "elo_rating": 1200, "total_duels": 50, "wins": 25, "owner_id": user.id},
            {"filename": "not_eligible.jpg", "elo_rating": 1300, "total_duels": 49, "wins": 30, "owner_id": user.id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        # Should only include the eligible photo
        assert len(data) == 1
        assert data[0]["filename"] == "eligible.jpg"
    
    def test_leaderboard_ranking(self, authorized_client: TestClient, session: Session):
        """Test leaderboard ranking positions"""
        user = session.query(User).first()
        
        photos_data = [
            {"filename": "rank1.jpg", "elo_rating": 1400, "total_duels": 60, "wins": 45, "owner_id": user.id},
            {"filename": "rank2.jpg", "elo_rating": 1300, "total_duels": 60, "wins": 40, "owner_id": user.id},
            {"filename": "rank3.jpg", "elo_rating": 1200, "total_duels": 60, "wins": 35, "owner_id": user.id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        # Check ranking
        assert data[0]["filename"] == "rank1.jpg"
        assert data[1]["filename"] == "rank2.jpg"
        assert data[2]["filename"] == "rank3.jpg"
    
    def test_leaderboard_includes_owner_username(self, authorized_client: TestClient, test_photos):
        """Test leaderboard includes owner username"""
        # Ensure at least one photo has enough duels
        session = next(get_db())
        photo = session.query(Photo).first()
        photo.total_duels = 60
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        if data:
            assert "owner_username" in data[0]
            assert data[0]["owner_username"] is not None
    
    def test_leaderboard_empty(self, authorized_client: TestClient):
        """Test empty leaderboard"""
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    def test_leaderboard_with_ties(self, authorized_client: TestClient, session: Session):
        """Test leaderboard handling of tied ELO ratings"""
        user = session.query(User).first()
        
        # Create photos with same ELO
        photos_data = [
            {"filename": "tie1.jpg", "elo_rating": 1200, "total_duels": 60, "wins": 30, "owner_id": user.id},
            {"filename": "tie2.jpg", "elo_rating": 1200, "total_duels": 60, "wins": 30, "owner_id": user.id},
        ]
        
        for photo_data in photos_data:
            photo = Photo(**photo_data)
            session.add(photo)
        session.commit()
        
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        # Both should have same ELO but different positions
        assert data[0]["elo_rating"] == data[1]["elo_rating"] == 1200
    
    def test_leaderboard_pagination(self, authorized_client: TestClient, session: Session):
        """Test leaderboard pagination"""
        user = session.query(User).first()
        
        # Create 20 photos
        for i in range(20):
            photo = Photo(
                filename=f"photo{i}.jpg",
                elo_rating=1200 + i,
                total_duels=60,
                wins=30 + i,
                owner_id=user.id
            )
            session.add(photo)
        session.commit()
        
        # Test different limits
        for limit in [1, 5, 10, 100]:
            response = authorized_client.get(f"/api/photos/leaderboard?limit={limit}")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == min(limit, 20)
    
    def test_leaderboard_negative_limit(self, authorized_client: TestClient):
        """Test leaderboard with negative limit"""
        response = authorized_client.get("/api/photos/leaderboard?limit=-1")
        assert response.status_code == 422  # Validation error
    
    def test_leaderboard_zero_limit(self, authorized_client: TestClient):
        """Test leaderboard with zero limit"""
        response = authorized_client.get("/api/photos/leaderboard?limit=0")
        assert response.status_code == 200
        data = response.json()
        assert data == []


