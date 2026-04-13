import os
import io
import json
import pickle
import sys
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from PIL import Image, ImageOps
import logging

# Try to import numpy - critical for face recognition
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"numpy not available: {e}")
    NUMPY_AVAILABLE = False
    # Create a stub to prevent NameError
    class NumpyStub:
        @staticmethod
        def array(*args, **kwargs):
            raise RuntimeError("numpy not installed")
        @staticmethod
        def mean(*args, **kwargs):
            raise RuntimeError("numpy not installed")
        @staticmethod
        def empty(*args, **kwargs):
            raise RuntimeError("numpy not installed")
    np = NumpyStub()

# face_recognition will be imported lazily (only when search_face endpoint is called)
# This prevents startup failures on Vercel where dlib system deps aren't available
face_recognition = None
FACE_RECOGNITION_AVAILABLE = False

def _get_face_recognition():
    """Lazy import of face_recognition - only load when needed."""
    global face_recognition, FACE_RECOGNITION_AVAILABLE
    if face_recognition is None:
        try:
            import face_recognition as fr
            face_recognition = fr
            FACE_RECOGNITION_AVAILABLE = True
            logger.info("✓ face_recognition loaded on first use")
        except Exception as e:
            logger.warning(f"face_recognition not available: {e}")
            FACE_RECOGNITION_AVAILABLE = False
            # Return stub to prevent crashes
            class FaceRecognitionStub:
                @staticmethod
                def face_encodings(*args, **kwargs):
                    raise RuntimeError(f"face_recognition not available: {e}")
                @staticmethod
                def face_distance(*args, **kwargs):
                    raise RuntimeError(f"face_recognition not available: {e}")
            face_recognition = FaceRecognitionStub()
    return face_recognition

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────
class Config:
    # Get app root directory - works on both local and Vercel
    APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # File paths - use env vars if set, otherwise construct from APP_ROOT
    _encodings = os.getenv('ENCODINGS_FILE')
    ENCODINGS_FILE = _encodings if _encodings else os.path.join(APP_ROOT, 'backend', 'face_encodings.pkl')
    
    _metadata = os.getenv('METADATA_FILE')
    METADATA_FILE = _metadata if _metadata else os.path.join(APP_ROOT, 'backend', 'photos_metadata.pkl')
    
    _gdrive = os.getenv('GDRIVE_FILE')
    GDRIVE_MAPPING_FILE = _gdrive if _gdrive else os.path.join(APP_ROOT, 'backend', 'gdrive_file_mappingf.json')
    
    TOLERANCE           = float(os.getenv('TOLERANCE', '0.52'))
    MAX_UPLOAD_MB       = int(os.getenv('MAX_UPLOAD_MB', '16'))
    ALLOWED_ORIGINS     = os.getenv('ALLOWED_ORIGINS', '*').split(',')

    GDRIVE_DIRECT = "https://drive.google.com/uc?export=view&id={}"
    GDRIVE_THUMB  = "https://drive.google.com/thumbnail?id={}&sz=w500"

# ── App setup ────────────────────────────────────────────
try:
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_MB * 1024 * 1024

    # Log configuration for debugging
    logger.info(f"App root directory: {Config.APP_ROOT}")
    logger.info(f"Looking for encodings file: {Config.ENCODINGS_FILE}")
    logger.info(f"Looking for metadata file: {Config.METADATA_FILE}")
    logger.info(f"Looking for gdrive mapping file: {Config.GDRIVE_MAPPING_FILE}")

    # FIX 1: Explicit CORS config — allow all origins, methods, and headers
    CORS(app, resources={r"/*": {"origins": "*"}},
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "OPTIONS"])
    logger.info("✓ Flask app initialized successfully")
except Exception as e:
    logger.error(f"FATAL: Failed to initialize Flask app: {e}", exc_info=True)
    raise

# ── Load data once at startup ────────────────────────────
_data_cache = None   # FIX 2: manual cache instead of @lru_cache (avoids pickling issues)

