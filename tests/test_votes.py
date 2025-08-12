import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import Vote, Photo


class TestEloAlgorithm:
    """Test ELO rating algorithm calculations"""
    
    def test_elo_calculation_equal_ratings(self):
        """Test ELO calculation with equal ratings"""
        from app.routers.votes import calculate_elo_change
        
        winner_change, loser_change = calculate_elo_change(1200, 1200)
        
        # When ratings are equal, winner gets +16, loser gets -16
        assert winner_change == 16.0
        assert loser_change == -16.0
    
    def test_elo_calculation_favorite_wins(self):
        """Test ELO calculation when favorite wins"""
        from app.routers.votes import calculate_elo_change
        
        # Higher rated player wins
        winner_change, loser_change = calculate_elo_change(1400, 1200)
        
        # Favorite wins, smaller rating change
        assert 0 < winner_change < 16
        assert -16 < loser_change < 0
    
    def test_elo_calculation_underdog_wins(self):
        """Test ELO calculation when underdog wins"""
        from app.routers.votes import calculate_elo_change
        
        # Lower rated player wins
        winner_change, loser_change = calculate_elo_change(1200, 1400)
        
        # Underdog wins, larger rating change
        assert winner_change > 16
        assert loser_change < -16
    
    def test_elo_calculation_extreme_ratings(self):
        """Test ELO calculation with extreme rating differences"""
        from app.routers.votes import calculate_elo_change
        
        # Very large rating difference
        winner_change, loser_change = calculate_elo_change(1000, 2000)
        
        # Maximum possible change when underdog wins
        assert winner_change > 30  # Close to K_FACTOR
        assert loser_change < -30


class TestVotingSystem:
    """Test voting system and duel mechanics"""
    
    def test_create_vote_success(self, authorized_client: TestClient, test_photos):
        """Test successful vote creation"""
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["winner_id"] == test_photos[0].id
        assert data["loser_id"] == test_photos[1].id
    
    def test_vote_updates_elo_ratings(self, authorized_client: TestClient, test_photos, session: Session):
        """Test that voting updates ELO ratings"""
        initial_winner_elo = test_photos[0].elo_rating
        initial_loser_elo = test_photos[1].elo_rating
        
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        assert response.status_code == 200
        
        # Refresh from database
        session.refresh(test_photos[0])
        session.refresh(test_photos[1])
        
        assert test_photos[0].elo_rating > initial_winner_elo
        assert test_photos[1].elo_rating < initial_loser_elo
    
    def test_vote_increments_duel_counts(self, authorized_client: TestClient, test_photos, session: Session):
        """Test that voting increments duel counts"""
        initial_winner_duels = test_photos[0].total_duels
        initial_loser_duels = test_photos[1].total_duels
        initial_winner_wins = test_photos[0].wins
        
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        assert response.status_code == 200
        
        # Refresh from database
        session.refresh(test_photos[0])
        session.refresh(test_photos[1])
        
        assert test_photos[0].total_duels == initial_winner_duels + 1
        assert test_photos[1].total_duels == initial_loser_duels + 1
        assert test_photos[0].wins == initial_winner_wins + 1
    
    def test_vote_same_photo_error(self, authorized_client: TestClient, test_photos):
        """Test voting for same photo error"""
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[0].id
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        
        assert response.status_code == 400
        assert "Cannot vote for same photo" in response.json()["detail"]
    
    def test_vote_nonexistent_photo(self, authorized_client: TestClient):
        """Test voting for non-existent photo"""
        vote_data = {
            "winner_id": 99999,
            "loser_id": 88888
        }
        
        response = authorized_client.post("/api/votes/", json=vote_data)
        
        assert response.status_code == 404
        assert "Photo not found" in response.json()["detail"]
    
    def test_duplicate_vote_prevention(self, authorized_client: TestClient, test_photos):
        """Test preventing duplicate votes on same pair"""
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        # First vote
        response1 = authorized_client.post("/api/votes/", json=vote_data)
        assert response1.status_code == 200
        
        # Second vote on same pair
        response2 = authorized_client.post("/api/votes/", json=vote_data)
        assert response2.status_code == 400
        assert "Already voted on this pair" in response2.json()["detail"]
    
    def test_reverse_vote_allowed(self, authorized_client: TestClient, test_photos):
        """Test that reverse vote (A>B then B>A) is allowed"""
        # Vote A > B
        vote1 = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        response1 = authorized_client.post("/api/votes/", json=vote1)
        assert response1.status_code == 200
        
        # Vote B > A (reverse)
        vote2 = {
            "winner_id": test_photos[1].id,
            "loser_id": test_photos[0].id
        }
        response2 = authorized_client.post("/api/votes/", json=vote2)
        assert response2.status_code == 200
    
    def test_vote_without_auth(self, client: TestClient, test_photos):
        """Test voting without authentication"""
        vote_data = {
            "winner_id": test_photos[0].id,
            "loser_id": test_photos[1].id
        }
        
        response = client.post("/api/votes/", json=vote_data)
        
        assert response.status_code == 401
    
    def test_multiple_votes_accuracy(self, authorized_client: TestClient, test_photos, session: Session):
        """Test accuracy of multiple votes"""
        # Record initial ratings
        initial_ratings = [(p.elo_rating, p.total_duels, p.wins) for p in test_photos]
        
        # Create multiple votes
        votes_data = [
            {"winner_id": test_photos[0].id, "loser_id": test_photos[1].id},
            {"winner_id": test_photos[2].id, "loser_id": test_photos[3].id},
            {"winner_id": test_photos[0].id, "loser_id": test_photos[2].id},
        ]
        
        for vote_data in votes_data:
            response = authorized_client.post("/api/votes/", json=vote_data)
            assert response.status_code == 200
        
        # Verify all photos have correct counts
        for i, photo in enumerate(test_photos):
            session.refresh(photo)
            
        # Check specific photo updates
        assert test_photos[0].total_duels == 2  # Won twice
        assert test_photos[0].wins == 2
        assert test_photos[1].total_duels == 1  # Lost once
        assert test_photos[1].wins == 0


class TestVoteStats:
    """Test vote statistics"""
    
    def test_get_vote_stats(self, authorized_client: TestClient, test_votes, test_user):
        """Test getting vote statistics"""
        response = authorized_client.get("/api/votes/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_votes"] == 2  # From test_votes fixture
    
    def test_get_vote_stats_empty(self, authorized_client: TestClient, test_user):
        """Test getting vote statistics for user with no votes"""
        response = authorized_client.get("/api/votes/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_votes"] == 0