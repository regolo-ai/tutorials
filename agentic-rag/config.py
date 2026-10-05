import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# configuration for regolo inference
regolo_base_url = os.environ.get("regolo_base_url", "https://api.regolo.ai/v1")
regolo_model_name = os.environ.get("regolo_model", "brick-complexity-pro")
regolo_api_key = os.environ.get("regolo_api_key", "")

# local storage configuration
base_dir = Path(__file__).resolve().parent
database_path = base_dir / "rag_storage.sqlite3"
sample_data_dir = base_dir / "sample_data"

# execution limits
max_retrieval_rounds = 4
top_k_baseline = 2
top_k_hierarchical = 2
