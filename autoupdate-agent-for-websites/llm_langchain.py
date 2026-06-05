import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize the LLM using Regolo.ai via the OpenAI-compatible interface.
# Make sure to set REGOLO_API_KEY, REGOLO_BASE_URL, and REGOLO_MODEL in your .env file.
llm = ChatOpenAI(
    api_key=os.environ.get("REGOLO_API_KEY", "your-regolo-api-key"),
    base_url=os.environ.get("REGOLO_BASE_URL", "https://api.regolo.ai/v1"),
    model=os.environ.get("REGOLO_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct"),
    temperature=0.0,  # Temperature 0.0 ensures deterministic and focused answers
)
