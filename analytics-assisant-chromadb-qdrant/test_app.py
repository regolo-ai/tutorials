import json
import os
import pytest
from app import (
    search_company_knowledge,
    query_activation_metrics,
    create_crm_followup_list,
    load_data_file,
    DATA_DOCUMENTS,
)

def test_knowledge_tool_returns_source():
    out=search_company_knowledge.invoke({"question":"What does activation rate mean?"})
    assert "metrics_glossary.md" in out

def test_metrics_tool_calculates_rate():
    rows=json.loads(query_activation_metrics.invoke({"week":"2026-W29"}))
    assert next(x for x in rows if x["segment"]=="Self-serve")["activation_rate"] == 0.3

def test_crm_tool_is_non_destructive():
    out=json.loads(create_crm_followup_list.invoke({"name":"Activation recovery","segment":"Self-serve","reason":"WoW decline"}))
    assert out["status"] == "created"
    assert out["requires_human_approval_for_outreach"] is True


def test_load_data_file_missing_path():
    with pytest.raises(ValueError):
        load_data_file("")


def test_load_data_file_not_found():
    with pytest.raises(ValueError):
        load_data_file("/nonexistent/file.csv")


def test_load_data_file_unsupported_extension(tmp_path):
    p = tmp_path / "data.json"
    p.write_text("{}")
    with pytest.raises(ValueError):
        load_data_file(str(p))


def test_load_data_file_csv(tmp_path):
    p = tmp_path / "metrics.csv"
    p.write_text("segment,signups,activated\nSelf-serve,130,39\nSales-led,42,29\n", encoding="utf-8")
    DATA_DOCUMENTS.clear()
    docs = load_data_file(str(p))
    assert len(docs) == 2
    assert docs[0].metadata["source"] == "metrics.csv"
    assert "Self-serve" in docs[0].page_content
    DATA_DOCUMENTS.clear()


def test_load_data_file_txt(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("Activation target is 40% for self-serve.", encoding="utf-8")
    DATA_DOCUMENTS.clear()
    docs = load_data_file(str(p))
    assert len(docs) == 1
    assert "Activation target" in docs[0].page_content
    DATA_DOCUMENTS.clear()


def test_load_data_file_empty_csv(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_data_file(str(p))


def test_load_data_file_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["segment", "signups", "activated"])
    ws.append(["Self-serve", 130, 39])
    p = tmp_path / "data.xlsx"
    wb.save(str(p))
    DATA_DOCUMENTS.clear()
    docs = load_data_file(str(p))
    assert len(docs) == 1
    assert "Self-serve" in docs[0].page_content
    DATA_DOCUMENTS.clear()
