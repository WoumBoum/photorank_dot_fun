#!/usr/bin/env python3
"""
Complete test suite for PhotoRank voting system and leaderboard
Tests ELO calculations, voting endpoints, and leaderboard functionality
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Photo, Vote, User
from app.routers.votes import calculate_elo_change


class TestCompleteVotingSystem:
    """Complete integration tests for voting system and leaderboard"""
    
    def test_elo_calculation_accuracy(self):
        """Test ELO calculation accuracy with known values"""
        # Test case 1: Equal ratings
        winner_change, loser_change = calculate_elo_change(1200, 1200)
        assert abs(winner_change - 16.0) < 0.1
        assert abs(loser_change + 16.0) < 0.1
        
        # Test case 2: Favorite wins (1400 vs 1200)
        winner_change, loser_change = calculate_elo_change(1400, 1200)
        assert 0 < winner_change < 16
        assert -16 < loser_change < 0
        
        # Test case 3: Underdog wins (1200 vs 1400)
        winner_change, loser_change = calculate_elo_change(1200, 1400)
        assert winner_change > 16
        assert loser_change < -16
        
        # Test case 4: Extreme difference
        winner_change, loser_change = calculate_elo_change(1000, 2000)
        assert abs(winner_change - 31.9) < 0.1
        assert abs(loser_change + 31.9) < 0.1
    
    def test_voting_flow_complete(self, authorized_client: TestClient, session: Session):
        """Test complete voting flow from start to finish"""
        # Create test users
        user1 = User(email="test1@example.com", username="user1", provider="github", provider_id="1")
        user2 = User(email="test2@example.com", username="user2", provider="github", provider_id="2")
        session.add_all([user1, user2])
        session.commit()
        
        # Create test photos
        photo1 = Photo(filename="test1.jpg", owner_id=user1.id, elo_rating=1200, total_duels=0, wins=0)
        photo2 = Photo(filename="test2.jpg", owner_id=user2.id, elo_rating=1200, total_duels=0, wins=0)
        session.add_all([photo1, photo2])
        session.commit()
        
        # Record initial ratings
        initial_elo1 = photo1.elo_rating
        initial_elo2 = photo2.elo_rating
        
        # Submit vote
        vote_data = {
            "winner_id": photo1.id,
            "loser_id": photo2.id
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        assert response.status_code == 200
        
        # Verify ELO changes
        session.refresh(photo1)
        session.refresh(photo2)
        
        assert photo1.elo_rating > initial_elo1
        assert photo2.elo_rating < initial_elo2
        assert photo1.total_duels == 1
        assert photo2.total_duels == 1
        assert photo1.wins == 1
        assert photo2.wins == 0
    
    def test_leaderboard_eligibility(self, authorized_client: TestClient, session: Session):
        """Test leaderboard eligibility (50+ duels requirement)"""
        # Create test user
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        # Create photos with different duel counts
        eligible_photo = Photo(
            filename="eligible.jpg", 
            owner_id=user.id, 
            elo_rating=1300, 
            total_duels=50, 
            wins=30
        )
        ineligible_photo = Photo(
            filename="ineligible.jpg", 
            owner_id=user.id, 
            elo_rating=1400, 
            total_duels=49, 
            wins=35
        )
        session.add_all([eligible_photo, ineligible_photo])
        session.commit()
        
        # Test leaderboard
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        
        # Should only include eligible photo
        assert len(leaderboard) == 1
        assert leaderboard[0]["filename"] == "eligible.jpg"
        assert leaderboard[0]["elo_rating"] == 1300
    
    def test_leaderboard_ordering(self, authorized_client: TestClient, session: Session):
        """Test leaderboard ordering by ELO rating"""
        # Create test user
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        # Create photos with different ELO ratings
        photos = [
            Photo(filename="low.jpg", owner_id=user.id, elo_rating=1100, total_duels=50, wins=25),
            Photo(filename="medium.jpg", owner_id=user.id, elo_rating=1200, total_duels=50, wins=30),
            Photo(filename="high.jpg", owner_id=user.id, elo_rating=1300, total_duels=50, wins=35),
        ]
        session.add_all(photos)
        session.commit()
        
        # Test leaderboard ordering
        response = authorized_client.get("/api/photos/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        
        # Should be ordered by ELO descending
        assert len(leaderboard) == 3
        assert leaderboard[0]["elo_rating"] == 1300
        assert leaderboard[1]["elo_rating"] == 1200
        assert leaderboard[2]["elo_rating"] == 1100
    
    def test_multiple_votes_accuracy(self, authorized_client: TestClient, session: Session):
        """Test accuracy with multiple votes"""
        # Create test users and photos
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        photos = []
        for i in range(3):
            photo = Photo(
                filename=f"photo{i}.jpg", 
                owner_id=user.id, 
                elo_rating=1200, 
                total_duels=0, 
                wins=0
            )
            session.add(photo)
            session.flush()
            photos.append(photo)
        session.commit()
        
        # Submit multiple votes
        votes_data = [
            {"winner_id": photos[0].id, "loser_id": photos[1].id},
            {"winner_id": photos[1].id, "loser_id": photos[2].id},
            {"winner_id": photos[0].id, "loser_id": photos[2].id},
        ]
        
        for vote_data in votes_data:
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
        
        # Verify final state
        session.refresh(photos[0])
        session.refresh(photos[1])
        session.refresh(photos[2])
        
        assert photos[0].total_duels == 2  # Won twice
        assert photos[0].wins == 2
        assert photos[1].total_duels == 2  # Won once, lost once
        assert photos[1].wins == 1
        assert photos[2].total_duels == 2  # Lost twice
        assert photos[2].wins == 0
    
    def test_duplicate_vote_prevention(self, authorized_client: TestClient, session: Session):
        """Test prevention of duplicate votes"""
        # Create test user and photos
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        photo1 = Photo(filename="photo1.jpg", owner_id=user.id, elo_rating=1200, total_duels=0, wins=0)
        photo2 = Photo(filename="photo2.jpg", owner_id=user.id, elo_rating=1200, total_duels=0, wins=0)
        session.add_all([photo1, photo2])
        session.commit()
        
        vote_data = {
            "winner_id": photo1.id,
            "loser_id": photo2.id
        }
        
        # First vote should succeed
        response1 = authorized_client.post("/api/votes/", json=vote_data)
        assert response1.status_code == 200
        
        # Second vote should fail
        response2 = authorized_client.post("/api/votes/", json=vote_data)
        assert response2.status_code == 400
        assert "Already voted on this pair" in response2.json()["detail"]
    
    def test_reverse_votes_allowed(self, authorized_client: TestClient, session: Session):
        """Test that reverse votes (A>B then B>A) are allowed"""
        # Create test user and photos
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        photo1 = Photo(filename="photo1.jpg", owner_id=user.id, elo_rating=1200, total_duels=0, wins=0)
        photo2 = Photo(filename="photo2.jpg", owner_id=user.id, elo_rating=1200, total_duels=0, wins=0)
        session.add_all([photo1, photo2])
        session.commit()
        
        # Vote A > B
        vote1 = {"winner_id": photo1.id, "loser_id": photo2.id}
        response1 = authorized_client.post("/api/votes/", json=vote1)
        assert response1.status_code == 200
        
        # Vote B > A (reverse)
        vote2 = {"winner_id": photo2.id, "loser_id": photo1.id}
        response2 = authorized_client.post("/api/votes/", json=vote2)
        assert response2.status_code == 200
    
    def test_leaderboard_limit_parameter(self, authorized_client: TestClient, session: Session):
        """Test leaderboard limit parameter"""
        # Create test user
        user = User(email="test@example.com", username="testuser", provider="github", provider_id="123")
        session.add(user)
        session.commit()
        
        # Create 5 photos
        photos = []
        for i in range(5):
            photo = Photo(
                filename=f"photo{i}.jpg", 
                owner_id=user.id, 
                elo_rating=1200 + i * 10, 
                total_duels=50, 
                wins=25 + i
            )
            session.add(photo)
            session.flush()
            photos.append(photo)
        session.commit()
        
        # Test different limits
        for limit in [1, 3, 5, 10]:
            response = authorized_client.get(f"/api/photos/leaderboard?limit={limit}")
            assert response.status_code == 200
            leaderboard = response.json()
            expected_length = min(limit, 5)
            assert len(leaderboard) == expected_length
    
    def test_edge_cases(self, authorized_client: TestClient, session: Session):
        """Test edge cases"""
        # Test zero limit
        response = authorized_client.get("/api/photos/leaderboard?limit=0")
        assert response.status_code == 200
        assert response.json() == []
        
        # Test large limit
        response = authorized_client.get("/api/photos/leaderboard?limit=1000")
        assert response.status_code == 200
        assert len(response.json()) >= 0  # Should not crash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])