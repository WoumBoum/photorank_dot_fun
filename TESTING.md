# PhotoRank Testing Guide

## Quick Verification

### Start Services
```bash
docker compose -f docker-compose-dev.yml up -d
```

### Test Core Features
```bash
# Basic functionality
python test_basic.py

# Full test suite
python run_tests.py

# With coverage
python run_tests.py --coverage
```

### Manual Testing
```bash
# Check endpoints
curl http://localhost:9001/api/photos/leaderboard
curl http://localhost:9001/api/photos/pair

# Check frontend
curl http://localhost:9001/
```

### Troubleshooting
```bash
# Check status
docker compose -f docker-compose-dev.yml ps

# View logs
docker compose -f docker-compose-dev.yml logs api

# Restart
docker compose -f docker-compose-dev.yml restart
```

## Test Coverage
- ✅ ELO algorithm calculations
- ✅ JWT authentication
- ✅ Rate limiting (5 uploads/day)
- ✅ Database models & relationships
- ✅ API endpoints
- ✅ OAuth integration
- ✅ Photo upload/delete
- ✅ Leaderboard filtering (≥50 duels)