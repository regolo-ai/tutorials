"""Deterministic assertions for Diagram_Design_Benchmark."""
from topology_extractor import (
    compress_routes_py,
    compress_sql_schema,
    compress_yaml_config,
    inspect_repo_compression,
    select_diagram_route,
)


def main():
    yaml_sample = "# comment\n" * 40 + "services:\n  api-gateway:\n    ports: ['8080:8080']\n    depends_on: [auth-svc]\n"
    y_res = compress_yaml_config(yaml_sample)
    assert "api-gateway" in y_res["body"]
    assert y_res["reduction_pct"] > 50.0

    sql_sample = "-- audit comment\n" * 40 + "CREATE TABLE invoices (id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id));\n"
    s_res = compress_sql_schema(sql_sample)
    assert "REFERENCES customers(id)" in s_res["body"]
    assert s_res["reduction_pct"] > 50.0

    py_sample = '"""' + ("compliance header\n" * 40) + '"""\n@app.post("/v1/charge")\ndef charge():\n    return ledger.append()\n'
    p_res = compress_routes_py(py_sample)
    assert "/v1/charge" in p_res["body"]
    assert p_res["reduction_pct"] > 60.0

    assert select_diagram_route({"category": "topology"}, True) == ("brick-complexity-pro", "none")
    assert select_diagram_route({"category": "svg_map"}, True) == ("qwen3.5-122b", "high")
    print("All diagram topology compression, FK extraction, and routing assertions passed.")


if __name__ == "__main__":
    main()
