import re
import shutil
import textwrap

# ansi color definitions for beautiful terminal styling
color_reset = "\033[0m"
color_bold = "\033[1m"
color_dim = "\033[2m"

color_green = "\033[38;5;48m"
color_emerald_bg = "\033[48;5;22m\033[38;5;158m"
color_blue = "\033[38;5;75m"
color_blue_bg = "\033[48;5;18m\033[38;5;153m"
color_amber = "\033[38;5;214m"
color_amber_bg = "\033[48;5;58m\033[38;5;222m"
color_purple = "\033[38;5;141m"
color_cyan = "\033[38;5;86m"
color_gray = "\033[38;5;244m"


def clean_markdown_formatting(text: str) -> str:
    # strip raw markdown syntax like bold tags and heading hashes for clean terminal display
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"\|", " ", cleaned)
    cleaned = re.sub(r"-{3,}", "", cleaned)
    # clean multiple blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def format_card_box(
    title: str,
    content: str,
    border_color: str,
    title_color: str,
    max_width: int = 86,
) -> str:
    inner_width = max_width - 4
    top_line = f"{border_color}╭─ {title_color}{title} {border_color}{'─' * (inner_width - len(title) - 2)}╮{color_reset}"
    bottom_line = (
        f"{border_color}╰{'─' * (inner_width + 2)}╯{color_reset}"
    )

    lines = []
    lines.append(top_line)

    cleaned_content = clean_markdown_formatting(content)
    for paragraph in cleaned_content.splitlines():
        if not paragraph.strip():
            lines.append(f"{border_color}│{color_reset}{' ' * (inner_width + 2)}{border_color}│{color_reset}")
            continue

        wrapped_lines = textwrap.wrap(paragraph, width=inner_width)
        for line in wrapped_lines:
            padding = inner_width - len(line)
            lines.append(
                f"{border_color}│{color_reset}  {line}{' ' * padding}{border_color}│{color_reset}"
            )

    lines.append(bottom_line)
    return "\n".join(lines)


def render_tui_dashboard(
    question: str, baseline_data: dict, agentic_data: dict
) -> str:
    terminal_width = min(shutil.get_terminal_size((90, 24)).columns, 88)
    divider_line = f"{color_gray}{'═' * terminal_width}{color_reset}"

    output_parts = []
    output_parts.append("\n" + divider_line)
    header_banner = (
        f"{color_green}  REGOLO BENCHMARK EVALUATION DASHBOARD  {color_reset}"
    )
    output_parts.append(f"{color_bold}{header_banner}{color_reset}")
    output_parts.append(divider_line)

    # question card
    question_wrapped = textwrap.fill(
        question, width=terminal_width - 8
    )
    output_parts.append(
        f"\n{color_cyan}● target inquiry:{color_reset}\n  {color_bold}{question_wrapped}{color_reset}\n"
    )

    # side-by-side metrics overview
    output_parts.append(
        f"{color_amber}● comparative performance metrics:{color_reset}"
    )
    metrics_header = (
        f"  {'metric':<30} {'baseline pipeline':<24} {'hierarchical agentic':<24}"
    )
    output_parts.append(f"{color_dim}{metrics_header}{color_reset}")
    output_parts.append(f"  {color_gray}{'-' * (terminal_width - 4)}{color_reset}")

    row_latency = (
        f"  {'execution latency':<30} "
        f"{color_cyan}{baseline_data['duration_seconds']:>6.3f}s{color_reset}{' ' * 17} "
        f"{color_green}{agentic_data['duration_seconds']:>6.3f}s{color_reset}"
    )
    output_parts.append(row_latency)

    row_steps = (
        f"  {'retrieval steps':<30} "
        f"{color_gray}{'1 step':<24}{color_reset} "
        f"{color_green}{agentic_data['steps_count']} steps (typed tools){color_reset}"
    )
    output_parts.append(row_steps)

    row_chunks = (
        f"  {'chunks evaluated':<30} "
        f"{color_gray}{baseline_data['chunks_count']} flat chunks{color_reset}{' ' * 11} "
        f"{color_green}{agentic_data['unique_chunks_count']} granular chunks{color_reset}"
    )
    output_parts.append(row_chunks)

    coverage_baseline = (
        "partial / flat"
        if baseline_data["chunks_count"] <= 2
        else "standard"
    )
    coverage_agentic = "complete / two-level"
    row_coverage = (
        f"  {'context depth':<30} "
        f"{color_amber}{coverage_baseline:<24}{color_reset} "
        f"{color_green}{coverage_agentic:<24}{color_reset}"
    )
    output_parts.append(row_coverage)
    output_parts.append(f"  {color_gray}{'-' * (terminal_width - 4)}{color_reset}\n")

    # baseline answer card in amber/blue
    baseline_box = format_card_box(
        title="baseline output: single-pass flat retrieval",
        content=baseline_data["answer"],
        border_color=color_blue,
        title_color=color_blue,
        max_width=terminal_width,
    )
    output_parts.append(baseline_box + "\n")

    # agentic answer card in vibrant emerald
    agentic_box = format_card_box(
        title="agentic rag output: hierarchical tool reasoning (brick-complexity-pro)",
        content=agentic_data["answer"],
        border_color=color_green,
        title_color=color_green,
        max_width=terminal_width,
    )
    output_parts.append(agentic_box + "\n")

    # architectural diagnosis box in purple
    diagnosis_body = (
        "architectural diagnosis:\n"
        "1. baseline failure mode: flat vector search maps query tokens to nearest individual chunks, "
        "frequently missing historical revisions and cross-document exceptions.\n\n"
        "2. hierarchical agentic advantage: the controller first navigates high-level topic summaries "
        "to discover all candidate parent files, then uses typed tools to retrieve granular section blocks with verifiable citations."
    )
    diagnosis_box = format_card_box(
        title="architectural analysis: why hierarchical agency wins",
        content=diagnosis_body,
        border_color=color_purple,
        title_color=color_purple,
        max_width=terminal_width,
    )
    output_parts.append(diagnosis_box)
    output_parts.append(divider_line + "\n")

    return "\n".join(output_parts)
