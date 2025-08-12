#!/usr/bin/env python3
"""
Debug script for Google OAuth configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=== Google OAuth Debug Information ===")
print("")

# Print all OAuth-related environment variables
print("1. Environment Variables:")
print("   GOOGLE_CLIENT_ID: {}".format(os.getenv('GOOGLE_CLIENT_ID', 'NOT SET')))
print("   GOOGLE_CLIENT_SECRET: {}".format('SET' if os.getenv('GOOGLE_CLIENT_SECRET') else 'NOT SET'))
print("   DOMAIN: {}".format(os.getenv('DOMAIN', 'NOT SET')))
print("   PORT: {}".format(os.getenv('PORT', 'NOT SET')))

# Construct the redirect URI
port = os.getenv('PORT', '8000')
domain = os.getenv('DOMAIN', 'localhost')
if domain == 'localhost':
    redirect_uri = "http://{}:{}/auth/callback/google".format(domain, port)
else:
    redirect_uri = "https://{}/auth/callback/google".format(domain)

print("")
print("2. Constructed Redirect URI:")
print("   {}".format(redirect_uri))

# Construct Google OAuth URL
client_id = os.getenv('GOOGLE_CLIENT_ID')
if client_id:
    google_auth_url = (
        "https://accounts.google.com/oauth2/authorize?"
        "client_id={}&"
        "redirect_uri={}&"
        "response_type=code&"
        "scope=openid%20email%20profile"
    ).format(client_id, redirect_uri)
    print("")
    print("3. Google OAuth URL:")
    print("   {}".format(google_auth_url))
else:
    print("")
    print("3. Google OAuth URL: Cannot construct - GOOGLE_CLIENT_ID not set")

# Print all environment variables containing 'oauth', 'auth', 'google', 'client'
print("")
print("4. All OAuth-related environment variables:")
for key, value in os.environ.items():
    if any(term in key.lower() for term in ['oauth', 'auth', 'google', 'client', 'secret']):
        if 'SECRET' in key.upper():
            print("   {}: {}".format(key, 'SET' if value else 'NOT SET'))
        else:
            print("   {}: {}".format(key, value))

print("")
print("=== End Debug Information ===")