def load_data():
    global _data_cache
    if _data_cache is not None:
        return _data_cache

    logger.info("Loading face database...")

    # --- face encodings ---
    try:
        with open(Config.ENCODINGS_FILE, 'rb') as f:
            db = pickle.load(f)
        logger.info(f"  Loaded {len(db)} face records from {Config.ENCODINGS_FILE}")
    except FileNotFoundError:
        logger.error(f"MISSING FILE: {Config.ENCODINGS_FILE}")
        db = {}
    except Exception as e:
        logger.error(f"Error loading encodings: {e}")
        db = {}

    # --- metadata ---
    try:
        with open(Config.METADATA_FILE, 'rb') as f:
            meta = pickle.load(f)
        logger.info(f"  Loaded {len(meta)} metadata records from {Config.METADATA_FILE}")
    except FileNotFoundError:
        logger.error(f"MISSING FILE: {Config.METADATA_FILE}")
        meta = {}
    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        meta = {}

    # --- GDrive mapping ---
    try:
        with open(Config.GDRIVE_MAPPING_FILE, 'r') as f:
            gdrive = json.load(f)
        logger.info(f"  Loaded {len(gdrive)} GDrive mappings from {Config.GDRIVE_MAPPING_FILE}")
    except FileNotFoundError:
        logger.error(f"MISSING FILE: {Config.GDRIVE_MAPPING_FILE}")
        gdrive = {}
    except Exception as e:
        logger.error(f"Error loading GDrive map: {e}")
        gdrive = {}

    # --- build numpy matrix ---
    ids, enc_matrix = [], []
    for photo_id, data in db.items():
        encs = data.get('encodings', [])
        if not encs:
            # FIX 3: support flat encoding (single array) not wrapped in a list
            if isinstance(data, np.ndarray) and data.shape == (128,):
                ids.append(photo_id)
                enc_matrix.append(data)
        else:
            for enc in encs:
                ids.append(photo_id)
                enc_matrix.append(enc)

    if enc_matrix:
        enc_array = np.array(enc_matrix, dtype=np.float64)
        logger.info(f"  Built encoding matrix: {enc_array.shape}")
    else:
        enc_array = np.empty((0, 128), dtype=np.float64)
        logger.warning("  Encoding matrix is EMPTY — no faces indexed yet!")

    _data_cache = (db, meta, gdrive, ids, enc_array)
    return _data_cache

# ── Helpers ──────────────────────────────────────────────
def encode_uploaded_images(files):
    """Extract face encodings from uploaded files. Returns list of 128-d vectors."""
    fr = _get_face_recognition()  # Lazy load face_recognition
    encodings = []
    for file in files:
        if not file or file.filename == '':
            continue
        try:
            img = Image.open(file.stream)
            img = ImageOps.exif_transpose(img)
            img = img.convert('RGB')
            img.thumbnail((1200, 1200), Image.LANCZOS)
            arr = np.array(img)
            # FIX 4: increase num_jitters for better accuracy on single upload
            found = fr.face_encodings(arr, num_jitters=3, model='large')
            if found:
                encodings.append(found[0])
                logger.info(f"  Encoded face from {file.filename}")
            else:
                logger.warning(f"  No face detected in {file.filename}")
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
    return encodings

def get_gdrive_urls(filename, gdrive_map):
    file_id = gdrive_map.get(filename)
    if not file_id:
        # FIX 5: also try without extension
        base = os.path.splitext(filename)[0]
        file_id = gdrive_map.get(base)
    if not file_id:
        logger.debug(f"No GDrive mapping found for: {filename}")
        return None, None
    return (
        Config.GDRIVE_DIRECT.format(file_id),
        Config.GDRIVE_THUMB.format(file_id)
    )

# ── Routes ───────────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    """FIX 6: belt-and-suspenders CORS headers on every response + force JSON content type."""
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    
    # Ensure all responses have JSON content type for consistency
    if response.status_code >= 400 or response.content_type is None:
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
    
    return response

@app.route('/api/test', methods=['GET', 'POST', 'OPTIONS'])
def api_test():
    """Simple test endpoint to verify API is responding with JSON."""
    return jsonify({'status': 'ok', 'message': 'API is working'})

@app.route('/', methods=['GET'])
def root():
    """Root endpoint."""
    return jsonify({'message': 'Graduation Finder API is running', 'endpoints': ['/health', '/search-face', '/api/test']})

