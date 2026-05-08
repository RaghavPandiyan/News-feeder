#!/usr/bin/env bash
set -e

echo "🚀 Starting News Feeder..."

# Copy .env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 Created .env from .env.example — edit it to add your ANTHROPIC_API_KEY"
fi

# Create virtualenv if not exists
if [ ! -d .venv ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

echo "✅ Starting server at http://localhost:8000"
echo "   Open this URL in your browser."
echo ""

python main.py
