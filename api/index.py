import sys
import os

# Add the project root to sys.path so Vercel can resolve absolute imports like "from src.main import app"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import app