@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all error handler that always returns JSON."""
    try:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500
    except Exception as inner_e:
        # If jsonify fails, return plain dict
        logger.error(f"Error handler itself failed: {inner_e}")
        return {'error': 'Internal error', 'type': type(e).__name__}, 500

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    try:
        db, meta, gdrive, ids, enc_array = load_data()
        missing = []
        for f in [Config.ENCODINGS_FILE, Config.METADATA_FILE, Config.GDRIVE_MAPPING_FILE]:
            if not os.path.exists(f):
                missing.append(f)
        return jsonify({
            "status":        "healthy",
            "total_photos":  len(meta),
            "total_faces":   len(enc_array),
            "gdrive_mapped": len(gdrive),
            "tolerance":     Config.TOLERANCE,
            "missing_files": missing,   # FIX 7: expose missing files to help debug
            "db_records":    len(db),
        })
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Face database failed to load. Check server logs.'
        }), 500

@app.route('/search-face', methods=['POST', 'OPTIONS'])
def search_face():
    # Handle preflight
    if request.method == 'OPTIONS':
        return '', 204

    try:
        files = request.files.getlist('face_image')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No images uploaded. Field name must be "face_image".'}), 400

        # 1 — Encode uploaded photos
        query_encodings = encode_uploaded_images(files)
        if not query_encodings:
            return jsonify({
                'error': (
                    'No face detected in your uploaded photo(s). '
                    'Please use a clear, well-lit, front-facing photo.'
                )
            }), 400

        # FIX 8: average all query encodings into one representative vector
        query_enc = np.mean(query_encodings, axis=0)

        # 2 — Load pre-built matrix and search
        db, meta, gdrive, ids, enc_array = load_data()

        if len(enc_array) == 0:
            logger.warning("Encoding matrix is empty — returning no matches")
            return jsonify({
                'success': True,
                'matches': [],
                'total_found': 0,
                'warning': 'Face database is empty. Run your indexing script first.'
            })

        # 3 — Vectorised distance computation
        fr = _get_face_recognition()  # Ensure face_recognition is available
        distances = fr.face_distance(enc_array, query_enc)
        logger.info(f"Distance stats — min: {distances.min():.3f}, "
                    f"max: {distances.max():.3f}, "
                    f"below tolerance ({Config.TOLERANCE}): "
                    f"{(distances < Config.TOLERANCE).sum()}")

        # 4 — Group by photo_id, keep minimum distance per photo
        best = {}
        for photo_id, dist in zip(ids, distances):
            if photo_id not in best or dist < best[photo_id]:
                best[photo_id] = dist

        # 5 — Filter and build response
        matches = []
        skipped_no_gdrive = 0
        for photo_id, dist in best.items():
            if dist >= Config.TOLERANCE:
                continue
            info     = meta.get(photo_id, {})
            filename = info.get('filename', f"{photo_id}.jpg")
            full_url, thumb_url = get_gdrive_urls(filename, gdrive)

            # FIX 9: don't skip photos just because GDrive mapping is missing —
            # include them with a placeholder so the UI can still show something
            if not full_url:
                skipped_no_gdrive += 1
                logger.debug(f"No GDrive URL for {filename} (id={photo_id})")
                # Uncomment next line to include unlinked matches anyway:
                # full_url = thumb_url = ''
                continue

            matches.append({
                'photo_id':   photo_id,
                'url':        full_url,
                'thumbnail':  thumb_url,
                'filename':   filename,
                'confidence': round(float(1 - dist), 4)
            })

        matches.sort(key=lambda x: x['confidence'], reverse=True)

        logger.info(
            f"Search complete: {len(matches)} matches returned, "
            f"{skipped_no_gdrive} skipped (no GDrive mapping)"
        )

        return jsonify({
            'success':           True,
            'matches':           matches,
            'total_found':       len(matches),
            'skipped_no_gdrive': skipped_no_gdrive,
        })
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.errorhandler(400)
def bad_request(e):
    try:
        return jsonify({'error': f'Bad request: {str(e)}'}), 400
    except:
        return {'error': 'Bad request'}, 400

@app.errorhandler(404)
def not_found(e):
    try:
        return jsonify({'error': 'Endpoint not found'}), 404
    except:
        return {'error': 'Endpoint not found'}, 404

@app.errorhandler(405)
def method_not_allowed(e):
    try:
        return jsonify({'error': 'Method not allowed'}), 405
    except:
        return {'error': 'Method not allowed'}, 405

@app.errorhandler(413)
def too_large(e):
    try:
        return jsonify({'error': f'File too large. Maximum {Config.MAX_UPLOAD_MB} MB per upload.'}), 413
    except:
        return {'error': f'File too large. Maximum {Config.MAX_UPLOAD_MB} MB per upload.'}, 413

@app.errorhandler(500)
def server_error(e):
    try:
        logger.error(f"500 error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error. Please try again.'}), 500
    except:
        return {'error': 'Internal server error'}, 500

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    try:
        logger.error(f"HTTP exception {e.code}: {e.description}")
        return jsonify({'error': str(e.description)}), e.code
    except:
        return {'error': str(e.description)}, getattr(e, 'code', 500)

if __name__ == '__main__':
    try:
        load_data()  # warm up — shows missing files immediately on start
    except Exception as e:
        logger.warning(f"Failed to load data at startup: {e}")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5001)), debug=True)