#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test runner for PhotoRank application
"""

import subprocess
import sys
import os
from pathlib import Path

def run_tests():
    """Run all tests with comprehensive coverage"""
    
    print("Starting comprehensive test suite for PhotoRank...")
    print("=" * 60)
    
    # Ensure test database exists
    test_db_url = os.getenv('DATABASE_URL', '').replace('/fastapi', '/fastapi_test')
    if not test_db_url:
        test_db_url = "postgresql://postgres:pepito1234@localhost:5433/fastapi_test"
    
    # Set environment variables for testing
    env = os.environ.copy()
    env['DATABASE_URL'] = test_db_url
    env['TESTING'] = 'true'
    
    # Test categories to run
    test_categories = [
        "test_auth.py",
        "test_photos.py", 
        "test_votes.py",
        "test_leaderboard.py",
        "test_user_stats.py",
        "test_edge_cases.py",
        "test_integration.py"
    ]
    
    results = {}
    
    for test_file in test_categories:
        print(f"\nRunning {test_file}...")
        print("-" * 40)
        
        try:
            cmd = [
                sys.executable, "-m", "pytest", 
                f"tests/{test_file}",
                "-v",
                "--tb=short"
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
            
            if result.returncode == 0:
                print(f"PASSED: {test_file}")
                results[test_file] = "PASSED"
            else:
                print(f"FAILED: {test_file}")
                print(result.stdout)
                print(result.stderr)
                results[test_file] = "FAILED"
                
        except Exception as e:
            print(f"ERROR running {test_file}: {e}")
            results[test_file] = "ERROR"
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r == "PASSED")
    total = len(results)
    
    for test_file, status in results.items():
        print(f"{test_file}: {status}")
    
    print(f"\nOverall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("All tests passed! PhotoRank is ready for production.")
        return 0
    else:
        print("Some tests failed. Please review the output above.")
        return 1

def run_coverage():
    """Run tests with coverage report"""
    print("\nRunning tests with coverage...")
    
    env = os.environ.copy()
    env['TESTING'] = 'true'
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--cov=app",
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ]
    
    result = subprocess.run(cmd, env=env)
    return result.returncode

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--coverage":
        sys.exit(run_coverage())
    else:
        sys.exit(run_tests())