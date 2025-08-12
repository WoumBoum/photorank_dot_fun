#!/usr/bin/env python3
"""
Cleanup script for local uploads
Run this with appropriate permissions to clean local storage
"""

import os
import glob
from pathlib import Path

def cleanup_local_uploads():
    """Clean all local uploads"""
    upload_dir = Path("app/static/uploads")
    
    if not upload_dir.exists():
        print("Upload directory doesn't exist")
        return
    
    # Get all files
    files = list(upload_dir.glob("*"))
    
    if not files:
        print("No files to clean")
        return
    
    print(f"Found {len(files)} files to clean:")
    for file in files:
        print(f"  - {file.name} ({file.stat().st_size} bytes)")
    
    # Clean files
    cleaned = 0
    for file in files:
        try:
            file.unlink()
            cleaned += 1
        except PermissionError:
            print(f"⚠️ Cannot delete {file.name} (permission denied)")
        except Exception as e:
            print(f"❌ Error deleting {file.name}: {e}")
    
    print(f"✅ Cleaned {cleaned} files")

if __name__ == "__main__":
    cleanup_local_uploads()
    print("🧹 Local uploads cleaned successfully!")