# Graduation Finder — Vercel Deployment Guide

This project is configured for deployment on Vercel with a Python Flask backend and static HTML frontend.

## Project Structure

```
graduation-finder/
├── api/
│   └── index.py              # Vercel serverless handler
├── backend/
│   ├── app.py                # Flask application
│   ├── requirements.txt       # Legacy requirements (for reference)
│   ├── gunicorn.conf.py
│   ├── face_encodings.pkl    # Face database (not in git)
│   ├── photos_metadata.pkl   # Metadata (not in git)
│   └── gdrive_file_mappingf.json  # Drive mappings (not in git)
├── frontend/
│   ├── index.html            # Main UI
│   ├── .gitignore
│   └── *.png                 # Images
├── vercel.json               # Vercel configuration
├── requirements.txt          # Vercel Python dependencies
└── .vercelignore            # Vercel ignore rules
```

## Deployment Steps

### 1. Prerequisites
- Vercel account (free or pro) — sign up at https://vercel.com
- GitHub repository pushed (already done)
- Python data files ready for upload

### 2. Deploy to Vercel

#### Option A: Using Vercel Dashboard (Recommended)
1. Go to https://vercel.com/dashboard
2. Click **"Add New"** → **"Project"**
3. Select your GitHub repository (`graduation-finder-backend`)
4. Vercel will auto-detect `vercel.json` configuration
5. **Don't modify build settings** — keep defaults
6. Click **"Deploy"**

#### Option B: Using Vercel CLI
```bash
npm i -g vercel          # Install Vercel CLI
vercel login              # Authenticate with your Vercel account
vercel                    # Deploy (from project root)
```

### 3. Upload Required Data Files

After deployment, your backend needs the face database files:

#### Option A: Deploy with Data (via GitHub)
1. Add `backend/face_encodings.pkl` to git (make sure `.gitignore` doesn't exclude)
2. Commit and push
3. Vercel will redeploy automatically

#### Option B: Upload via Vercel Dashboard
1. Go to your Vercel project settings
2. Add environment variables with the file contents (base64 encoded)
3. Or use Vercel CLI: `vercel env add`

#### Option C: Store in External Service
Deploy files to AWS S3, Google Drive, or similar, and load them at runtime:
```python
# In backend/app.py:
ENCODINGS_FILE = download_from_s3('face_encodings.pkl')
```

### 4. Set Environment Variables

In Vercel Dashboard → **Settings** → **Environment Variables**, add:

```
ENCODINGS_FILE=backend/face_encodings.pkl
METADATA_FILE=backend/photos_metadata.pkl
GDRIVE_FILE=backend/gdrive_file_mappingf.json
TOLERANCE=0.52
MAX_UPLOAD_MB=16
ALLOWED_ORIGINS=*
```

### 5. Test Deployment

Once deployed:
1. Visit your Vercel URL: `https://your-project.vercel.app`
2. Test the `/health` endpoint: `https://your-project.vercel.app/health`
3. Upload a photo to verify face search works

## API Endpoints

All endpoints are available at `https://your-project.vercel.app/`:

- **GET** `/health` — Check API status and database info
- **POST** `/search-face` — Search for matching faces
  - Form data: `face_image` (multipart file)
  - Response: JSON with matches and confidence scores

## Local Development

To test locally before deploying:

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask dev server
python backend/app.py

# Frontend will be available at http://localhost:5001
```

## Troubleshooting

### "File not found" errors
- Verify `face_encodings.pkl`, `photos_metadata.pkl`, and `gdrive_file_mappingf.json` are deployed
- Check `/health` endpoint for missing files
- Ensure paths in `vercel.json` env variables match actual file locations

### "face_recognition" module errors
- Vercel's Python runtime may need additional system dependencies
- Add `vercel.json` build config for dlib/face_recognition:
```json
"buildCommand": "pip install -r requirements.txt && python -c 'import face_recognition'"
```

### CORS errors
- API endpoints allow all origins by default (`ALLOWED_ORIGINS=*`)
- For security, update to specific domains in vercel.json env

### Cold start latency
- Python serverless functions have 5-10s cold start on free tier
- First request will be slow; subsequent requests are faster
- Consider Vercel Pro for better performance

## Notes

- The frontend automatically detects localhost vs production and connects to appropriate API
- Static files (HTML, images) are served directly by Vercel
- Python runtime uses Python 3.11 (default on Vercel)
- Maximum request timeout is 60 seconds on free tier

## Support

For Vercel docs: https://vercel.com/docs
For Flask integration: https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python
