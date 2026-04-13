"""
Vercel Python serverless handler for the Graduation Finder API.
Imports and exports the Flask app for Vercel's Python runtime.
"""
import sys
import os
import traceback

# Add current directory and parent to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)

# Try to import the Flask app from backend.app
try:
    from backend.app import app
    print(f"[INFO] Successfully imported Flask app from backend.app", file=sys.stderr)
except Exception as e:
    print(f"[ERROR] Failed to import Flask app: {e}", file=sys.stderr)
    traceback.print_exc()
    
    # Create fallback app if import fails
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/api/test')
    @app.route('/health')
    @app.route('/search-face', methods=['POST', 'OPTIONS'])
    @app.route('/', methods=['GET'])
    def error_fallback():
        return jsonify({
            'error': f'Failed to initialize backend: {str(e)}',
            'type': 'ImportError'
        }), 500

# These explicit exports help Vercel's Python runtime find the app
application = app

# Ensure app is available at module level for Vercel
__all__ = ['app', 'application']

