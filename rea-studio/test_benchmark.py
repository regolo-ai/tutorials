"""Deterministic assertions for REA_Reverse_Engineering_Benchmark."""
import json
from rea_filter import filter_binary_symbol_table, filter_electron_ipc_dump, select_rea_route


def main():
    ipc_sample = json.dumps(
        {
            "bundle": "app.asar",
            "ipc_channels": [
                {"channel": f"ui:theme:hover_{i}", "scope": "renderer_ui"} for i in range(120)
            ]
            + [{"channel": "ipc:vault:unlock", "scope": "preload_bridge", "handler": "unlockVaultSqlite"}],
        }
    )
    ipc_res = filter_electron_ipc_dump(ipc_sample)
    assert "ipc:vault:unlock" in ipc_res["body"]
    assert ipc_res["reduction_pct"] > 80.0

    sym_sample = json.dumps(
        {
            "binary": "syncd-linux-amd64",
            "symbols": [
                {"name": f"runtime.gcMarkTinyAllocs_{i}", "module": "go_runtime"} for i in range(120)
            ]
            + [{"name": "crypto_keystore.DeriveArgon2idKey", "module": "crypto_keystore", "kdf_rounds": 4}],
        }
    )
    sym_res = filter_binary_symbol_table(sym_sample)
    assert "DeriveArgon2idKey" in sym_res["body"]
    assert sym_res["reduction_pct"] > 80.0

    assert select_rea_route({"category": "triage"}, True) == ("brick-complexity-pro", "none")
    assert select_rea_route({"category": "reconstruct"}, True) == ("qwen3.5-122b", "high")
    print("All REA IPC filtering, binary symbol sieve, and routing assertions passed.")


if __name__ == "__main__":
    main()
