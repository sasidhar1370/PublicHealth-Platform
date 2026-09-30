"""Server-Side Ingestion Pipeline for Public Health Platform.

Reads curriculum textbooks and reference documents from `textbooks/`,
chunks them by section and semantic boundaries,
and populates the persistent ChromaDB vector store at `data/chroma`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEXTBOOKS_DIR = PROJECT_ROOT / "textbooks"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "public_health_knowledge"

# Setup logging
logger = logging.getLogger("public_health.ingest")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

PILLAR_MAPPINGS = {
    "epidemiology": "epi",
    "biostatistics": "biostat",
    "research methods": "research",
    "environmental health": "env_health",
    "program management": "program_mgmt",
    "professional communication": "prof_comm",
}


def parse_and_chunk_textbook(file_path: Path) -> List[Dict[str, Any]]:
    """Parse textbook or curriculum reference file into thematic chunks with domain tags."""
    if file_path.suffix.lower() == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            content = "\n\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception as exc:
            logger.error("Failed to parse PDF %s: %s", file_path, exc)
            content = ""
    else:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.error("Failed to read text file %s: %s", file_path, exc)
            content = ""

    if not content.strip():
        return []

    # Check for major divider, otherwise split on headers or large blank lines
    if "================================================================================" in content:
        sections = content.split("================================================================================")
    elif "\n## " in content or "\n# " in content:
        import re
        sections = re.split(r"\n(?=#{1,3}\s)", content)
    else:
        sections = [content]

    chunks: List[Dict[str, Any]] = []
    chunk_counter = 1

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # Detect pillar from section title
        pillar = "general"
        domain_name = "Core Public Health"
        lines = sec.splitlines()
        first_lines = " ".join(lines[:4]).lower()

        for key, p_id in PILLAR_MAPPINGS.items():
            if key in first_lines:
                pillar = p_id
                domain_name = key.title()
                break

        # Sub-divide by subsections (e.g., 1.1, 1.2, etc.) or paragraphs
        subsections = sec.split("\n\n")
        current_block: List[str] = []
        current_title = domain_name

        for sub in subsections:
            sub = sub.strip()
            if not sub:
                continue

            if sub.startswith("SECTION ") or sub.startswith("# "):
                current_title = sub.replace("#", "").strip()
                continue

            # If subsection starts with a header or block is growing
            if any(sub.startswith(f"{i}.") for i in range(1, 10)) or len(current_block) > 2 or sum(len(b) for b in current_block) > 1000:
                if current_block:
                    text_block = "\n\n".join(current_block).strip()
                    if text_block and len(text_block) > 40:
                        chunks.append({
                            "id": f"{file_path.stem}_{chunk_counter}",
                            "text": text_block,
                            "metadata": {
                                "file_name": file_path.name,
                                "pillar": pillar,
                                "domain_name": domain_name,
                                "title": current_title,
                                "chunk_index": chunk_counter,
                            },
                        })
                        chunk_counter += 1
                    current_block = []

            current_block.append(sub)

        if current_block:
            text_block = "\n\n".join(current_block).strip()
            if text_block and len(text_block) > 40:
                chunks.append({
                    "id": f"{file_path.stem}_{chunk_counter}",
                    "text": text_block,
                    "metadata": {
                        "file_name": file_path.name,
                        "pillar": pillar,
                        "domain_name": domain_name,
                        "title": current_title,
                        "chunk_index": chunk_counter,
                    },
                })
                chunk_counter += 1

    return chunks


def ingest_textbooks(
    textbooks_dir: Optional[Path] = None,
    chroma_dir: Optional[Path] = None,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Read all curriculum reference documents and persist into ChromaDB."""
    target_textbooks = textbooks_dir or TEXTBOOKS_DIR
    target_chroma = chroma_dir or CHROMA_DIR

    target_textbooks.mkdir(parents=True, exist_ok=True)
    target_chroma.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to persistent ChromaDB at %s...", target_chroma)
    client = chromadb.PersistentClient(path=str(target_chroma))

    # Reset or get collection
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(collection_name)

    # Read all text and pdf files from textbooks/
    text_files = (
        list(target_textbooks.glob("*.txt"))
        + list(target_textbooks.glob("*.md"))
        + list(target_textbooks.glob("*.pdf"))
    )
    logger.info("Found %d curriculum text files in %s", len(text_files), target_textbooks)

    all_chunks: List[Dict[str, Any]] = []
    for tf in text_files:
        chunks = parse_and_chunk_textbook(tf)
        all_chunks.extend(chunks)

    if not all_chunks:
        logger.warning("No chunks generated. Verify that %s contains curriculum text files.", target_textbooks)
        return 0

    # Add to Chroma
    ids = [c["id"] for c in all_chunks]
    documents = [c["text"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    logger.info("Indexing %d semantic chunks into ChromaDB collection '%s'...", len(all_chunks), collection_name)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info(
        "Successfully indexed %d chunks across %d documents into '%s'.",
        len(all_chunks),
        len(text_files),
        collection_name,
    )
    return len(all_chunks)


def run_ingestion(
    textbooks_dir: Optional[Path] = None,
    chroma_dir: Optional[Path] = None,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Convenience entry point for triggering curriculum ingestion."""
    return ingest_textbooks(
        textbooks_dir=textbooks_dir,
        chroma_dir=chroma_dir,
        collection_name=collection_name,
    )


if __name__ == "__main__":
    logger.info("Starting Public Health curriculum ingestion pipeline...")
    try:
        count = ingest_textbooks()
        print("\n=======================================================")
        print(f"[OK] INGESTION COMPLETE: {count} Chunks Indexed")
        print(f"Collection: '{COLLECTION_NAME}'")
        print(f"Storage Path: {CHROMA_DIR}")
        print("=======================================================\n")
    except Exception as exc:
        logger.exception("Ingestion failed: %s", exc)
        sys.exit(1)
