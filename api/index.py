"""
Vercel Python serverless handler for the Graduation Finder API.
This module wraps the Flask app for Vercel's Python runtime with proper error handling.
"""
import sys
import os
import traceback
from functools import wraps

# Ensure backend dir and app root are in Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.app import app
except ImportError as e:
    print(f"FATAL: Failed to import Flask app: {e}")
    traceback.print_exc()
    # Create minimal app if import fails
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.errorhandler(500)
    def handle_error(e):
        return jsonify({'error': f'Import error: {str(e)}'}), 500
    
    @app.route('/health')
    def health():
        return jsonify({'error': 'Flask app failed to import', 'details': str(e)}), 500

# Wrapper to ensure all responses have proper Content-Type
original_wsgi = app.wsgi_app

def cors_wrapper(environ, start_response):
    def custom_start_response(status, response_headers, exc_info=None):
        # Ensure JSON responses have correct content type
        response_headers = list(response_headers)
        has_content_type = any(h[0].lower() == 'content-type' for h in response_headers)
        if not has_content_type:
            response_headers.append(('Content-Type', 'application/json'))
        return start_response(status, response_headers, exc_info)
    
    return original_wsgi(environ, custom_start_response)

app.wsgi_app = cors_wrapper

# Export as `app` for Vercel's Python runtime
__all__ = ['app']
