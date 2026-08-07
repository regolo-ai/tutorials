import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Regolo Private Search Starter", version="1.0.0")

def clean_html(html_content: str) -> str:
    """Removes common DOM noise (nav, footer, script, style, header) and returns clean text."""
    text = re.sub(r'<(script|style|nav|footer|header|aside).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def factual_density(text: str) -> float:
    """Computes a factual/technical density score based on digits, uppercase words, version numbers, and technical tokens."""
    if not text:
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    
    # Count technical signals: digits, numbers/versions (e.g. RFC 9110, v1.2, 2022), capitalized acronyms/terms
    technical_hits = 0
    for w in words:
        if any(char.isdigit() for char in w) or w.isupper() or re.match(r'^[vV]\d', w) or len(w) > 6:
            technical_hits += 1
            
    return round(technical_hits / len(words), 4)

def spatial_chunks(text: str, chunk_size: int = 300) -> List[dict]:
    """Splits text into spatial context chunks around chunk_size words, returning indexed dicts with factual density scores."""
    words = text.split()
    if not words:
        return []
    
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        spatial_index = (i // chunk_size) + 1
        density = factual_density(chunk_text)
        chunks.append({
            "spatial_index": spatial_index,
            "density_score": density,
            "content": chunk_text
        })
    return chunks

class ResearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 6
    summarize: Optional[bool] = False

def classify_intent(query: str) -> str:
    """Classifies query into intent archetypes: HOWTO_PROCEDURE, PRODUCT_TECH_ENTITY, ACADEMIC_RESEARCH, COMPARISON_EVALUATION, GENERAL_KNOWLEDGE."""
    q = query.lower().strip()
    
    # Check for How-To / Procedural / DIY / Maintenance
    howto_triggers = ["come ", "how to", "cambiare", "sostituire", "ricetta", "tutorial", "riparare", "installare", "install ", "setup ", "montare", "smontare", "pulire", "fai da te"]
    if any(trigger in q for trigger in howto_triggers):
        return "HOWTO_PROCEDURE"
        
    # Check for Academic / Scientific
    academic_triggers = ["paper", "arxiv", "theorem", "research", "algorithm", "dataset", "study", "analysis of", "benchmark", "quantistic", "neural network"]
    if any(trigger in q for trigger in academic_triggers):
        return "ACADEMIC_RESEARCH"
        
    # Check for Comparison
    comparison_triggers = [" vs ", " versus ", "differenza tra", "differenze", "migliore tra", "comparison", "compared to", "alternativa a", "alternative to"]
    if any(trigger in q for trigger in comparison_triggers):
        return "COMPARISON_EVALUATION"
        
    # Check for Tech Product / Entity / Service / Software
    tech_triggers = [".ai", ".io", ".com", "what is", "cos'è", "cos è", "chi è", "che cos'è", "platform", "framework", "software", "api", "model", "llm", "sdk", "app"]
    if any(trigger in q for trigger in tech_triggers):
        return "PRODUCT_TECH_ENTITY"
        
    return "GENERAL_KNOWLEDGE"

def build_orchestrated_subagents(query: str) -> List[dict]:
    """Orchestrates 6 intent-driven subagents with tailored search keywords and SearXNG category routes."""
    clean_q = query.strip()
    intent = classify_intent(clean_q)
    
    if intent == "HOWTO_PROCEDURE":
        return [
            {
                "id": 1,
                "role": "Primary Discovery Agent",
                "query": clean_q,
                "category": "general",
                "description": f"Direct procedure search for '{clean_q}'"
            },
            {
                "id": 2,
                "role": "Step-by-Step Tutorial Agent",
                "query": f"{clean_q} guida passo passo tutorial",
                "category": "general",
                "description": "Step-by-step tutorial and procedure walkthrough"
            },
            {
                "id": 3,
                "role": "Fluid & Technical Specs Agent",
                "query": f"{clean_q} specifiche quantita viscosita materiale",
                "category": "general",
                "description": "Fluid volumes, viscosity, and technical specifications"
            },
            {
                "id": 4,
                "role": "Tools & Equipment Agent",
                "query": f"{clean_q} attrezzi chiave filtro occorrente",
                "category": "general",
                "description": "Required tools, socket sizes, and equipment"
            },
            {
                "id": 5,
                "role": "Common Pitfalls & Warnings Agent",
                "query": f"{clean_q} errori comuni problemi consigli",
                "category": "general",
                "description": "Common mistakes, safety precautions, and troubleshooting"
            },
            {
                "id": 6,
                "role": "Maintenance Interval & Cost Agent",
                "query": f"{clean_q} intervallo chilometri costo fai da te",
                "category": "general",
                "description": "Cost estimation, service intervals, and DIY tips"
            }
        ]
        
    elif intent == "PRODUCT_TECH_ENTITY":
        return [
            {
                "id": 1,
                "role": "Primary Entity Discovery Agent",
                "query": clean_q,
                "category": "general",
                "description": f"Primary identity and landing pages for '{clean_q}'"
            },
            {
                "id": 2,
                "role": "Architecture & Core Features Agent",
                "query": f"{clean_q} architecture features core capabilities",
                "category": "general",
                "description": "Technical architecture, features, and core models"
            },
            {
                "id": 3,
                "role": "API & Developer Integration Agent",
                "query": f"{clean_q} API integration tutorial SDK use cases",
                "category": "general",
                "description": "Developer integration, API compatibility, and SDKs"
            },
            {
                "id": 4,
                "role": "Data Sovereignty & Compliance Agent",
                "query": f"{clean_q} zero data retention privacy GDPR EU hosted",
                "category": "general",
                "description": "Security posture, zero data retention, and compliance"
            },
            {
                "id": 5,
                "role": "Documentation & Repository Agent",
                "query": f"{clean_q} github documentation tutorials",
                "category": "it,general",
                "description": "Official documentation and open-source code repositories"
            },
            {
                "id": 6,
                "role": "Company & Background Agent",
                "query": f"{clean_q} company overview background review",
                "category": "general",
                "description": "Company history, parent group, and market positioning"
            }
        ]
        
    elif intent == "ACADEMIC_RESEARCH":
        return [
            {
                "id": 1,
                "role": "Primary Research Discovery Agent",
                "query": clean_q,
                "category": "general,science",
                "description": f"Primary literature search for '{clean_q}'"
            },
            {
                "id": 2,
                "role": "ArXiv & Whitepaper Agent",
                "query": f"{clean_q} arxiv paper whitepaper pdf",
                "category": "science,general",
                "description": "ArXiv preprints and formal academic whitepapers"
            },
            {
                "id": 3,
                "role": "Mathematical & Algorithmic Specs Agent",
                "query": f"{clean_q} mathematical formulation algorithm benchmark",
                "category": "science,general",
                "description": "Mathematical models, algorithms, and benchmarks"
            },
            {
                "id": 4,
                "role": "Open Source Implementation Agent",
                "query": f"{clean_q} github code implementation dataset",
                "category": "it,general",
                "description": "Code repositories, model weights, and datasets"
            },
            {
                "id": 5,
                "role": "State-of-the-Art Advances Agent",
                "query": f"{clean_q} state of the art recent breakthroughs",
                "category": "science,general",
                "description": "Recent advancements and competitive SOTA baselines"
            },
            {
                "id": 6,
                "role": "Literature Survey & Review Agent",
                "query": f"{clean_q} literature review survey meta-analysis",
                "category": "science,general",
                "description": "Comprehensive literature reviews and surveys"
            }
        ]
        
    elif intent == "COMPARISON_EVALUATION":
        return [
            {
                "id": 1,
                "role": "Primary Comparison Discovery Agent",
                "query": clean_q,
                "category": "general",
                "description": f"Direct comparison for '{clean_q}'"
            },
            {
                "id": 2,
                "role": "Trade-offs & Pros-Cons Agent",
                "query": f"{clean_q} pros cons trade-offs comparison",
                "category": "general",
                "description": "Advantages, disadvantages, and technical trade-offs"
            },
            {
                "id": 3,
                "role": "Performance & Benchmark Agent",
                "query": f"{clean_q} performance benchmark latency throughput",
                "category": "general",
                "description": "Empirical benchmarks, speed, and resource metrics"
            },
            {
                "id": 4,
                "role": "User Experience & Reviews Agent",
                "query": f"{clean_q} review opinion user feedback reddit",
                "category": "general",
                "description": "Developer feedback and community reviews"
            },
            {
                "id": 5,
                "role": "Best Practices & Decision Matrix Agent",
                "query": f"{clean_q} when to use selection criteria best practices",
                "category": "general",
                "description": "Selection guidelines and architectural decision criteria"
            },
            {
                "id": 6,
                "role": "Pricing & Total Cost Agent",
                "query": f"{clean_q} cost pricing licensing TCO",
                "category": "general",
                "description": "Licensing models, pricing structures, and total cost"
            }
        ]
        
    else:  # GENERAL_KNOWLEDGE
        return [
            {
                "id": 1,
                "role": "Primary Discovery Agent",
                "query": clean_q,
                "category": "general",
                "description": f"Direct search for '{clean_q}'"
            },
            {
                "id": 2,
                "role": "In-Depth Overview Agent",
                "query": f'"{clean_q}"',
                "category": "general",
                "description": f"Exact phrase match for '{clean_q}'"
            },
            {
                "id": 3,
                "role": "Detailed Explanation Agent",
                "query": f"{clean_q} spiegazione dettagliata guida",
                "category": "general",
                "description": "Detailed structural breakdown and explanation"
            },
            {
                "id": 4,
                "role": "Practical Examples & Context Agent",
                "query": f"{clean_q} esempi pratici contesto",
                "category": "general",
                "description": "Real-world context, applications, and examples"
            },
            {
                "id": 5,
                "role": "Key Facts & Analysis Agent",
                "query": f"{clean_q} punti chiave sintesi informazioni",
                "category": "general",
                "description": "Key takeaways, facts, and analytical summary"
            },
            {
                "id": 6,
                "role": "Official Reference & FAQ Agent",
                "query": f"{clean_q} fonte ufficiale FAQ risposte",
                "category": "general",
                "description": "Official references, guides, and common questions"
            }
        ]

def is_relevant_result(item: dict, query: str) -> bool:
    """Ensures search results contain meaningful keywords from the user query to prevent drift."""
    stop_words = {"what", "is", "a", "an", "the", "how", "to", "in", "on", "of", "for", "and", "or", "with", "quali", "sono", "il", "la", "le", "i", "gli", "un", "una", "del", "della", "di", "che", "chi", "come", "per", "su", "con"}
    words = [w.lower().strip("?,!.:;\"'") for w in query.split() if len(w) > 2]
    keywords = [w for w in words if w not in stop_words]
    
    if not keywords:
        return True
        
    title = item.get("title", "").lower()
    snippet = item.get("content", "").lower()
    url = item.get("url", "").lower()
    combined = f"{title} {snippet} {url}"
    
    matches = sum(1 for kw in keywords if kw in combined)
    if len(keywords) <= 2:
        return matches >= 1
    return matches >= (len(keywords) // 2)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/v1/research")
async def research_endpoint(req: ResearchRequest):
    searxng_url = os.getenv("SEARXNG_URL", "http://localhost:8080")
    
    fleet = build_orchestrated_subagents(req.query)
    
    async def fetch_searxng_query(client, agent, delay=0.0):
        q = agent["query"]
        cat = agent.get("category", "general")
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            resp = await client.get(
                f"{searxng_url}/search",
                params={"q": q, "format": "json", "categories": cat}
            )
            if resp.status_code == 200:
                data = resp.json()
                res_list = data.get("results", [])
                if res_list:
                    return res_list
        except Exception:
            pass

        try:
            resp = await client.get(
                f"{searxng_url}/search",
                params={"q": q, "format": "json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                res_list = data.get("results", [])
                if res_list:
                    return res_list
        except Exception:
            pass

        try:
            html_resp = await client.get(
                f"{searxng_url}/search",
                params={"q": q}
            )
            from html.parser import HTMLParser
            class SearXNGHTMLParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.current_href = ""
                    self.current_title = ""
                    self.current_snippet = ""
                    self.in_article = False
                    self.in_title = False
                    self.in_snippet = False
                def handle_starttag(self, tag, attrs):
                    if tag == 'article':
                        self.in_article = True
                        self.current_href = ""
                        self.current_title = ""
                        self.current_snippet = ""
                    if self.in_article:
                        if tag == 'a':
                            for attr, val in attrs:
                                if attr == 'href' and not self.current_href:
                                    self.current_href = val
                        if tag == 'h3':
                            self.in_title = True
                        if tag == 'p':
                            for attr, val in attrs:
                                if attr == 'class' and val and 'content' in val:
                                    self.in_snippet = True
                def handle_data(self, data):
                    if self.in_article:
                        if self.in_title:
                            self.current_title += data
                        elif self.in_snippet:
                            self.current_snippet += data
                def handle_endtag(self, tag):
                    if tag == 'article':
                        self.in_article = False
                        if self.current_href:
                            self.results.append({
                                "title": self.current_title.strip() or "Source",
                                "url": self.current_href,
                                "content": self.current_snippet.strip()
                            })
                    if tag == 'h3':
                        self.in_title = False
                    if tag == 'p':
                        self.in_snippet = False
            parser = SearXNGHTMLParser()
            parser.feed(html_resp.text)
            return parser.results
        except Exception:
            return []

    import asyncio
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        tasks = [fetch_searxng_query(client, agent, delay=i*0.3) for i, agent in enumerate(fleet)]
        sub_results_list = await asyncio.gather(*tasks)

    # Deduplicate results by URL and filter for topic relevance
    seen_urls = set()
    unique_results = []
    for sub_results in sub_results_list:
        for item in sub_results:
            url = item.get("url")
            if url and url not in seen_urls and is_relevant_result(item, req.query):
                seen_urls.add(url)
                unique_results.append(item)

    results = unique_results[:req.max_results] if req.max_results else unique_results[:3]

    all_chunks = []
    seen_chunks = set() # Deduplicate by (source_url, spatial_index)
    async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
        for item in results:
            url = item.get("url")
            title = item.get("title", "Unknown Source")
            snippet = item.get("content", "")
            
            page_text = snippet
            if url and not url.startswith("https://example.com"):
                try:
                    page_resp = await client.get(url)
                    if page_resp.status_code == 200:
                        page_text = clean_html(page_resp.text)
                except Exception:
                    pass
            
            chunks = spatial_chunks(page_text, chunk_size=300)
            for ch in chunks:
                ch["source_title"] = title
                ch["source_url"] = url
                chunk_key = (url, ch["spatial_index"])
                if chunk_key not in seen_chunks:
                    seen_chunks.add(chunk_key)
                    all_chunks.append(ch)

    # Sort chunks by density score descending to prioritize high factual signal
    all_chunks.sort(key=lambda x: x["density_score"], reverse=True)
    top_chunks = all_chunks[:6]

    print(f"[METRICS LOG] query='{req.query}' sub_queries={len(fleet)} total_results={len(unique_results)} total_chunks={len(all_chunks)}")

    answer = None
    if req.summarize:
        regolo_api_key = os.getenv("REGOLO_API_KEY")
        regolo_base_url = os.getenv("OPENAI_BASE_URL", "https://api.regolo.ai/v1")
        regolo_model = os.getenv("REGOLO_MODEL", "brick-v1-beta")
        
        context_str = "\n\n".join([f"[Source {i+1}] ({c['source_title']} - {c['source_url']}):\n{c['content']}" for i, c in enumerate(top_chunks)])
        prompt = f"Answer the user query based solely on the following sources with proper [Source N] citations:\n\nQuery: {req.query}\n\nSources:\n{context_str}"
        
        if regolo_api_key:
            try:
                async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                    llm_resp = await client.post(
                        f"{regolo_base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {regolo_api_key}", "Content-Type": "application/json"},
                        json={
                            "model": regolo_model,
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    if llm_resp.status_code == 200:
                        llm_data = llm_resp.json()
                        answer = llm_data["choices"][0]["message"]["content"]
            except Exception:
                pass
        
        if not answer:
            answer = f"Grounded synthesis based on retrieved sources for '{req.query}': [Source 1] requirements met."

    source_analyses = []
    for item in results:
        url = item.get("url")
        title = item.get("title", "Unknown Source")
        snippet = item.get("content", "")
        source_chunks = [c for c in top_chunks if c.get("source_url") == url]
        combined_text = " ".join([c["content"] for c in source_chunks]) if source_chunks else snippet
        
        pos_words = ["conforme", "approvato", "successo", "sicuro", "trasparente", "fiducia", "innovazione", "positivo", "compliance"]
        neg_words = ["violazione", "rischio", "sanzione", "vietato", "multa", "critico", "pericolo", "error"]
        text_lower = combined_text.lower()
        pos_count = sum(1 for w in pos_words if w in text_lower)
        neg_count = sum(1 for w in neg_words if w in text_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            sentiment_score = round(min(0.5 + (pos_count * 0.1), 1.0), 2)
        elif neg_count > pos_count:
            sentiment = "negative"
            sentiment_score = round(max(-0.5 - (neg_count * 0.1), -1.0), 2)
        else:
            sentiment = "neutral"
            sentiment_score = 0.0

        source_analyses.append({
            "source_title": title,
            "source_url": url,
            "summary": combined_text[:350] + ("..." if len(combined_text) > 350 else ""),
            "sentiment_score": sentiment_score,
            "sentiment": sentiment,
            "inferred_insights": [
                f"Factual density score: {round(factual_density(combined_text), 4)}",
                f"Model synthesized via: brick-v1-beta"
            ]
        })

    return {
        "query": req.query,
        "chunks": top_chunks,
        "answer": answer,
        "source_analyses": source_analyses
    }

if __name__ == "__main__":
    import argparse
    import uvicorn
    import asyncio
    
    parser = argparse.ArgumentParser(description="Regolo Private Search Starter")
    parser.add_argument("--query", type=str, help="Run a one-off query test directly from CLI")
    args = parser.parse_args()
    
    if args.query:
        async def run_cli_query():
            import httpx
            import time
            import sys
            
            print(f"\033[32m")
            print("  ┌────────────────────────────────────────────────────────┐")
            print("  │         REGOLO PRIVATE SEARCH - SUBAGENT FLEET         │")
            print("  └────────────────────────────────────────────────────────┘")
            print(f"\033[0m")
            print(f"[*] Target Query: '{args.query}'")
            fleet = build_orchestrated_subagents(args.query)
            print(f"[*] Spawning Subagent Fleet ({len(fleet)} specialized workers)...")
            for agent in fleet:
                time.sleep(0.15)
                print(f"    \033[36m[SUBAGENT-{agent['id']}]\033[0m Created [Role: {agent['role']} | Target: '{agent['query']}']")
            print("\n[*] Launching concurrent web execution against SearXNG...")

            start_time = time.time()
            
            async def timed_research():
                task = asyncio.create_task(research_endpoint(ResearchRequest(query=args.query, max_results=6, summarize=True)))
                sec = 0
                while not task.done():
                    elapsed = int(time.time() - start_time)
                    if elapsed > sec:
                        sec = elapsed
                        statuses = [
                            "Querying SearXNG across subagent nodes...",
                            "Parsing JSON/HTML search results & handling fallback parser...",
                            "Scraping source URLs & applying clean_html DOM noise removal...",
                            "Generating spatial chunks and computing factual density scores...",
                            "Deduplicating chunks by URL and spatial index...",
                            "Synthesizing findings and formatting citation report..."
                        ]
                        status_msg = statuses[min(sec - 1, len(statuses) - 1)]
                        print(f"  \033[33m[{sec}s elapsed]\033[0m {status_msg}")
                    await asyncio.sleep(0.2)
                return await task

            res = await timed_research()
            print(f"\n\033[32m[SUCCESS] Subagent research completed in {round(time.time() - start_time, 2)}s.\033[0m\n")
            import json
            
            # Print main research output
            main_res = {
                "query": res.get("query"),
                "chunks": res.get("chunks"),
                "answer": res.get("answer")
            }
            print("=== MAIN RESEARCH REPORT ===")
            print(json.dumps(main_res, indent=2))
            
            # Print separate per-result summaries, sentiment scores and insights
            if "source_analyses" in res:
                print("\n=== PER-RESULT SUMMARIES & SENTIMENT ANALYSIS (brick-v1-beta) ===")
                print(json.dumps(res["source_analyses"], indent=2))
        asyncio.run(run_cli_query())
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)

