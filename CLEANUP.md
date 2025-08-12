# Local Uploads Cleanup

## Current Status
All photos are now served from Cloudflare R2. The local uploads directory contains old files that can be safely removed.

## Files to Clean
The following files are in local storage and can be deleted:
- 2b1c3487-14b0-4a86-a05f-adc6c75b6ce6.jpg (14.6MB)
- 2f6b4226-2e79-4c52-9841-98785c08dcf2.png (2.0MB)
- 6414a4e2-6996-4618-ac63-ecf3f3c64fc8.png (512KB)
- 73e7ce5b-2b91-4488-a2b6-cccdbb3908eb.png (3.4MB)
- 8a973d64-aba4-40ff-8a59-c0f41fffa5f0.JPG (86KB)
- 94f41f6b-7cac-414c-908b-0e792d0a20ea.png (1.4MB)
- ab6890e2-ac33-4f01-8d17-f9341f77a9e7.jpg (21KB)
- da8007a0-70f1-4f86-9fc4-4f5e656a03a1.png (1.3MB)
- e0891516-b4a4-4240-8173-65e3acb58158.png (2.1MB)
- e0ab65fb-112e-46ce-8948-7f7dc81b37a5.png (84KB)

## Cleanup Command
Run this command to clean local uploads:
```bash
sudo rm -f app/static/uploads/*
```

## Verification
After cleanup, the directory should be empty:
```bash
ls -la app/static/uploads/
```

## Note
These files are no longer needed as all photos are now served from Cloudflare R2.