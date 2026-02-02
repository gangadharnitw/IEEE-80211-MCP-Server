"""
Store extracted IEEE 802.11 content (sections, tables, figures) into ChromaDB for semantic search.
Uses sentence-transformers for embeddings (compatible with Python 3.14).
"""

import chromadb
from chromadb.utils import embedding_functions
import json
import argparse
from pathlib import Path


def get_embedding_function():
    """Get a sentence-transformers based embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def store_to_vectordb(json_paths: list, db_path: str = "./chroma_db") -> chromadb.Collection:
    """
    Load extracted data from one or more JSON files and store in ChromaDB.

    Args:
        json_paths: List of paths to JSON files (e.g., ["80211be_output.json", "80211bn_output.json"])
        db_path: Path for the persistent ChromaDB database

    Returns:
        The ChromaDB collection
    """
    # Initialize ChromaDB with persistent storage
    client = chromadb.PersistentClient(path=db_path)

    # Get embedding function
    ef = get_embedding_function()

    # Get or create collection (delete if exists for clean re-runs)
    try:
        client.delete_collection(name="ieee_80211")
        print("Deleted existing collection for clean re-run")
    except Exception:
        pass  # Collection doesn't exist, that's fine

    collection = client.create_collection(
        name="ieee_80211",
        metadata={"description": "IEEE 802.11 specification content (multi-spec)"},
        embedding_function=ef
    )

    documents = []
    metadatas = []
    ids = []
    spec_counts = {}

    # Process each JSON file
    for json_path in json_paths:
        print(f"\nProcessing: {json_path}")
        with open(json_path) as f:
            data = json.load(f)

        # Get spec identifier from JSON metadata or filename
        spec = data.get("spec", "")
        if not spec:
            # Try to infer from filename (e.g., "80211be_output.json" -> "80211be")
            filename = Path(json_path).stem
            if filename.endswith("_output"):
                spec = filename.replace("_output", "")
            else:
                spec = filename

        spec_name = data.get("spec_name", f"IEEE 802.11 ({spec})")
        print(f"  Spec: {spec} ({spec_name})")

        if spec not in spec_counts:
            spec_counts[spec] = {"sections": 0, "tables": 0, "figures": 0}

        # Add sections
        for i, section in enumerate(data.get("sections", [])):
            text = section.get("text", "")
            if text and text.strip():
                documents.append(text)
                metadatas.append({
                    "type": "section",
                    "spec": spec,
                    "spec_name": spec_name,
                    "title": section.get("section_title", ""),
                    "level": section.get("level", 0),
                    "page": section.get("page", 0)
                })
                ids.append(f"{spec}_section_{i}")
                spec_counts[spec]["sections"] += 1

        # Add tables (markdown content)
        for i, table in enumerate(data.get("tables", [])):
            content = table.get("content", "")
            if content and content.strip():
                documents.append(content)
                metadatas.append({
                    "type": "table",
                    "spec": spec,
                    "spec_name": spec_name,
                    "caption": table.get("caption", ""),
                    "page": table.get("page", 0)
                })
                ids.append(f"{spec}_table_{i}")
                spec_counts[spec]["tables"] += 1

        # Add figures (caption only, image referenced by path in metadata)
        for i, figure in enumerate(data.get("figures", [])):
            caption = figure.get("caption", "")
            if caption and caption.strip():
                documents.append(caption)
                metadatas.append({
                    "type": "figure",
                    "spec": spec,
                    "spec_name": spec_name,
                    "caption": caption,
                    "page": figure.get("page", 0),
                    "image_path": figure.get("image_path", "")
                })
                ids.append(f"{spec}_figure_{i}")
                spec_counts[spec]["figures"] += 1

    # Store in ChromaDB
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    # Print summary
    print(f"\n{'='*50}")
    print(f"Stored {len(documents)} items in ChromaDB:")
    for spec, counts in spec_counts.items():
        total = sum(counts.values())
        print(f"\n  [{spec}] {total} items:")
        print(f"    - Sections: {counts['sections']}")
        print(f"    - Tables: {counts['tables']}")
        print(f"    - Figures: {counts['figures']}")
    print(f"\nDatabase path: {db_path}")

    return collection


def search(query: str, n_results: int = 3, db_path: str = "./chroma_db") -> dict:
    """
    Search the ChromaDB collection for relevant content.

    Args:
        query: The search query
        n_results: Number of results to return
        db_path: Path to the ChromaDB database

    Returns:
        Query results with documents, metadatas, and distances
    """
    client = chromadb.PersistentClient(path=db_path)
    ef = get_embedding_function()
    collection = client.get_collection("ieee_80211", embedding_function=ef)

    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    return results


def print_results(results: dict) -> None:
    """Pretty print search results."""
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        print(f"\n--- Result {i+1} (distance: {dist:.4f}) ---")
        print(f"Type: {meta.get('type', 'unknown')}")

        if meta.get('type') == 'section':
            print(f"Title: {meta.get('title', 'N/A')}")
            print(f"Level: {meta.get('level', 'N/A')}")
        elif meta.get('type') == 'table':
            print(f"Caption: {meta.get('caption', 'N/A')}")
        elif meta.get('type') == 'figure':
            print(f"Caption: {meta.get('caption', 'N/A')}")
            print(f"Image: {meta.get('image_path', 'N/A')}")

        print(f"Page: {meta.get('page', 'N/A')}")
        print(f"Content preview: {doc[:200]}..." if len(doc) > 200 else f"Content: {doc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store IEEE 802.11 content in ChromaDB")
    parser.add_argument(
        "--json",
        nargs="+",
        default=["sections_output.json"],
        help="Path(s) to JSON file(s). Can specify multiple files for multi-spec support."
    )
    parser.add_argument("--db", default="./chroma_db", help="Path for ChromaDB")
    parser.add_argument("--query", help="Optional: run a search query after storing")
    parser.add_argument("--search-only", action="store_true", help="Only search, don't store")
    parser.add_argument("-n", type=int, default=3, help="Number of results for search")

    args = parser.parse_args()

    if args.search_only:
        if args.query:
            print(f"Searching for: {args.query}")
            results = search(args.query, n_results=args.n, db_path=args.db)
            print_results(results)
        else:
            print("Error: --query required with --search-only")
    else:
        # Store data from all JSON files
        store_to_vectordb(args.json, args.db)

        # Run optional query
        if args.query:
            print(f"\nSearching for: {args.query}")
            results = search(args.query, n_results=args.n, db_path=args.db)
            print_results(results)
