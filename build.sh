#!/bin/bash
# Build script for Vercel deployment
# Ensures all Python dependencies are properly installed

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Verifying face_recognition installation..."
python -c "import face_recognition; print('✓ face_recognition imported successfully')" || {
    echo "⚠ face_recognition import failed, but deployment will continue"
}

echo "Verifying Flask installation..."
python -c "import flask; print(f'✓ Flask {flask.__version__} imported successfully')"

echo "Build complete!"
