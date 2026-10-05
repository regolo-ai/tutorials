import sys
from pathlib import Path
from config import (
    sample_data_dir,
    regolo_model_name,
    regolo_api_key,
    regolo_base_url,
)
from ingest import ingest_path
from compare import run_comparison
from storage import init_database

banner_green = "\033[1;32m"
reset_color = "\033[0m"

regolo_ascii = f"""{banner_green}
██████╗ ███████╗ ██████╗  ██████╗ ██╗      ██████╗ 
██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██║     ██╔═══██╗
██████╔╝█████╗  ██║  ███╗██║   ██║██║     ██║   ██║
██╔══██╗██╔══╝  ██║   ██║██║   ██║██║     ██║   ██║
██║  ██║███████╗╚██████╔╝╚██████╔╝███████╗╚██████╔╝
╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ 
{reset_color}"""


def print_banner() -> None:
    print(regolo_ascii)
    print("agentic rag architecture with hierarchical index retrieval:")
    print(f"selected endpoint: {regolo_model_name} ({regolo_base_url})\n")


def interactive_menu() -> None:
    print_banner()
    init_database()

    while True:
        print("available lab options:")
        print(
            "1. ingest documents from a custom path for both storage representations"
        )
        print(
            "2. run empirical comparison between baseline and hierarchical agentic rag"
        )
        print("3. run end-to-end benchmark with included sample policy files")
        print("4. exit program")

        choice = input("\nenter option number: ").strip()

        if choice == "1":
            target_path = input(
                "enter relative or absolute path of documents to process: "
            ).strip()
            if not target_path:
                print("warning: empty or invalid path.\n")
                continue
            try:
                result = ingest_path(target_path)
                print(
                    f"\ningestion completed successfully: stored {result['documents_count']} documents."
                )
                print(
                    f"flat baseline chunks created: {result['total_baseline_chunks']} items."
                )
                print(
                    f"hierarchical child chunks created: {result['total_child_chunks']} granular items linked to parent summaries.\n"
                )
            except Exception as error:
                print(f"error during document ingestion: {error}\n")

        elif choice == "2":
            default_query = "compare the 2026 refund policy with 2025 and explain which exceptions changed."
            user_query = input(
                f"enter evaluation inquiry (press enter for '{default_query}'): "
            ).strip()
            query_to_run = user_query if user_query else default_query

            print(
                f"\nexecuting empirical comparison for inquiry: {query_to_run}"
            )
            comparison = run_comparison(question=query_to_run)
            print(comparison["summary_report"])

        elif choice == "3":
            print(
                f"\nstarting automatic ingestion of sample policy directory: {sample_data_dir}"
            )
            ingest_result = ingest_path(str(sample_data_dir))
            print(
                f"sample documents indexed: {ingest_result['documents_count']} files."
            )

            test_query = "compare the 2026 refund policy with 2025 and explain which exceptions changed."
            print(f"running verification benchmark with query: {test_query}")
            comparison = run_comparison(question=test_query)
            print(comparison["summary_report"])

        elif choice in ["4", "exit", "quit", "q"]:
            print("session closed.")
            break
        else:
            print("invalid selection: enter a number between 1 and 4.\n")


def main() -> None:
    args_list = sys.argv[1:]

    sample_test = "--sample-test" in args_list
    target_path = ""
    query_text = ""
    api_key_param = ""

    if "--path" in args_list:
        idx = args_list.index("--path")
        if idx + 1 < len(args_list):
            target_path = args_list[idx + 1]

    if "--query" in args_list:
        idx = args_list.index("--query")
        if idx + 1 < len(args_list):
            query_text = args_list[idx + 1]

    if "--api-key" in args_list:
        idx = args_list.index("--api-key")
        if idx + 1 < len(args_list):
            api_key_param = args_list[idx + 1]

    if sample_test:
        print_banner()
        print(f"indexing sample directory: {sample_data_dir}")
        ingest_path(str(sample_data_dir))
        sample_q = (
            query_text
            if query_text
            else "compare the 2026 refund policy with 2025 and explain which exceptions changed."
        )
        result = run_comparison(question=sample_q, api_key=api_key_param)
        print("\n" + result["summary_report"])
        return

    if target_path:
        print_banner()
        print(f"starting ingestion from specified path: {target_path}")
        result_ingest = ingest_path(target_path)
        print(
            f"ingestion completed: {result_ingest['documents_count']} documents stored."
        )
        if query_text:
            print(f"running comparison for inquiry: {query_text}")
            result_compare = run_comparison(
                question=query_text, api_key=api_key_param
            )
            print("\n" + result_compare["summary_report"])
        return

    # launch interactive terminal menu when no direct flags are provided
    interactive_menu()


if __name__ == "__main__":
    main()
