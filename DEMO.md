# PhotoRank Quick Start

## 🚀 **Get Started in 30 Seconds**

### **1. Start the App**
```bash
docker compose -f docker-compose-dev.yml up -d
```

### **2. Access the App**
- **Main App**: http://localhost:9001
- **Login**: http://localhost:9001/login
- **Upload**: http://localhost:9001/upload
- **Leaderboard**: http://localhost:9001/leaderboard
- **Stats**: http://localhost:9001/stats

### **3. OAuth Setup (First Time)**

#### GitHub OAuth
1. Go to https://github.com/settings/developers
2. Create new OAuth app
3. Set redirect URL: `http://localhost:9001/auth/callback/github`

#### Google OAuth  
1. Go to https://console.developers.google.com/
2. Create OAuth 2.0 credentials
3. Set redirect URL: `http://localhost:9001/auth/callback/google`

#### Environment Variables
```bash
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### **4. Test the Flow**
1. Visit http://localhost:9001/login
2. Click GitHub or Google login
3. Upload photos (max 5/day)
4. Start voting!

## ✅ **What's Working**
- OAuth login (GitHub/Google)
- Photo upload with rate limiting
- ELO-based voting system
- Real-time leaderboard
- Photo deletion
- User statistics