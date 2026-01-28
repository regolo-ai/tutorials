#!/usr/bin/env python3
"""
Telegram Bot Handler for Clawdbot Knowledge Base
Integrates RAG pipeline with Telegram Bot API
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from rag_pipeline import KnowledgeBaseRAG, build_knowledge_base

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAX_QUERIES_PER_DAY = int(os.getenv("MAX_QUERIES_PER_DAY", "500"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "./logs/kb-bot.log")

# Setup logging
os.makedirs(os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else "./logs", exist_ok=True)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize RAG pipeline
rag = KnowledgeBaseRAG()


class BotStats:
    """Track bot usage statistics."""
    def __init__(self):
        self.daily_queries = {}
        self.reset_date = datetime.now().date()
        self.user_queries = {}  # Track per-user usage
    
    def increment(self, user_id: Optional[int] = None):
        date = datetime.now().date()
        
        # Reset if new day
        if date > self.reset_date:
            self.daily_queries = {}
            self.user_queries = {}
            self.reset_date = date
        
        # Global counter
        self.daily_queries[date] = self.daily_queries.get(date, 0) + 1
        
        # Per-user counter
        if user_id:
            if user_id not in self.user_queries:
                self.user_queries[user_id] = 0
            self.user_queries[user_id] += 1
    
    def get_today_count(self):
        return self.daily_queries.get(datetime.now().date(), 0)
    
    def get_user_count(self, user_id: int):
        return self.user_queries.get(user_id, 0)
    
    def is_limit_reached(self):
        return self.get_today_count() >= MAX_QUERIES_PER_DAY


stats = BotStats()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_name = update.effective_user.first_name
    welcome_message = f"""
👋 **Welcome {user_name} to the Knowledge Base Bot!**

I can help you search through company documentation, runbooks, policies, and technical guides using AI-powered retrieval.

**🎯 Available Commands:**
• `/kb <question>` - Search the knowledge base
• `/kb_stats` - Show usage statistics and costs
• `/kb_update` - Rebuild document index (admin only)
• `/kb_help` - Show this help message

**💡 Example queries:**
/kb What is our GDPR data retention policy?
/kb How do we handle production incidents?
/kb What are the deployment procedures?
/kb Explain our security guidelines

**🔒 Privacy:**
All queries are processed on EU-hosted GPUs (Regolo.ai) with zero data retention outside your infrastructure. GDPR-compliant by design.

**⚡ Powered by:**
• Embeddings: gte-Qwen2
• Reranking: Qwen3-Reranker-4B
• Generation: {os.getenv('CHAT_MODEL', 'Llama-3.1-8B-Instruct')}

