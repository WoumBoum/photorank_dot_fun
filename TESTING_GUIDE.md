# PhotoRank Testing Guide

This guide provides comprehensive instructions for testing the PhotoRank application. It covers setup, running tests, troubleshooting, and best practices for future agents.

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Activate virtual environment
cd /home/walid/Documents/PROJ/photorank_dot_fun
. venv/bin/activate

# Install test dependencies
pip install pytest Pillow

# Ensure test database exists
docker exec photorank_nv_depart-db-1 psql -U postgres -c "CREATE DATABASE fastapi_test;"

# Set up test database schema
python -c "
from tests.conftest import engine
from app.database import Base
Base.metadata.create_all(bind=engine)
print('Test database schema created')
"
```

### 2. Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_auth.py -v

# Run specific test
python -m pytest tests/test_auth.py::TestAuthentication::test_get_current_user -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## 🧪 Test Structure

### Test Files
- `tests/test_auth.py` - Authentication and JWT tests
- `tests/test_photos.py` - Photo upload and retrieval tests
- `tests/test_votes.py` - Voting and ELO algorithm tests
- `tests/test_leaderboard.py` - Leaderboard functionality
- `tests/test_user_stats.py` - User statistics and dashboard
- `tests/test_edge_cases.py` - Edge cases and error handling
- `tests/test_integration.py` - Complete user workflows
- `tests/test_categories_moderation.py` - Category management
- `tests/test_batch_upload.py` - Batch upload functionality

### Key Fixtures (tests/conftest.py)
- `db_engine` - Database engine with test schema
- `session` - Database session with transaction rollback
- `client` - TestClient with proper host configuration
- `test_user`, `test_user2` - Test user accounts
- `test_category` - Test category for photo categorization
- `test_photos` - Test photos with proper category associations
- `authorized_client` - Authenticated test client

## ⚠️ Common Issues & Solutions

### 1. Database Schema Mismatch
**Problem**: Tests fail with column missing errors
**Solution**: Ensure test database has latest schema:
```bash
python -c "
from tests.conftest import engine
from app.database import Base
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print('Test database schema refreshed')
"
```

### 2. Host Header Errors
**Problem**: `400 Invalid host header` errors
**Solution**: TestClient must use proper base_url:
```python
# In conftest.py
TestClient(app, base_url="http://localhost")
```

### 3. Category Requirements
**Problem**: Photos require category_id (NOT NULL constraint)
**Solution**: All test photos must include category_id:
```python
# Updated test_photos fixture includes category_id
photos_data = [
    {
        "filename": "photo1.jpg",
        "elo_rating": 1200.0,
        "total_duels": 0,
        "wins": 0,
        "owner_id": test_user.id,
        "category_id": test_category.id  # Required
    }
]
```

### 4. Session-Based Uploads
**Problem**: Upload endpoints return 405 Method Not Allowed
**Solution**: Use session-based endpoints:
- Old: `/api/photos/upload`
- New: `/api/photos/upload/session`

## 🔧 Test Configuration

### Database Configuration
Test database uses separate connection string:
```python
# tests/conftest.py
SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}_test'
```

### Test Client Configuration
```python
# Proper TestClient configuration
test_client = TestClient(app, base_url="http://localhost")
test_client.headers.update({"host": "localhost"})
```

### Session Management
For session-based endpoints, ensure proper session handling:
```python
# Select category before testing uploads
response = client.post("/api/categories/1/select")
assert response.status_code == 200
```

## 🧪 Writing New Tests

### Basic Test Structure
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestNewFeature:
    def test_feature_basic(self, authorized_client: TestClient, test_user):
        """Test basic functionality"""
        response = authorized_client.get("/api/new-endpoint")
        assert response.status_code == 200
        assert response.json()["key"] == "expected_value"
    
    def test_feature_with_db(self, authorized_client: TestClient, session: Session):
        """Test with database interaction"""
        # Setup test data
        test_data = {"key": "value"}
        
        # Make request
        response = authorized_client.post("/api/new-endpoint", json=test_data)
        
        # Verify response
        assert response.status_code == 200
        
        # Verify database changes
        result = session.query(MyModel).filter(MyModel.key == "value").first()
        assert result is not None
```

### Testing Authentication
```python
def test_authentication_required(self, client: TestClient):
    """Test endpoint requires authentication"""
    response = client.get("/api/protected-endpoint")
    assert response.status_code == 401

def test_authorized_access(self, authorized_client: TestClient):
    """Test authenticated access"""
    response = authorized_client.get("/api/protected-endpoint")
    assert response.status_code == 200
```

