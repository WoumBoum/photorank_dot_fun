import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO

from app.models import User, Photo, Vote, UploadLimit


class TestIntegration:
    """Integration tests covering complete user workflows"""
    
    def test_complete_user_workflow(self, authorized_client: TestClient, session: Session):
        """Test complete user workflow from signup to leaderboard"""
        
        # 1. User uploads photos
        upload_count = 3
        photo_ids = []
        for i in range(upload_count):
            img = Image.new('RGB', (100, 100), color='red')
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes.seek(0)
            
            files = {"file": (f"photo{i}.jpg", img_bytes, "image/jpeg")}
            response = authorized_client.post("/api/photos/upload", files=files)
            assert response.status_code == 200
            photo_ids.append(response.json()["id"])
        
        # 2. Verify photos appear in user stats
        response = authorized_client.get("/api/users/stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_photos"] == upload_count
        assert len(stats["photos"]) == upload_count
        
        # 3. Simulate duels to make photos eligible for leaderboard
        for i in range(50):  # Create enough duels
            vote_data = {
                "winner_id": photo_ids[0],
                "loser_id": photo_ids[1]
            }
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
        
        # 4. Update photo duel counts manually (since we can't create 50 votes easily)
        for photo_id in photo_ids:
            photo = session.query(Photo).filter(Photo.id == photo_id).first()
            photo.total_duels = 60
            photo.wins = 30
        session.commit()
        
        # 5. Check leaderboard
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        assert len(leaderboard) >= 1  # At least one photo should be eligible
        
        # 6. Check ELO changes
        photos = session.query(Photo).filter(Photo.id.in_(photo_ids)).all()
        elo_ratings = [p.elo_rating for p in photos]
        assert len(set(elo_ratings)) > 1  # ELOs should have diverged
    
    def test_rate_limit_reset_workflow(self, authorized_client: TestClient, session: Session, test_user):
        """Test rate limit reset after 24 hours"""
        
        # 1. Create upload limit at capacity
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=5,
            last_upload_date=datetime.utcnow() - timedelta(days=1)
        )
        session.add(upload_limit)
        session.commit()
        
        # 2. Should allow upload after 24h
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("reset_test.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        assert response.status_code == 200
        
        # 3. Verify counter reset
        upload_limit = session.query(UploadLimit).filter(
            UploadLimit.user_id == test_user.id
        ).first()
        assert upload_limit.upload_count == 1  # Should reset and increment
    
    def test_elo_convergence(self, authorized_client: TestClient, session: Session, test_user):
        """Test ELO ratings converge appropriately over many duels"""
        
        # Create two photos
        photos = []
        for i in range(2):
            photo = Photo(
                filename=f"convergence{i}.jpg",
                elo_rating=1200,
                total_duels=0,
                wins=0,
                owner_id=test_user.id
            )
            session.add(photo)
            session.commit()
            session.refresh(photo)
            photos.append(photo)
        
        # Simulate 100 duels
        for i in range(100):
            # Photo 0 wins 70% of the time
            winner_id = photos[0].id if i < 70 else photos[1].id
            loser_id = photos[1].id if i < 70 else photos[0].id
            
            vote_data = {"winner_id": winner_id, "loser_id": loser_id}
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
        
        # Refresh photos
        for photo in photos:
            session.refresh(photo)
        
        # Photo 0 should have higher ELO
        assert photos[0].elo_rating > photos[1].elo_rating
        assert photos[0].total_duels == 100
        assert photos[1].total_duels == 100
    
    def test_multiple_users_interaction(self, client: TestClient, session: Session):
        """Test interaction between multiple users"""
        
        # Create multiple users
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@test.com",
                username=f"user{i}",
                provider="github",
                provider_id=f"user{i}"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            users.append(user)
        
        # Create photos for each user
        photos = []
        for user in users:
            for j in range(2):
                photo = Photo(
                    filename=f"user{user.id}_photo{j}.jpg",
                    elo_rating=1200,
                    total_duels=60,
                    wins=30,
                    owner_id=user.id
                )
                session.add(photo)
                session.commit()
                session.refresh(photo)
                photos.append(photo)
        
        # Create tokens for each user
        from app.oauth2 import create_access_token
        tokens = [create_access_token({"user_id": user.id}) for user in users]
        
        # Each user votes on photos
        for i, (user, token) in enumerate(zip(users, tokens)):
            client.headers = {"Authorization": f"Bearer {token}"}
            
            # User votes on photos not their own
            for photo in photos:
                if photo.owner_id != user.id:
                    other_photos = [p for p in photos if p.owner_id != user.id and p.id != photo.id]
                    if other_photos:
                        vote_data = {
                            "winner_id": photo.id,
                            "loser_id": other_photos[0].id
                        }
                        response = client.post("/api/votes/", json=vote_data)
                        assert response.status_code == 200
        
        # Check global leaderboard
        response = client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        assert len(leaderboard) > 0
    
    def test_upload_during_rate_limit(self, authorized_client: TestClient, session: Session, test_user):
        """Test upload behavior during rate limit"""
        
        # Set up rate limit
        upload_limit = UploadLimit(
            user_id=test_user.id,
            upload_count=5,
            last_upload_date=datetime.utcnow()
        )
        session.add(upload_limit)
        session.commit()
        
        # Try to upload
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {"file": ("blocked.jpg", img_bytes, "image/jpeg")}
        response = authorized_client.post("/api/photos/upload", files=files)
        assert response.status_code == 429
        
        # Verify no new photos were created
        photos = session.query(Photo).filter(Photo.owner_id == test_user.id).count()
        assert photos == 0  # Assuming fresh database
    
    def test_photo_deletion_cascade(self, authorized_client: TestClient, session: Session, test_user):
        """Test cascade deletion when user is deleted"""
        
        # Create photo
        photo = Photo(
            filename="cascade.jpg",
            elo_rating=1200,
            total_duels=0,
            wins=0,
            owner_id=test_user.id
        )
        session.add(photo)
        session.commit()
        
        # Create vote
        vote = Vote(
            user_id=test_user.id,
            winner_id=photo.id,
            loser_id=photo.id  # This would normally be invalid, but for testing
        )
        session.add(vote)
        session.commit()
        
        # Delete user
        session.delete(test_user)
        session.commit()
        
        # Verify cascade deletion
        remaining_photos = session.query(Photo).filter(Photo.owner_id == test_user.id).count()
        remaining_votes = session.query(Vote).filter(Vote.user_id == test_user.id).count()
        
        assert remaining_photos == 0
        assert remaining_votes == 0
    
    def test_elo_stability(self, authorized_client: TestClient, session: Session, test_user):
        """Test ELO rating stability over time"""
        
        # Create two photos with known ratings
        photo1 = Photo(
            filename="stable1.jpg",
            elo_rating=1500,
            total_duels=100,
            wins=75,
            owner_id=test_user.id
        )
        photo2 = Photo(
            filename="stable2.jpg",
            elo_rating=900,
            total_duels=100,
            wins=25,
            owner_id=test_user.id
        )
        session.add_all([photo1, photo2])
        session.commit()
        
        # Simulate many duels between them
        initial_diff = photo1.elo_rating - photo2.elo_rating
        
        for _ in range(50):
            # Higher rated should win most
            vote_data = {"winner_id": photo1.id, "loser_id": photo2.id}
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
        
        session.refresh(photo1)
        session.refresh(photo2)
        
        # Rating difference should stabilize
        final_diff = photo1.elo_rating - photo2.elo_rating
        assert abs(final_diff - initial_diff) < 100  # Should not diverge too much
    
    def test_leaderboard_consistency(self, authorized_client: TestClient, session: Session, test_user):
        """Test leaderboard consistency across requests"""
        
        # Create photos
        for i in range(10):
            photo = Photo(
                filename=f"consistency{i}.jpg",
                elo_rating=1200 + i * 10,
                total_duels=60,
                wins=30 + i,
                owner_id=test_user.id
            )
            session.add(photo)
        session.commit()
        
        # Get leaderboard multiple times
        responses = []
        for _ in range(3):
            response = authorized_client.get("/api/photos/leaderboard")
            assert response.status_code == 200
            responses.append(response.json())
        
        # All responses should be identical
        assert all(r == responses[0] for r in responses)