Try asking me something! 🚀
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kb_help command."""
    await start_command(update, context)


async def kb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kb <question> command."""
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Rate limiting
    if stats.is_limit_reached():
        await update.message.reply_text(
            f"⚠️ **Daily query limit reached** ({MAX_QUERIES_PER_DAY} queries/day).\n\n"
            "The limit will reset tomorrow. Contact admin to increase the limit if needed.",
            parse_mode='Markdown'
        )
        return
    
    # Extract question
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text(
            "❓ **Please provide a question.**\n\n"
            "**Example:**\n"
            "`/kb What is our GDPR policy?`",
            parse_mode='Markdown'
        )
        return
    
    # Show "typing..." indicator
    await update.message.chat.send_action("typing")
    
    logger.info(f"Query from {user_name} (ID: {user_id}): {question}")
    
    try:
        # Query RAG pipeline
        result = rag.query(question)
        
        # Format response
        response = f"📚 **Knowledge Base Answer**\n\n{result['answer']}\n\n"
        
        # Add sources
        if result['sources']:
            response += "📎 **Sources:**\n"
            for src in result['sources'][:3]:  # Top 3 sources
                response += f"• `{src['file']}` (relevance: {src['relevance']})\n"
            response += "\n"
        
        # Add metrics
        response += f"⏱️ Retrieved in {result['total_latency_ms']:.0f}ms | Cost: €{result['cost_eur']:.4f}"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
        # Update stats
        stats.increment(user_id)
        
        logger.info(
            f"Response sent | Latency: {result['total_latency_ms']:.0f}ms | "
            f"Cost: €{result['cost_eur']:.4f} | User queries today: {stats.get_user_count(user_id)}"
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ **Error processing your question:**\n\n"
            f"`{str(e)[:200]}`\n\n"
            "Please try:\n"
            "• Rephrasing your question\n"
            "• Using simpler keywords\n"
            "• Contacting admin if the issue persists",
            parse_mode='Markdown'
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kb_stats command."""
    
    # Aggregate metrics
    total_queries = rag.metrics["queries_total"]
    total_cost = rag.metrics["cost_total_eur"]
    today_queries = stats.get_today_count()
    user_id = update.effective_user.id
    user_queries = stats.get_user_count(user_id)
    
    # Calculate latency percentiles
    latencies = rag.metrics["latency_history"]
    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies) // 2]
        p95 = latencies_sorted[int(len(latencies) * 0.95)] if len(latencies) > 20 else latencies_sorted[-1]
        avg = sum(latencies) / len(latencies)
    else:
        p50 = p95 = avg = 0
    
    # Index info
    index_info = ""
    if rag.index:
        built_at = datetime.fromisoformat(rag.index['built_at'])
        time_ago = datetime.now() - built_at
        hours_ago = int(time_ago.total_seconds() / 3600)
        
        index_info = f"""
**📚 Knowledge Base:**
├─ Documents: {rag.index['num_docs']}
├─ Chunks: {rag.index['num_chunks']}
└─ Last updated: {hours_ago}h ago
"""
    
    # Cost breakdown
    embed_cost = (rag.metrics["embedding_tokens"] / 1_000_000) * 0.05
    rerank_cost = rag.metrics["rerank_queries"] * 0.01
    gen_input_cost = (rag.metrics["generation_input_tokens"] / 1_000_000) * 0.05
    gen_output_cost = (rag.metrics["generation_output_tokens"] / 1_000_000) * 0.25
    
    response = f"""
📊 **Knowledge Base Statistics**

**📈 Usage (last 24h):**
├─ Total queries: {today_queries}
├─ Your queries: {user_queries}
├─ Avg response time: {avg:.0f}ms
├─ p50 latency: {p50:.0f}ms
├─ p95 latency: {p95:.0f}ms
└─ Daily limit: {today_queries}/{MAX_QUERIES_PER_DAY}

**💰 Costs (lifetime):**
├─ Total queries: {total_queries}
├─ Total cost: €{total_cost:.2f}
├─ Avg cost/query: €{total_cost/max(total_queries,1):.4f}
└─ Breakdown:
    ├─ Embeddings: €{embed_cost:.2f}
    ├─ Reranking: €{rerank_cost:.2f}
    └─ Generation: €{gen_input_cost + gen_output_cost:.2f}

{index_info}

**📊 Projected monthly cost:**
€{(total_cost/max(total_queries,1)) * MAX_QUERIES_PER_DAY * 30:.2f} (at current rate)

**🚀 Models:**
• Embed: {os.getenv('EMBED_MODEL')}
• Rerank: {os.getenv('RERANK_MODEL')}
• Chat: {os.getenv('CHAT_MODEL')}
"""
    
    await update.message.reply_text(response, parse_mode='Markdown')


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kb_update command (rebuild index)."""
    
    # Admin check (only configured chat ID can rebuild)
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        await update.message.reply_text(
            "❌ **Unauthorized.**\n\nOnly admin can rebuild the index.",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        "🔄 **Rebuilding knowledge base index...**\n\n"
        "This may take 1-2 minutes depending on document count.",
        parse_mode='Markdown'
    )
    
    try:
        # Rebuild index
        t0 = datetime.now()
        build_knowledge_base()
        elapsed = (datetime.now() - t0).total_seconds()
        
        # Reload index
        rag.load_index()
        
        await update.message.reply_text(
            f"✅ **Index rebuilt successfully**\n\n"
            f"├─ Build time: {elapsed:.1f}s\n"
            f"├─ Documents: {rag.index['num_docs']}\n"
            f"├─ Chunks: {rag.index['num_chunks']}\n"
            f"└─ Models: {rag.index['models']['embed']}, {rag.index['models']['rerank']}, {rag.index['models']['chat']}\n\n"
            f"Ready to serve queries! 🚀",
            parse_mode='Markdown'
        )
        
        logger.info(f"Index rebuilt by user {update.effective_user.first_name} in {elapsed:.1f}s")
        
    except Exception as e:
        logger.error(f"Error rebuilding index: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ **Error rebuilding index:**\n\n`{str(e)[:200]}`",
            parse_mode='Markdown'
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again or contact admin."
        )


def main():
    """Start the bot."""
    
    logger.info("🚀 Starting Clawdbot Knowledge Base...")
    
    # Load index
    if not rag.load_index():
        logger.warning("⚠️  Index not found. Building initial index...")
        try:
            build_knowledge_base()
            rag.load_index()
        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            logger.error("Add documents to ./knowledge-base/ and run: python3 rag_pipeline.py build")
            return
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("kb_help", help_command))
    application.add_handler(CommandHandler("kb", kb_command))
    application.add_handler(CommandHandler("kb_stats", stats_command))
    application.add_handler(CommandHandler("kb_update", update_command))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("=" * 60)
    logger.info(f"🤖 Bot username: @{application.bot.username if hasattr(application.bot, 'username') else 'N/A'}")
    logger.info(f"├─ Models:")
    logger.info(f"│  ├─ Embeddings: {os.getenv('EMBED_MODEL')}")
    logger.info(f"│  ├─ Reranking: {os.getenv('RERANK_MODEL')}")
    logger.info(f"│  └─ Chat: {os.getenv('CHAT_MODEL')}")
    logger.info(f"├─ Knowledge base: {rag.index['num_docs']} docs, {rag.index['num_chunks']} chunks")
    logger.info(f"└─ Daily query limit: {MAX_QUERIES_PER_DAY}")
    logger.info("=" * 60)
    logger.info("✅ Bot is running. Press Ctrl+C to stop.")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()