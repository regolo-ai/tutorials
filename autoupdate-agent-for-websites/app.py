from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
import asyncio

from rag_chain import get_rag_chain

async def auto_update_task(hours: float):
    """Background task that runs the content_generator script periodically."""
    print(f"\n[CRON] Auto-Update job registered. Will scrape website every {hours} hours.")
    while True:
        await asyncio.sleep(hours * 3600)
        print("\n[CRON] Triggering scheduled Knowledge Base Auto-Update...")
        try:
            # We run it in a subprocess so it doesn't block the FastAPI event loop or leak memory
            process = await asyncio.create_subprocess_exec(
                sys.executable, "content_generator.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(f"[CRON-SUCCESS] Scheduled Auto-Update completed successfully! (Check content_generator_log.txt for details)")
            else:
                print(f"[CRON-ERROR] Scheduled Auto-Update failed with code {process.returncode}")
                if stderr:
                    print(stderr.decode())
        except Exception as e:
            print(f"[CRON-ERROR] Failed to execute auto-update subprocess: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    auto_update_hours = os.environ.get("AUTO_UPDATE_HOURS")
    task = None
    if auto_update_hours:
        try:
            hours = float(auto_update_hours)
            if hours > 0:
                task = asyncio.create_task(auto_update_task(hours))
        except ValueError:
            print("[ERROR] AUTO_UPDATE_HOURS must be a valid number.")
            
    yield # App runs here
    
    # --- Shutdown ---
    if task:
        task.cancel()

app = FastAPI(title="AutoUpdate Agent", lifespan=lifespan)

# CORS Configuration: allow access from React frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    """Schema for the incoming agent query request."""
    question: str

class QueryResponse(BaseModel):
    """Schema for the outgoing agent answer response."""
    answer: str

# Initialize the RAG chain globally to reuse across API requests
rag_chain = get_rag_chain()

@app.post("/autoupdate-agent/query", response_model=QueryResponse)
async def agent_query(req: QueryRequest):
    """
    Endpoint to handle user queries.
    Invokes the RAG chain to retrieve context and generate an answer.
    """
    answer = rag_chain.invoke(req.question)
    return QueryResponse(answer=answer)

if __name__ == "__main__":
    # You can easily change the port here or via environment variables
    port = int(os.environ.get("PORT", 8080))
    print("="*60)
    print(f"[SUCCESS] AutoUpdate Agent API is starting!")
    print(f"[INFO] Server is operational on: http://localhost:{port}")
    print(f"[INFO] Swagger Documentation: http://localhost:{port}/docs")
    print("="*60)
    
    # We turn off reload to avoid double initialization in production
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
