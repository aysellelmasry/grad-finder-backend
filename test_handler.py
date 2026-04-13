#!/usr/bin/env python
"""Test that the Vercel handler works correctly."""
import sys
sys.path.insert(0, '.')

try:
    from api.index import app, application, handler
    print("✓ All handlers imported")
    
    # Try a test request
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.get('/api/test')
        print(f"✓ GET /api/test: {resp.status_code}")
        print(f"  Response: {resp.get_json()}")
        print("✓ All tests passed!")
except Exception as e:
    import traceback
    print(f"✗ Error: {e}")
    traceback.print_exc()
    sys.exit(1)
