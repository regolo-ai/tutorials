"""Entrypoint CLI for Closed-Loop Secure Coding Agent.
Executes the interactive TUI.
"""

import sys
from tui import interactive_main_menu, run_full_closed_loop_flow


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive CLI mode
        run_full_closed_loop_flow(auto_mode=True)
    else:
        # Default interactive TUI mode
        interactive_main_menu()


if __name__ == "__main__":
    main()
