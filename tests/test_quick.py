#!/usr/bin/env python3
"""
Quick test script for R2 integration
Run this regularly to ensure everything works
"""

import urllib.request
import json
import sys

def quick_test():
    """Quick test of R2 integration"""
    print("🚀 Quick R2 Integration Test")
    
    tests = [
        ("Homepage", "http://localhost:9001/", 200),
        ("Leaderboard", "http://localhost:9001/leaderboard", 200),
        ("Upload page", "http://localhost:9001/upload", 200),
        ("Local photo", "http://localhost:9001/api/photos/8a973d64-aba4-40ff-8a59-c0f41fffa5f0.JPG", 200),
        ("R2 photo", "http://localhost:9001/api/photos/c9f3d5f1-c4f1-41e1-8dcf-82e354d5d43e.jpg", 200),
        ("Non-existent", "http://localhost:9001/api/photos/nonexistent.jpg", 404)
    ]
    
    passed = 0
    failed = 0
    
    for name, url, expected in tests:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                status = response.getcode()
                if status == expected:
                    print(f"✅ {name}: {status}")
                    passed += 1
                else:
                    print(f"❌ {name}: Expected {expected}, got {status}")
                    failed += 1
        except urllib.error.HTTPError as e:
            if e.code == expected:
                print(f"✅ {name}: {e.code}")
                passed += 1
            else:
                print(f"❌ {name}: Expected {expected}, got {e.code}")
                failed += 1
        except Exception as e:
            print(f"❌ {name}: {e}")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! R2 integration is working perfectly!")
        return True
    else:
        print("⚠️ Some tests failed. Check the issues above.")
        return False

if __name__ == "__main__":
    success = quick_test()
    sys.exit(0 if success else 1)