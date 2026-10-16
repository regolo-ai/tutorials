import os
import sys
from pathlib import Path

os.environ["DB_PATH"] = ":memory:"
import tempfile

os.environ["REGOLO_API_KEY"] = "test-key-1234"
os.environ["ENV_FILE"] = os.path.join(tempfile.mkdtemp(), ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
