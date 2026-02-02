"""
MCP Server for IEEE 802.11 Vector Database.

Provides semantic search capabilities over IEEE 802.11be specification content
including sections, tables, and figures stored in ChromaDB.
"""

import logging
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (required for STDIO transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ieee80211-mcp")

# Initialize FastMCP server
mcp = FastMCP("ieee80211")

# Database configuration
DB_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "ieee_80211"


def get_embedding_function():
    """Get the sentence-transformers embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def get_collection():
    """Get the ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(DB_PATH))
    ef = get_embedding_function()
    return client.get_collection(COLLECTION_NAME, embedding_function=ef)


def format_result(doc: str, metadata: dict, distance: float) -> str:
    """Format a single search result as a readable string."""
    content_type = metadata.get("type", "unknown")
    lines = [f"[{content_type.upper()}] (relevance: {1 - distance:.2%})"]

    if content_type == "section":
        lines.append(f"Title: {metadata.get('title', 'N/A')}")
        lines.append(f"Level: {metadata.get('level', 'N/A')}")
    elif content_type == "table":
        lines.append(f"Caption: {metadata.get('caption', 'N/A')}")
    elif content_type == "figure":
        lines.append(f"Caption: {metadata.get('caption', 'N/A')}")
        lines.append(f"Image: {metadata.get('image_path', 'N/A')}")

    lines.append(f"Page: {metadata.get('page', 'N/A')}")
    lines.append(f"Content:\n{doc}")

    return "\n".join(lines)


@mcp.tool()
async def search_ieee80211(query: str, n_results: int = 5) -> str:
    """Search the IEEE 802.11be specification for relevant content.

    Performs semantic search across all sections, tables, and figures
    in the IEEE 802.11be (Wi-Fi 7) specification.

    Args:
        query: The search query (e.g., "EMLSR padding delay", "Multi-Link element")
        n_results: Number of results to return (default: 5, max: 20)
    """
    logger.info(f"Searching for: {query}")

    n_results = min(max(1, n_results), 20)  # Clamp between 1 and 20

    try:
        collection = get_collection()
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return "No results found for your query."

        formatted_results = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            formatted_results.append(f"--- Result {i + 1} ---")
            formatted_results.append(format_result(doc, meta, dist))

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error performing search: {str(e)}"


@mcp.tool()
async def search_sections(query: str, n_results: int = 5) -> str:
    """Search only the specification sections (text content).

    Use this when looking for explanatory text, definitions, or procedures
    in the IEEE 802.11be specification.

    Args:
        query: The search query
        n_results: Number of results to return (default: 5, max: 20)
    """
    logger.info(f"Searching sections for: {query}")

    n_results = min(max(1, n_results), 20)

    try:
        collection = get_collection()
        results = collection.query(
            query_texts=[query],
            n_results=n_results * 3,  # Get more to filter
            where={"type": "section"}
        )

        documents = results.get("documents", [[]])[0][:n_results]
        metadatas = results.get("metadatas", [[]])[0][:n_results]
        distances = results.get("distances", [[]])[0][:n_results]

        if not documents:
            return "No sections found for your query."

        formatted_results = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            formatted_results.append(f"--- Section {i + 1} ---")
            formatted_results.append(format_result(doc, meta, dist))

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error performing search: {str(e)}"


@mcp.tool()
async def search_tables(query: str, n_results: int = 5) -> str:
    """Search only the specification tables.

    Use this when looking for tabular data like encoding values,
    parameter definitions, or field mappings in the IEEE 802.11be specification.

    Args:
        query: The search query (e.g., "EMLSR padding delay encoding")
        n_results: Number of results to return (default: 5, max: 10)
    """
    logger.info(f"Searching tables for: {query}")

    n_results = min(max(1, n_results), 10)

    try:
        collection = get_collection()
        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2,
            where={"type": "table"}
        )

        documents = results.get("documents", [[]])[0][:n_results]
        metadatas = results.get("metadatas", [[]])[0][:n_results]
        distances = results.get("distances", [[]])[0][:n_results]

        if not documents:
            return "No tables found for your query."

        formatted_results = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            formatted_results.append(f"--- Table {i + 1} ---")
            formatted_results.append(format_result(doc, meta, dist))

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error performing search: {str(e)}"


@mcp.tool()
async def search_figures(query: str, n_results: int = 5) -> str:
    """Search only the specification figures.

    Use this when looking for diagrams, frame formats, or visual
    representations in the IEEE 802.11be specification.
    Returns figure captions and image file paths.

    Args:
        query: The search query (e.g., "Multi-Link element format")
        n_results: Number of results to return (default: 5, max: 10)
    """
    logger.info(f"Searching figures for: {query}")

    n_results = min(max(1, n_results), 10)

    try:
        collection = get_collection()
        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2,
            where={"type": "figure"}
        )

        documents = results.get("documents", [[]])[0][:n_results]
        metadatas = results.get("metadatas", [[]])[0][:n_results]
        distances = results.get("distances", [[]])[0][:n_results]

        if not documents:
            return "No figures found for your query."

        formatted_results = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            formatted_results.append(f"--- Figure {i + 1} ---")
            formatted_results.append(format_result(doc, meta, dist))

        return "\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error performing search: {str(e)}"


@mcp.tool()
async def get_database_stats() -> str:
    """Get statistics about the IEEE 802.11 database.

    Returns the count of sections, tables, and figures stored in the database.
    """
    logger.info("Getting database stats")

    try:
        collection = get_collection()
        all_docs = collection.get()

        metadatas = all_docs.get("metadatas", [])

        stats = {
            "total": len(metadatas),
            "sections": sum(1 for m in metadatas if m.get("type") == "section"),
            "tables": sum(1 for m in metadatas if m.get("type") == "table"),
            "figures": sum(1 for m in metadatas if m.get("type") == "figure"),
        }

        return f"""IEEE 802.11be Database Statistics:
- Total documents: {stats['total']}
- Sections: {stats['sections']}
- Tables: {stats['tables']}
- Figures: {stats['figures']}

Database path: {DB_PATH}"""

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return f"Error getting stats: {str(e)}"


def main():
    """Run the MCP server."""
    logger.info("Starting IEEE 802.11 MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
