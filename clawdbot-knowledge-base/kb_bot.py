#!/usr/bin/env python3
"""
Clawdbot Knowledge Base - Main Entry Point
Production-ready knowledge bot using Regolo EU GPUs
"""

import sys
from telegram_handler import main

if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("🚀 Clawdbot Knowledge Base")
        print("📡 Powered by Regolo EU GPUs")
        print("="*60 + "\n")
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
