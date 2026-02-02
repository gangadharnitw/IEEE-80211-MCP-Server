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
    spec = metadata.get("spec", "")
    spec_label = f" [{spec}]" if spec else ""
    lines = [f"[{content_type.upper()}]{spec_label} (relevance: {1 - distance:.2%})"]

    if content_type == "section":
        lines.append(f"Title: {metadata.get('title', 'N/A')}")
        lines.append(f"Level: {metadata.get('level', 'N/A')}")
    elif content_type == "table":
        lines.append(f"Caption: {metadata.get('caption', 'N/A')}")
    elif content_type == "figure":
        lines.append(f"Caption: {metadata.get('caption', 'N/A')}")
        lines.append(f"Image: {metadata.get('image_path', 'N/A')}")

    if spec:
        lines.append(f"Spec: {metadata.get('spec_name', spec)}")
    lines.append(f"Page: {metadata.get('page', 'N/A')}")
    lines.append(f"Content:\n{doc}")

    return "\n".join(lines)


@mcp.tool()
async def search_ieee80211(query: str, n_results: int = 5, spec: str = None) -> str:
    """Search IEEE 802.11 specifications for relevant content.

    Performs semantic search across all sections, tables, and figures
    in the indexed IEEE 802.11 specifications.

    Args:
        query: The search query (e.g., "EMLSR padding delay", "Multi-Link element")
        n_results: Number of results to return (default: 5, max: 20)
        spec: Optional spec filter (e.g., "80211be", "80211bn"). If not provided, searches all specs.
    """
    logger.info(f"Searching for: {query}" + (f" in spec={spec}" if spec else ""))

    n_results = min(max(1, n_results), 20)  # Clamp between 1 and 20

    try:
        collection = get_collection()

        # Build where filter if spec is provided
        where_filter = {"spec": spec} if spec else None

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
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
async def search_sections(query: str, n_results: int = 5, spec: str = None) -> str:
    """Search only the specification sections (text content).

    Use this when looking for explanatory text, definitions, or procedures
    in the IEEE 802.11 specifications.

    Args:
        query: The search query
        n_results: Number of results to return (default: 5, max: 20)
        spec: Optional spec filter (e.g., "80211be", "80211bn"). If not provided, searches all specs.
    """
    logger.info(f"Searching sections for: {query}" + (f" in spec={spec}" if spec else ""))

    n_results = min(max(1, n_results), 20)

    try:
        collection = get_collection()

        # Build where filter: type=section AND optionally spec
        if spec:
            where_filter = {"$and": [{"type": "section"}, {"spec": spec}]}
        else:
            where_filter = {"type": "section"}

        results = collection.query(
            query_texts=[query],
            n_results=n_results * 3,  # Get more to filter
            where=where_filter
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
async def search_tables(query: str, n_results: int = 5, spec: str = None) -> str:
    """Search only the specification tables.

    Use this when looking for tabular data like encoding values,
    parameter definitions, or field mappings in the IEEE 802.11 specifications.

    Args:
        query: The search query (e.g., "EMLSR padding delay encoding")
        n_results: Number of results to return (default: 5, max: 10)
        spec: Optional spec filter (e.g., "80211be", "80211bn"). If not provided, searches all specs.
    """
    logger.info(f"Searching tables for: {query}" + (f" in spec={spec}" if spec else ""))

    n_results = min(max(1, n_results), 10)

    try:
        collection = get_collection()

        # Build where filter: type=table AND optionally spec
        if spec:
            where_filter = {"$and": [{"type": "table"}, {"spec": spec}]}
        else:
            where_filter = {"type": "table"}

        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2,
            where=where_filter
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
async def search_figures(query: str, n_results: int = 5, spec: str = None) -> str:
    """Search only the specification figures.

    Use this when looking for diagrams, frame formats, or visual
    representations in the IEEE 802.11 specifications.
    Returns figure captions and image file paths.

    Args:
        query: The search query (e.g., "Multi-Link element format")
        n_results: Number of results to return (default: 5, max: 10)
        spec: Optional spec filter (e.g., "80211be", "80211bn"). If not provided, searches all specs.
    """
    logger.info(f"Searching figures for: {query}" + (f" in spec={spec}" if spec else ""))

    n_results = min(max(1, n_results), 10)

    try:
        collection = get_collection()

        # Build where filter: type=figure AND optionally spec
        if spec:
            where_filter = {"$and": [{"type": "figure"}, {"spec": spec}]}
        else:
            where_filter = {"type": "figure"}

        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2,
            where=where_filter
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

    Returns the count of sections, tables, and figures stored in the database,
    broken down by specification.
    """
    logger.info("Getting database stats")

    try:
        collection = get_collection()
        all_docs = collection.get()

        metadatas = all_docs.get("metadatas", [])

        # Count by spec
        spec_counts = {}
        for m in metadatas:
            spec = m.get("spec", "unknown")
            spec_name = m.get("spec_name", spec)
            if spec not in spec_counts:
                spec_counts[spec] = {
                    "spec_name": spec_name,
                    "section": 0,
                    "table": 0,
                    "figure": 0
                }
            doc_type = m.get("type", "unknown")
            if doc_type in spec_counts[spec]:
                spec_counts[spec][doc_type] += 1

        # Build output
        lines = ["IEEE 802.11 Database Statistics:", ""]

        total_docs = len(metadatas)
        total_sections = sum(c["section"] for c in spec_counts.values())
        total_tables = sum(c["table"] for c in spec_counts.values())
        total_figures = sum(c["figure"] for c in spec_counts.values())

        lines.append(f"Total: {total_docs} documents")
        lines.append(f"  - Sections: {total_sections}")
        lines.append(f"  - Tables: {total_tables}")
        lines.append(f"  - Figures: {total_figures}")
        lines.append("")

        if len(spec_counts) > 1 or (len(spec_counts) == 1 and "unknown" not in spec_counts):
            lines.append("By Specification:")
            for spec, counts in sorted(spec_counts.items()):
                spec_total = counts["section"] + counts["table"] + counts["figure"]
                lines.append(f"  [{spec}] {counts['spec_name']}: {spec_total} documents")
                lines.append(f"    - Sections: {counts['section']}")
                lines.append(f"    - Tables: {counts['table']}")
                lines.append(f"    - Figures: {counts['figure']}")

        lines.append("")
        lines.append(f"Database path: {DB_PATH}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return f"Error getting stats: {str(e)}"


@mcp.tool()
async def list_specs() -> str:
    """List all available IEEE 802.11 specifications in the database.

    Returns a list of specification identifiers that can be used with the
    spec parameter in search tools.
    """
    logger.info("Listing available specs")

    try:
        collection = get_collection()
        all_docs = collection.get()

        metadatas = all_docs.get("metadatas", [])

        # Gather unique specs with counts
        spec_info = {}
        for m in metadatas:
            spec = m.get("spec", "")
            if spec:
                if spec not in spec_info:
                    spec_info[spec] = {
                        "spec_name": m.get("spec_name", spec),
                        "count": 0
                    }
                spec_info[spec]["count"] += 1

        if not spec_info:
            return "No specifications found in the database."

        lines = ["Available IEEE 802.11 Specifications:", ""]
        for spec, info in sorted(spec_info.items()):
            lines.append(f"  - {spec}: {info['spec_name']} ({info['count']} documents)")

        lines.append("")
        lines.append("Use the spec parameter in search tools to filter by specification.")
        lines.append('Example: search_ieee80211("EMLSR", spec="80211be")')

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"List specs error: {e}")
        return f"Error listing specs: {str(e)}"


def main():
    """Run the MCP server."""
    logger.info("Starting IEEE 802.11 MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
