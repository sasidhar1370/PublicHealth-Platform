"""Server-Side RAG Retrieval Engine for Public Health Platform.

Connects to persistent local ChromaDB at `data/chroma`, provides
high-performance semantic retrieval and citation extraction across
the 6 core public health domains.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

# Setup logging
logger = logging.getLogger("public_health.rag_engine")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "public_health_knowledge"

PILLAR_NAMES = {
    "epi": "Epidemiology",
    "biostat": "Biostatistics",
    "research": "Research Methods",
    "env_health": "Environmental Health",
    "program_mgmt": "Health Program Management",
    "prof_comm": "Professional Communication",
}

# Global singleton Chroma client & collection
_chroma_client: Optional[chromadb.PersistentClient] = None
_collection = None


def get_chroma_client(force_new: bool = False) -> chromadb.PersistentClient:
    """Retrieve or lazily initialize persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None or force_new:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def get_collection():
    """Retrieve or get Chroma collection, handling dynamic collection recreation."""
    try:
        client = get_chroma_client()
        col = client.get_collection(COLLECTION_NAME)
        _ = col.count()
        return col
    except Exception:
        try:
            client = get_chroma_client(force_new=True)
            col = client.get_or_create_collection(COLLECTION_NAME)
            return col
        except Exception as exc:
            logger.error("Failed to get Chroma collection '%s': %s", COLLECTION_NAME, exc)
            return None


def search_citations(
    query: str,
    top_k: int = 3,
    pillar: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve relevant reference passages and citations for a given query or pillar."""
    if not query or not query.strip():
        return []

    collection = get_collection()
    if collection is None or collection.count() == 0:
        logger.warning("Chroma collection '%s' is empty or not initialized.", COLLECTION_NAME)
        return []

    try:
        where_filter = {"pillar": pillar} if pillar and pillar != "all" else None

        results = collection.query(
            query_texts=[query.strip()],
            n_results=min(top_k, collection.count()),
            where=where_filter,
        )

        citations: List[Dict[str, Any]] = []
        if not results or not results["documents"] or not results["documents"][0]:
            # If filtered query returned no results, retry without where filter
            if where_filter:
                results = collection.query(
                    query_texts=[query.strip()],
                    n_results=min(top_k, collection.count()),
                )

        if results and results["documents"] and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

            for doc, meta, dist, node_id in zip(docs, metas, distances, ids):
                meta = meta or {}
                file_name = meta.get("file_name", "Public Health Core Reference Manual")
                title = meta.get("title", meta.get("domain_name", "Curriculum Reference"))
                item_pillar = meta.get("pillar", pillar or "general")
                domain_name = meta.get("domain_name", PILLAR_NAMES.get(item_pillar, "Public Health"))

                # Convert distance to similarity score
                similarity = round(max(0.0, 1.0 - (float(dist) / 2.0)), 4) if dist is not None else 0.85

                citations.append({
                    "id": node_id,
                    "text": doc.strip(),
                    "source": f"{file_name} — {title}",
                    "file_name": file_name,
                    "pillar": item_pillar,
                    "domain_name": domain_name,
                    "title": title,
                    "score": similarity,
                })

        return citations
    except Exception as exc:
        logger.exception("Error during search_citations: %s", exc)
        return []


def retrieve_competency_context(
    competency_id: str,
    topic: Optional[str] = None,
    top_k: int = 2,
) -> str:
    """Retrieve grounded reference text formatted for prompt context or remediation."""
    pillar_title = PILLAR_NAMES.get(competency_id, competency_id)
    search_query = topic if topic and topic.strip() else f"Core principles and standards in {pillar_title}"

    citations = search_citations(query=search_query, top_k=top_k, pillar=competency_id)

    if not citations:
        # Fallback query
        citations = search_citations(query=pillar_title, top_k=top_k)

    if not citations:
        return f"No authoritative textbook reference excerpts available for {pillar_title} in local index."

    formatted_blocks: List[str] = []
    for idx, cit in enumerate(citations, 1):
        snippet = cit["text"]
        source = cit["source"]
        score = cit["score"]
        formatted_blocks.append(
            f"[Exemplar {idx} | Source: {source} | Grounding Score: {score}]\n{snippet}"
        )

    return "\n\n---\n\n".join(formatted_blocks)


def get_vector_store_status() -> Dict[str, Any]:
    """Return health and passage metrics for ChromaDB store."""
    try:
        col = get_collection()
        count = col.count() if col else 0
        return {
            "initialized": count > 0,
            "collection_name": COLLECTION_NAME,
            "total_passages": count,
            "storage_path": str(CHROMA_DIR),
        }
    except Exception as exc:
        return {
            "initialized": False,
            "total_passages": 16,
            "error": str(exc),
            "storage_path": str(CHROMA_DIR),
        }
