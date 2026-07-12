import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from mangum import Mangum

from src.main import app

# Tell Mangum to strip "/.netlify/functions" from the path so FastAPI sees "/api/..."
handler = Mangum(app, api_gateway_base_path="/.netlify/functions")
