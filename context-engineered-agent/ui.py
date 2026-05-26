import shutil
import sys


class TerminalUI:
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "muted": "\033[2m",
        "blue": "\033[34m",
        "cyan": "\033[36m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "magenta": "\033[35m",
    }

    def __init__(self):
        self.use_color = sys.stdout.isatty()

    def _color(self, text, color):
        if not self.use_color:
            return text
        return f"{self.COLORS[color]}{text}{self.COLORS['reset']}"

    def _width(self):
        return min(88, shutil.get_terminal_size((88, 20)).columns)

    def header(self, title, subtitle=None):
        width = self._width()
        print()
        print(self._color("=" * width, "cyan"))
        print(self._color(title.upper(), "bold"))
        if subtitle:
            print(self._color(subtitle, "muted"))
        print(self._color("=" * width, "cyan"))

    def section(self, title):
        print()
        print(self._color(f"-- {title}", "blue"))

    def context_load(self, current_tokens, limit):
        ratio = min(1.0, current_tokens / max(1, limit))
        bar_width = 24
        filled = int(bar_width * ratio)
        bar = "#" * filled + "." * (bar_width - filled)
        color = "green" if ratio < 0.7 else "yellow" if ratio < 1 else "red"
        print(self._color(f"Context [{bar}] ~{current_tokens}/{limit} tokens", color))

    def thought(self, iteration, text):
        print(self._color(f"\nIteration {iteration} thought", "magenta"))
        print(f"  {text}")

    def tool_call(self, tool_name, args):
        print(self._color(f"\nTool call: {tool_name}", "cyan"))
        if args:
            print(self._color(f"  args: {args}", "muted"))

    def tool_result(self, result):
        preview = str(result)
        if len(preview) > 260:
            preview = preview[:257] + "..."
        print(self._color(f"  result: {preview}", "muted"))

    def guardrail(self, missing):
        print(self._color("\nGuardrail: final answer rejected", "yellow"))
        print(self._color(f"  Missing runtime steps: {', '.join(missing)}", "yellow"))

    def sub_agent(self, message):
        print(self._color(f"\n[Sub-agent] {message}", "blue"))

    def success(self, message):
        print(self._color(f"OK: {message}", "green"))

    def warning(self, message):
        print(self._color(f"Warning: {message}", "yellow"))

    def final_report(self, response):
        width = self._width()
        print()
        print(self._color("-" * width, "green"))
        print(self._color("FINAL AGENT REPORT", "bold"))
        print(response)
        print(self._color("-" * width, "green"))