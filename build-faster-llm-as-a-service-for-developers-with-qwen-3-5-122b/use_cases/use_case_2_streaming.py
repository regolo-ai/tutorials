"""Use case 2: streaming assistant for interactive chat UX."""

from __future__ import annotations

from regolo_client import RegoloClient


def run_single_stream(client: RegoloClient, system_prompt: str, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    chunks = []
    for piece in client.stream_chat_completion(messages=messages):
        chunks.append(piece)
    return "".join(chunks).strip()


def streaming_assistant_loop(client: RegoloClient, system_prompt: str) -> None:
    history = [{"role": "system", "content": system_prompt}]
    print("Assistant ready. Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break

        history.append({"role": "user", "content": user_input})
        print("Assistant: ", end="", flush=True)
        complete = ""
        for piece in client.stream_chat_completion(messages=history):
            complete += piece
            print(piece, end="", flush=True)

        print("\n")
        history.append({"role": "assistant", "content": complete})
