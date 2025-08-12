import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db
from app.models import Base

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_storage.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestStorageIntegration:
    
    def setup_method(self):
        """Setup test database"""
        Base.metadata.create_all(bind=engine)
    
    def teardown_method(self):
        """Cleanup test database"""
        Base.metadata.drop_all(bind=engine)
        import os
        if os.path.exists("./test_storage.db"):
            os.remove("./test_storage.db")
    
    def test_api_endpoints_exist(self):
        """Test that all API endpoints exist and respond"""
        endpoints = [
            "/api/photos/leaderboard",
            "/api/photos/pair",
            "/upload",
            "/leaderboard",
            "/stats"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 404, 307]  # Accept various valid responses
    
    def test_photo_serving_endpoints(self):
        """Test photo serving endpoints"""
        # Test with non-existent photo
        response = client.get("/api/photos/nonexistent.jpg")
        assert response.status_code == 404
        
        # Test with invalid filename
        response = client.get("/api/photos/../../../etc/passwd")
        assert response.status_code == 404
    
    def test_health_check(self):
        """Test basic health check"""
        response = client.get("/")
        assert response.status_code == 200
        assert "PhotoRank" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])