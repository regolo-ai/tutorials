from crewai import Task
from agents import competitive_analyst, copywriter, campaign_manager

# Task 1: Competitive Analysis
analysis_task = Task(
    description="""Analyze the competitive landscape for {product_name} in {market_segment}.
    Include:
    - Top 5 competitors and their pricing
    - Unique value propositions
    - Market gaps and opportunities
    - Recommended positioning strategy""",
    expected_output="A structured competitive analysis report with actionable positioning recommendations.",
    agent=competitive_analyst
)

# Task 2: Create Marketing Copy
copy_task = Task(
    description="""Using the competitive analysis, create:
    - Product landing page copy (hero section, features, benefits)
    - 3-email launch sequence (teaser, launch, follow-up)
    - 5 Facebook/Instagram ad variations
    All copy must highlight our competitive advantages.""",
    expected_output="Complete marketing copy package in markdown format with clear sections.",
    agent=copywriter,
    context=[analysis_task]  # Depends on analyst's output
)

# Task 3: Campaign Strategy
strategy_task = Task(
    description="""Design a complete 30-day product launch campaign including:
    - Channel mix and budget allocation
    - Week-by-week timeline
    - Key metrics and KPIs (CAC, conversion rate, LTV targets)
    - A/B testing plan
    Use the positioning from analysis and copy assets created.""",
    expected_output="A detailed campaign plan with timeline, budget, and success metrics.",
    agent=campaign_manager,
    context=[analysis_task, copy_task]  # Depends on both previous outputs
)
