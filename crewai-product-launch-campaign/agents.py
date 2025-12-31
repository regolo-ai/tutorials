from crewai import Agent
from llm_config import regolo_llm

# Agent 1: Competitive Intelligence Analyst
competitive_analyst = Agent(
    role="Senior Competitive Intelligence Analyst",
    goal="Analyze competitor products, pricing strategies, and market positioning for {product_name} in {market_segment}",
    backstory="You're a strategic analyst with 10+ years in e-commerce. You identify market gaps and competitive advantages that inform product positioning.",
    llm=regolo_llm,
    verbose=True
)

# Agent 2: Conversion Copywriter
copywriter = Agent(
    role="Conversion-Focused Copywriter",
    goal="Create compelling product descriptions, email sequences, and ad copy that drive conversions for {product_name}",
    backstory="You craft persuasive copy backed by psychology and conversion rate optimization principles. Every word has a purpose.",
    llm=regolo_llm,
    verbose=True
)

# Agent 3: Growth Campaign Manager
campaign_manager = Agent(
    role="Growth Campaign Strategist",
    goal="Design a complete product launch campaign with channels, timeline, KPIs, and budget allocation for {product_name}",
    backstory="You've launched 50+ products with an average 3x ROAS. You know which channels work and how to allocate resources for maximum impact.",
    llm=regolo_llm,
    verbose=True
)
