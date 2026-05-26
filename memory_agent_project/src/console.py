import os
import shutil


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def supports_color() -> bool:
    return os.getenv("NO_COLOR") is None and os.getenv("TERM") != "dumb"


def paint(text: str, *styles: str) -> str:
    if not supports_color():
        return text
    return "".join(styles) + text + Style.RESET


def terminal_width(default: int = 78) -> int:
    return shutil.get_terminal_size((default, 20)).columns


def rule(title: str = "", color: str = Style.CYAN) -> None:
    width = min(terminal_width(), 96)
    if title:
        label = f" {title} "
        side = max((width - len(label)) // 2, 2)
        line = "=" * side + label + "=" * (width - side - len(label))
    else:
        line = "=" * width
    print(paint(line, color, Style.BOLD))


def panel(title: str, lines: list[str], color: str = Style.CYAN) -> None:
    width = min(terminal_width(), 96)
    border = "=" * width
    print("\n" + paint(border, color, Style.BOLD))
    print(paint(f"  {title}", color, Style.BOLD))
    print(paint(border, color, Style.BOLD))
    for line in lines:
        print(f"  {line}")
    print()


def step(number: int, title: str, detail: str | None = None) -> None:
    prefix = paint(f"[{number}]", Style.BLUE, Style.BOLD)
    print(f"\n{prefix} {paint(title, Style.BOLD)}")
    if detail:
        print(paint(f"    {detail}", Style.DIM))


def info(message: str) -> None:
    print(f"  {paint('INFO', Style.CYAN, Style.BOLD)} {message}")


def success(message: str) -> None:
    print(f"  {paint('OK', Style.GREEN, Style.BOLD)} {message}")


def warning(message: str) -> None:
    print(f"  {paint('WARN', Style.YELLOW, Style.BOLD)} {message}")


def error(message: str) -> None:
    print(f"  {paint('ERR', Style.RED, Style.BOLD)} {message}")


def key_value(key: str, value: str) -> None:
    print(f"  {paint(key + ':', Style.BOLD)} {value}")


def file_list(title: str, files: list[str]) -> None:
    if not files:
        return
    print(f"  {paint(title + ':', Style.BOLD)}")
    for file in files:
        print(f"    - {file}")