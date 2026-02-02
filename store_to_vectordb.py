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


def store_to_vectordb(json_path: str, db_path: str = "./chroma_db") -> chromadb.Collection:
    """
    Load extracted data from JSON and store in ChromaDB.

    Args:
        json_path: Path to the sections_output.json file
        db_path: Path for the persistent ChromaDB database

    Returns:
        The ChromaDB collection
    """
    # Load extracted data
    with open(json_path) as f:
        data = json.load(f)

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
        metadata={"description": "IEEE 802.11be specification content"},
        embedding_function=ef
    )

    documents = []
    metadatas = []
    ids = []

    # Add sections
    for i, section in enumerate(data.get("sections", [])):
        text = section.get("text", "")
        if text and text.strip():  # Skip empty sections
            documents.append(text)
            metadatas.append({
                "type": "section",
                "title": section.get("section_title", ""),
                "level": section.get("level", 0),
                "page": section.get("page", 0)
            })
            ids.append(f"section_{i}")

    # Add tables (markdown content)
    for i, table in enumerate(data.get("tables", [])):
        content = table.get("content", "")
        if content and content.strip():
            documents.append(content)
            metadatas.append({
                "type": "table",
                "caption": table.get("caption", ""),
                "page": table.get("page", 0)
            })
            ids.append(f"table_{i}")

    # Add figures (caption only, image referenced by path in metadata)
    for i, figure in enumerate(data.get("figures", [])):
        caption = figure.get("caption", "")
        if caption and caption.strip():
            documents.append(caption)
            metadatas.append({
                "type": "figure",
                "caption": caption,
                "page": figure.get("page", 0),
                "image_path": figure.get("image_path", "")
            })
            ids.append(f"figure_{i}")

    # Store in ChromaDB
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    # Print summary
    section_count = sum(1 for m in metadatas if m["type"] == "section")
    table_count = sum(1 for m in metadatas if m["type"] == "table")
    figure_count = sum(1 for m in metadatas if m["type"] == "figure")

    print(f"Stored {len(documents)} items in ChromaDB:")
    print(f"  - Sections: {section_count}")
    print(f"  - Tables: {table_count}")
    print(f"  - Figures: {figure_count}")
    print(f"Database path: {db_path}")

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
    parser.add_argument("--json", default="sections_output.json", help="Path to JSON file")
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
        # Store data
        store_to_vectordb(args.json, args.db)

        # Run optional query
        if args.query:
            print(f"\nSearching for: {args.query}")
            results = search(args.query, n_results=args.n, db_path=args.db)
            print_results(results)
