import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.main import app
from mangum import Mangum

# Tell Mangum to strip "/.netlify/functions" from the path so FastAPI sees "/api/..."
handler = Mangum(app, api_gateway_base_path="/.netlify/functions")
