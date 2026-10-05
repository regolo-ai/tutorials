import json
import sqlite3
from config import database_path
from embeddings import compute_vector, calculate_cosine_similarity


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    # initialize local relational and vector tables
    connection = get_connection()
    cursor = connection.cursor()

    # flat table for conventional baseline rag
    cursor.execute("""
    create table if not exists baseline_chunks (
        chunk_id text primary key,
        document_name text,
        chunk_index integer,
        content text,
        vector_json text
    );
    """)

    # hierarchical index: parent table storing thematic summaries
    cursor.execute("""
    create table if not exists parent_summaries (
        document_id text primary key,
        document_name text,
        title text,
        summary text,
        metadata_json text,
        vector_json text
    );
    """)

    # hierarchical index: child table storing granular sections with foreign key
    cursor.execute("""
    create table if not exists child_chunks (
        chunk_id text primary key,
        document_id text,
        section_title text,
        chunk_index integer,
        content text,
        vector_json text,
        foreign key(document_id) references parent_summaries(document_id)
    );
    """)

    connection.commit()
    connection.close()


def store_baseline_document(
    document_name: str, chunks: list[dict]
) -> list[str]:
    # store raw chunks in the flat baseline table
    connection = get_connection()
    cursor = connection.cursor()
    inserted_ids = []

    for index, chunk in enumerate(chunks):
        chunk_id = f"baseline_{document_name}_{index}"
        content = chunk.get("content", "")
        vector = compute_vector(content)
        cursor.execute(
            """
            insert or replace into baseline_chunks
            (chunk_id, document_name, chunk_index, content, vector_json)
            values (?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                document_name,
                index,
                content,
                json.dumps(vector),
            ),
        )
        inserted_ids.append(chunk_id)

    connection.commit()
    connection.close()
    return inserted_ids


def store_hierarchical_document(
    document_id: str,
    document_name: str,
    title: str,
    summary: str,
    metadata: dict,
    sections: list[dict],
) -> tuple[str, list[str]]:
    # store structured document with parent summary and child chunks
    connection = get_connection()
    cursor = connection.cursor()

    summary_vector = compute_vector(f"{title} {summary}")
    cursor.execute(
        """
        insert or replace into parent_summaries
        (document_id, document_name, title, summary, metadata_json, vector_json)
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            document_name,
            title,
            summary,
            json.dumps(metadata),
            json.dumps(summary_vector),
        ),
    )

    child_ids = []
    for index, section in enumerate(sections):
        chunk_id = f"{document_id}_part_{index}"
        section_title = section.get("section_title", f"section {index}")
        content = section.get("content", "")
        chunk_vector = compute_vector(f"{section_title} {content}")

        cursor.execute(
            """
            insert or replace into child_chunks
            (chunk_id, document_id, section_title, chunk_index, content, vector_json)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                document_id,
                section_title,
                index,
                content,
                json.dumps(chunk_vector),
            ),
        )
        child_ids.append(chunk_id)

    connection.commit()
    connection.close()
    return document_id, child_ids


def search_baseline(query: str, top_k: int = 2) -> list[dict]:
    # flat single-pass similarity search for baseline rag
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "select chunk_id, document_name, chunk_index, content, vector_json from baseline_chunks"
    )
    rows = cursor.fetchall()
    connection.close()

    query_vector = compute_vector(query)
    scored = []
    for row in rows:
        row_vector = json.loads(row["vector_json"])
        score = calculate_cosine_similarity(query_vector, row_vector)
        scored.append({
            "chunk_id": row["chunk_id"],
            "document_name": row["document_name"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "similarity": score,
        })

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]


def search_parent_summaries(query: str, top_k: int = 3) -> list[dict]:
    # high-level topic search across parent document summaries
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "select document_id, document_name, title, summary, metadata_json, vector_json from parent_summaries"
    )
    rows = cursor.fetchall()
    connection.close()

    query_vector = compute_vector(query)
    scored = []
    for row in rows:
        row_vector = json.loads(row["vector_json"])
        score = calculate_cosine_similarity(query_vector, row_vector)
        scored.append({
            "document_id": row["document_id"],
            "document_name": row["document_name"],
            "title": row["title"],
            "summary": row["summary"],
            "metadata": json.loads(row["metadata_json"]),
            "similarity": score,
        })

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]


def read_child_chunks_by_parent(
    document_id: str, query: str = "", top_k: int = 3
) -> list[dict]:
    # granular retrieval of child chunks belonging to a target parent
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        select chunk_id, document_id, section_title, chunk_index, content, vector_json
        from child_chunks
        where document_id = ?
        """,
        (document_id,),
    )
    rows = cursor.fetchall()
    connection.close()

    if not rows:
        return []

    if not query:
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "section_title": row["section_title"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
            }
            for row in rows[:top_k]
        ]

    query_vector = compute_vector(query)
    scored = []
    for row in rows:
        row_vector = json.loads(row["vector_json"])
        score = calculate_cosine_similarity(query_vector, row_vector)
        scored.append({
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "section_title": row["section_title"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "similarity": score,
        })

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]


def keyword_search_chunks(keyword: str, top_k: int = 3) -> list[dict]:
    # exact keyword and identifier search across all child sections
    connection = get_connection()
    cursor = connection.cursor()
    clean_keyword = f"%{keyword.lower()}%"
    cursor.execute(
        """
        select chunk_id, document_id, section_title, content
        from child_chunks
        where lower(content) like ? or lower(section_title) like ?
        limit ?
        """,
        (clean_keyword, clean_keyword, top_k),
    )
    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "section_title": row["section_title"],
            "content": row["content"],
        }
        for row in rows
    ]
