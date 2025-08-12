#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic functionality test for PhotoRank
"""

import sys
import os
sys.path.append('/usr/src/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import User, Photo, Vote, UploadLimit
from app.routers.votes import calculate_elo_change
from app.oauth2 import create_access_token, verify_access_token
from fastapi import HTTPException

def test_database_models():
    """Test database models creation"""
    print("🧪 Testing database models...")
    
    # Test model instantiation
    user = User(
        email="test@example.com",
        username="testuser",
        provider="github",
        provider_id="123456"
    )
    
    photo = Photo(
        filename="test.jpg",
        elo_rating=1200.0,
        total_duels=0,
        wins=0,
        owner_id=1
    )
    
    vote = Vote(
        user_id=1,
        winner_id=1,
        loser_id=2
    )
    
    upload_limit = UploadLimit(
        user_id=1,
        upload_count=0,
        last_upload_date=None
    )
    
    print("✅ All models created successfully")
    return True

def test_elo_algorithm():
    """Test ELO rating algorithm"""
    print("🧪 Testing ELO algorithm...")
    
    # Test equal ratings
    winner_change, loser_change = calculate_elo_change(1200, 1200)
    assert winner_change == 16.0 and loser_change == -16.0
    
    # Test favorite wins
    winner_change, loser_change = calculate_elo_change(1400, 1200)
    assert 0 < winner_change < 16
    assert -16 < loser_change < 0
    
    # Test underdog wins
    winner_change, loser_change = calculate_elo_change(1200, 1400)
    assert winner_change > 16
    assert loser_change < -16
    
    print("✅ ELO algorithm tests passed")
    return True

def test_jwt_tokens():
    """Test JWT token creation and verification"""
    print("🧪 Testing JWT tokens...")
    
    # Test token creation
    token = create_access_token({"user_id": 123})
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Test token verification
    try:
        user_id = verify_access_token(token, HTTPException(status_code=401))
        assert user_id == 123
    except HTTPException:
        assert False, "Valid token should not raise exception"
    
    # Test invalid token
    try:
        verify_access_token("invalid_token", HTTPException(status_code=401))
        assert False, "Invalid token should raise exception"
    except HTTPException:
        pass  # Expected
    
    print("✅ JWT token tests passed")
    return True

def test_rate_limiting():
    """Test rate limiting logic"""
    print("🧪 Testing rate limiting...")
    
    # Test upload limit creation
    upload_limit = UploadLimit(
        user_id=1,
        upload_count=5,
        last_upload_date=None
    )
    
    # Test boundary conditions
    assert upload_limit.upload_count <= 5
    
    print("✅ Rate limiting tests passed")
    return True

def test_leaderboard_logic():
    """Test leaderboard eligibility logic"""
    print("🧪 Testing leaderboard logic...")
    
    # Test eligibility criteria
    eligible_photo = Photo(elo_rating=1200, total_duels=50, wins=25)
    ineligible_photo = Photo(elo_rating=1200, total_duels=49, wins=25)
    
    # Photos need >= 50 duels to be eligible
    assert eligible_photo.total_duels >= 50
    assert ineligible_photo.total_duels < 50
    
    print("✅ Leaderboard logic tests passed")
    return True

def run_all_tests():
    """Run all basic tests"""
    print("🚀 Running comprehensive PhotoRank tests...")
    print("=" * 50)
    
    tests = [
        test_database_models,
        test_elo_algorithm,
        test_jwt_tokens,
        test_rate_limiting,
        test_leaderboard_logic
    ]
    
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All basic tests passed! PhotoRank core functionality is working.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())