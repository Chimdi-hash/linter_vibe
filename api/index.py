import sys
import os

# Add the root directory to the python path so imports from the root work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_server import app

# Vercel requires the application to be exposed
# The variable name should match what's imported or defined
