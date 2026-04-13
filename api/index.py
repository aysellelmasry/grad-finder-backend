"""
Vercel Python serverless handler for the Graduation Finder API.
This module imports the Flask app and exports it for Vercel's Python runtime.
"""
import sys
import os

# Ensure backend dir is in Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the Flask app from backend
from backend.app import app

# Export as `app` for Vercel's Python runtime
__all__ = ['app']
