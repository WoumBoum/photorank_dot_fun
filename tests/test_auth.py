import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import User


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_create_user(self, client: TestClient, session: Session):
        """Test user creation via OAuth simulation"""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "provider": "github",
            "provider_id": "999999"
        }
        
        # Simulate user creation (normally done via OAuth)
        user = User(**user_data)
        session.add(user)
        session.commit()
        session.refresh(user)
        
        assert user.email == user_data["email"]
        assert user.username == user_data["username"]
        assert user.provider == "github"
        assert user.provider_id == "999999"
        assert user.id is not None
        assert user.created_at is not None
    
    def test_jwt_token_creation(self, test_user):
        """Test JWT token generation"""
        from app.oauth2 import create_access_token
        
        token = create_access_token({"user_id": test_user.id})
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_jwt_token_verification(self, test_user):
        """Test JWT token verification"""
        from app.oauth2 import verify_access_token, create_access_token
        from fastapi import HTTPException
        
        token = create_access_token({"user_id": test_user.id})
        user_id = verify_access_token(token, HTTPException(status_code=401))
        assert user_id == test_user.id
    
    def test_invalid_token(self):
        """Test invalid JWT token handling"""
        from app.oauth2 import verify_access_token
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException):
            verify_access_token("invalid_token", HTTPException(status_code=401))
    
    def test_expired_token(self):
        """Test expired JWT token handling"""
        from app.oauth2 import create_access_token, verify_access_token
        from fastapi import HTTPException
        from datetime import datetime, timedelta
        
        # Create token with negative expiration
        payload = {"user_id": 1, "exp": datetime.utcnow() - timedelta(hours=1)}
        import jwt
        expired_token = jwt.encode(payload, "test_secret", algorithm="HS256")
        
        with pytest.raises(HTTPException):
            verify_access_token(expired_token, HTTPException(status_code=401))
    
    def test_get_current_user(self, authorized_client: TestClient, test_user):
        """Test getting current authenticated user"""
        response = authorized_client.get("/api/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
    
    def test_unauthorized_access(self, client: TestClient):
        """Test unauthorized access to protected endpoints"""
        response = client.get("/api/users/me")
        assert response.status_code == 401
    
    def test_user_uniqueness(self, session: Session):
        """Test user uniqueness constraints"""
        user1 = User(
            email="unique@example.com",
            username="uniqueuser",
            provider="github",
            provider_id="111111"
        )
        session.add(user1)
        session.commit()
        
        # Try to create duplicate
        user2 = User(
            email="unique@example.com",  # Same email
            username="uniqueuser2",
            provider="google",
            provider_id="222222"
        )
        session.add(user2)
        
        with pytest.raises(Exception):  # Should violate unique constraint
            session.commit()
    
    def test_provider_id_uniqueness(self, session: Session):
        """Test provider_id uniqueness"""
        user1 = User(
            email="test1@example.com",
            username="test1",
            provider="github",
            provider_id="333333"
        )
        session.add(user1)
        session.commit()
        
        user2 = User(
            email="test2@example.com",
            username="test2",
            provider="github",
            provider_id="333333"  # Same provider_id
        )
        session.add(user2)
        
        with pytest.raises(Exception):  # Should violate unique constraint
            session.commit()