### Testing Error Conditions
```python
def test_invalid_input(self, authorized_client: TestClient):
    """Test error handling for invalid input"""
    response = authorized_client.post("/api/endpoint", json={"invalid": "data"})
    assert response.status_code == 400
    assert "error" in response.json()

def test_not_found(self, authorized_client: TestClient):
    """Test 404 handling"""
    response = authorized_client.get("/api/nonexistent-endpoint")
    assert response.status_code == 404
```

## 📊 Test Coverage

### Running Coverage Reports
```bash
# Generate HTML coverage report
python -m pytest tests/ --cov=app --cov-report=html

# View coverage in terminal
python -m pytest tests/ --cov=app --cov-report=term-missing

# Minimum coverage requirement
python -m pytest tests/ --cov=app --cov-fail-under=80
```

### Coverage Targets
- **80%+** overall coverage
- **90%+** for core functionality (auth, photos, votes)
- **70%+** for edge cases and error handling
- **100%** for critical security features

## 🐛 Debugging Tests

### Common Debugging Techniques

1. **Verbose Output**: Use `-v` flag for detailed test output
2. **PDB Debugging**: Add `import pdb; pdb.set_trace()` to pause execution
3. **Response Inspection**: Print response details for debugging:
   ```python
   print(f"Status: {response.status_code}")
   print(f"Response: {response.text}")
   ```

### Database Debugging
```python
# Check database state during tests
def test_debug_db_state(self, session: Session):
    users = session.query(User).all()
    print(f"Users in DB: {len(users)}")
    for user in users:
        print(f"User: {user.username}, Email: {user.email}")
```

### Network Debugging
```python
# Inspect request/response details
def test_debug_network(self, authorized_client: TestClient):
    response = authorized_client.get("/api/endpoint")
    print(f"Request headers: {dict(response.request.headers)}")
    print(f"Response headers: {dict(response.headers)}")
    print(f"Response body: {response.text}")
```

## 🔄 Continuous Integration

### GitHub Actions Setup
```yaml
name: PhotoRank Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres
        env:
          POSTGRES_PASSWORD: pepito1234
          POSTGRES_DB: fastapi_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest Pillow
    
    - name: Run tests
      env:
        DATABASE_HOSTNAME: localhost
        DATABASE_PORT: 5432
        DATABASE_USERNAME: postgres
        DATABASE_PASSWORD: pepito1234
        DATABASE_NAME: fastapi_test
      run: |
        python -m pytest tests/ -v --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Local CI Simulation
```bash
# Run tests in isolated environment
docker-compose -f docker-compose-dev.yml run --rm api \
  sh -c "pip install pytest Pillow && python -m pytest tests/ -v"
```

## 📝 Best Practices

### 1. Test Isolation
- Each test should be independent
- Use database transactions that roll back after each test
- Clean up any external resources (files, temp directories)

### 2. Test Data Management
- Use fixtures for reusable test data
- Avoid hardcoded values where possible
- Clean up test data after tests

### 3. Assertion Quality
- Use specific assertions rather than generic ones
- Test both success and failure cases
- Verify database state changes where appropriate

### 4. Performance Considerations
- Keep tests fast and efficient
- Avoid unnecessary database operations
- Use mocking for external services

### 5. Security Testing
- Always test authentication and authorization
- Test rate limiting and input validation
- Verify proper error handling for security-sensitive operations

## 🆘 Troubleshooting

### Common Error Messages

1. **"database does not exist"**: Create test database first
2. **"Invalid host header"**: Configure TestClient with proper base_url
3. **"NOT NULL constraint"**: Ensure all required fields are provided
4. **"405 Method Not Allowed"**: Check endpoint URL and HTTP method
5. **"JWT decode error"**: Verify token generation and secret key

### Database Issues
```bash
# Reset test database
docker exec photorank_nv_depart-db-1 psql -U postgres -c "DROP DATABASE IF EXISTS fastapi_test;"
docker exec photorank_nv_depart-db-1 psql -U postgres -c "CREATE DATABASE fastapi_test;"

# Recreate schema
python -c "
from tests.conftest import engine
from app.database import Base
Base.metadata.create_all(bind=engine)
print('Test database reset')
"
```

### Dependency Issues
```bash
# Reinstall test dependencies
pip uninstall pytest Pillow
pip install pytest Pillow

# Check installed versions
pip list | grep -E "(pytest|Pillow)"
```

## 📞 Support

For additional help with testing:

1. Check existing test files for examples
2. Review FastAPI testing documentation
3. Examine the conftest.py for fixture patterns
4. Look at similar tests for the functionality you're testing

Remember: The test suite is designed to be comprehensive but maintainable. When in doubt, follow existing patterns and conventions.