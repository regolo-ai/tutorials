"""
Test suite for Regolo API integration
Run with: python test_regolo.py
"""

import os
from regolo_client import regolo_chat


def test_basic_completion():
    """Test basic chat completion"""
    print("\n[TEST 1] Basic completion...")

    response = regolo_chat(
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello from Regolo!' and nothing else."},
        ],
        temperature=0.1
    )

    print(f"Response: {response}")
    assert len(response) > 0, "Response should not be empty"
    print("✓ PASSED")


def test_technical_query():
    """Test technical reasoning"""
    print("\n[TEST 2] Technical query...")

    response = regolo_chat(
        [
            {
                "role": "system",
                "content": "You are an expert software architect."
            },
            {
                "role": "user",
                "content": "Explain in 2 sentences why OpenAI-compatible APIs are useful for AI agents."
            },
        ],
        temperature=0.2
    )

    print(f"Response: {response}")
    assert "API" in response or "api" in response, "Response should mention API"
    print("✓ PASSED")


def test_multi_turn():
    """Test multi-turn conversation"""
    print("\n[TEST 3] Multi-turn conversation...")

    messages = [
        {"role": "system", "content": "You are a friendly assistant."},
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you, Alice!"},
        {"role": "user", "content": "What's my name?"},
    ]

    response = regolo_chat(messages, temperature=0.1)

    print(f"Response: {response}")
    assert "Alice" in response or "alice" in response, "Should remember the name"
    print("✓ PASSED")


def test_temperature_variation():
    """Test different temperature settings"""
    print("\n[TEST 4] Temperature variation...")

    prompt = [
        {"role": "user", "content": "Generate a creative startup name for an AI company."}
    ]

    # Low temperature (deterministic)
    response_low = regolo_chat(prompt, temperature=0.1)
    print(f"Low temp (0.1): {response_low}")

    # High temperature (creative)
    response_high = regolo_chat(prompt, temperature=0.9)
    print(f"High temp (0.9): {response_high}")

    print("✓ PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("Regolo API Integration Test Suite")
    print("=" * 60)

    # Check API key
    if not os.environ.get("REGOLO_API_KEY"):
        print("\n❌ ERROR: REGOLO_API_KEY not set")
        print("Set it with: export REGOLO_API_KEY=your_key_here")
        exit(1)

    try:
        test_basic_completion()
        test_technical_query()
        test_multi_turn()
        test_temperature_variation()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
