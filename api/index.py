"""
Vercel Python serverless handler for the Graduation Finder API.
Imports and exports the Flask app for Vercel's Python runtime.
"""
import sys
import os

# Add current directory and parent to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

# Import the Flask app from backend.app
from backend.app import app

# These explicit exports help Vercel's Python runtime find the app
application = app

# Ensure app is available at module level for Vercel
__all__ = ['app', 'application']

