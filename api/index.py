"""
Vercel Python serverless handler.
"""
import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import and export Flask app for Vercel
from backend.app import app

# Vercel serverless runtimes look for 'app', 'application', or 'handler'
application = app
handler = app

