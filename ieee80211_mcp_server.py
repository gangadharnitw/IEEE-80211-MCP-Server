"""
MCP Server for IEEE 802.11 Database.

Provides semantic search (ChromaDB) and structured queries (SQLite) over
IEEE 802.11 specification content including sections, tables, and figures.
"""

import logging
import sqlite3
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
CHROMA_DB_PATH = Path(__file__).parent / "chroma_db"
SQLITE_DB_PATH = Path(__file__).parent / "ieee80211.db"
COLLECTION_NAME = "ieee_80211"


def get_embedding_function():
    """Get the sentence-transformers embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def get_collection():
    """Get the ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
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
        lines.append(f"ChromaDB path: {CHROMA_DB_PATH}")
        lines.append(f"SQLite path: {SQLITE_DB_PATH}")

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


# =============================================================================
# SQLite Database Tools (Structured Queries)
# =============================================================================


def get_sqlite_connection():
    """Get a SQLite database connection."""
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found at {SQLITE_DB_PATH}. Run store_to_db.py first.")
    return sqlite3.connect(str(SQLITE_DB_PATH))


@mcp.tool()
async def get_section(section_number: str, spec: str = None) -> str:
    """Get a specific section by its number.

    Performs exact lookup of a section by its number (e.g., "9.4.2.322.2").

    Args:
        section_number: The section number to look up (e.g., "9.4.2.322.2")
        spec: Optional spec filter (e.g., "80211be"). If not provided, searches all specs.
    """
    logger.info(f"Getting section: {section_number}" + (f" from spec={spec}" if spec else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        if spec:
            cursor.execute("""
                SELECT spec_id, section_number, section_title, level, page, text
                FROM sections
                WHERE section_number = ? AND spec_id = ?
            """, (section_number, spec))
        else:
            cursor.execute("""
                SELECT spec_id, section_number, section_title, level, page, text
                FROM sections
                WHERE section_number = ?
            """, (section_number,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No section found with number: {section_number}"

        results = []
        for row in rows:
            spec_id, sec_num, title, level, page, text = row
            results.append(f"[{spec_id}] Section {sec_num}")
            results.append(f"Title: {title}")
            results.append(f"Level: {level}, Page: {page}")
            results.append(f"Content:\n{text if text else '(no content)'}")
            results.append("")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Get section error: {e}")
        return f"Error getting section: {str(e)}"


@mcp.tool()
async def get_table(table_number: str, spec: str = None) -> str:
    """Get a specific table by its number.

    Performs exact lookup of a table by its number (e.g., "9-417g").

    Args:
        table_number: The table number to look up (e.g., "9-417g")
        spec: Optional spec filter (e.g., "80211be"). If not provided, searches all specs.
    """
    logger.info(f"Getting table: {table_number}" + (f" from spec={spec}" if spec else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        if spec:
            cursor.execute("""
                SELECT spec_id, table_number, caption, page, content_markdown, section_number, level
                FROM tables
                WHERE table_number = ? AND spec_id = ?
            """, (table_number, spec))
        else:
            cursor.execute("""
                SELECT spec_id, table_number, caption, page, content_markdown, section_number, level
                FROM tables
                WHERE table_number = ?
            """, (table_number,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No table found with number: {table_number}"

        results = []
        for row in rows:
            spec_id, tbl_num, caption, page, content, section_num, level = row
            results.append(f"[{spec_id}] Table {tbl_num}")
            results.append(f"Caption: {caption}")
            results.append(f"Page: {page}, Section: {section_num or 'N/A'}, Level: {level or 'N/A'}")
            results.append(f"Content:\n{content if content else '(no content)'}")
            results.append("")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Get table error: {e}")
        return f"Error getting table: {str(e)}"


@mcp.tool()
async def get_figure(figure_number: str, spec: str = None) -> str:
    """Get a specific figure by its number.

    Performs exact lookup of a figure by its number (e.g., "9-1074o").

    Args:
        figure_number: The figure number to look up (e.g., "9-1074o")
        spec: Optional spec filter (e.g., "80211be"). If not provided, searches all specs.
    """
    logger.info(f"Getting figure: {figure_number}" + (f" from spec={spec}" if spec else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        if spec:
            cursor.execute("""
                SELECT spec_id, figure_number, caption, page, image_path, section_number, level
                FROM figures
                WHERE figure_number = ? AND spec_id = ?
            """, (figure_number, spec))
        else:
            cursor.execute("""
                SELECT spec_id, figure_number, caption, page, image_path, section_number, level
                FROM figures
                WHERE figure_number = ?
            """, (figure_number,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No figure found with number: {figure_number}"

        results = []
        for row in rows:
            spec_id, fig_num, caption, page, image_path, section_num, level = row
            results.append(f"[{spec_id}] Figure {fig_num}")
            results.append(f"Caption: {caption}")
            results.append(f"Page: {page}, Section: {section_num or 'N/A'}, Level: {level or 'N/A'}")
            results.append(f"Image path: {image_path or 'N/A'}")
            results.append("")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Get figure error: {e}")
        return f"Error getting figure: {str(e)}"


@mcp.tool()
async def list_sections(spec: str = None, level: int = None, page: int = None) -> str:
    """List all sections, optionally filtered by spec, level, or page.

    Args:
        spec: Optional spec filter (e.g., "80211be")
        level: Optional level filter (e.g., 5 for top-level sections)
        page: Optional page filter
    """
    logger.info(f"Listing sections" + (f" spec={spec}" if spec else "") + (f" level={level}" if level else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        query = "SELECT spec_id, section_number, section_title, level, page FROM sections WHERE 1=1"
        params = []

        if spec:
            query += " AND spec_id = ?"
            params.append(spec)
        if level is not None:
            query += " AND level = ?"
            params.append(level)
        if page is not None:
            query += " AND page = ?"
            params.append(page)

        query += " ORDER BY spec_id, section_number"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "No sections found matching the criteria."

        results = [f"Found {len(rows)} sections:", ""]
        for row in rows:
            spec_id, sec_num, title, lvl, pg = row
            indent = "  " * (lvl - 1) if lvl else ""
            results.append(f"[{spec_id}] {indent}{sec_num} {title} (p.{pg})")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"List sections error: {e}")
        return f"Error listing sections: {str(e)}"


@mcp.tool()
async def list_tables(spec: str = None, section_number: str = None) -> str:
    """List all tables, optionally filtered by spec or section.

    Args:
        spec: Optional spec filter (e.g., "80211be")
        section_number: Optional section filter (e.g., "9.4.2" for all tables in that section)
    """
    logger.info(f"Listing tables" + (f" spec={spec}" if spec else "") + (f" section={section_number}" if section_number else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        query = "SELECT spec_id, table_number, caption, page, section_number FROM tables WHERE 1=1"
        params = []

        if spec:
            query += " AND spec_id = ?"
            params.append(spec)
        if section_number:
            query += " AND section_number LIKE ?"
            params.append(f"{section_number}%")

        query += " ORDER BY spec_id, table_number"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "No tables found matching the criteria."

        results = [f"Found {len(rows)} tables:", ""]
        for row in rows:
            spec_id, tbl_num, caption, page, sec_num = row
            results.append(f"[{spec_id}] Table {tbl_num}: {caption} (p.{page}, sec.{sec_num or 'N/A'})")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"List tables error: {e}")
        return f"Error listing tables: {str(e)}"


@mcp.tool()
async def list_figures(spec: str = None, section_number: str = None) -> str:
    """List all figures, optionally filtered by spec or section.

    Args:
        spec: Optional spec filter (e.g., "80211be")
        section_number: Optional section filter (e.g., "9.4.2" for all figures in that section)
    """
    logger.info(f"Listing figures" + (f" spec={spec}" if spec else "") + (f" section={section_number}" if section_number else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        query = "SELECT spec_id, figure_number, caption, page, section_number, image_path FROM figures WHERE 1=1"
        params = []

        if spec:
            query += " AND spec_id = ?"
            params.append(spec)
        if section_number:
            query += " AND section_number LIKE ?"
            params.append(f"{section_number}%")

        query += " ORDER BY spec_id, figure_number"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "No figures found matching the criteria."

        results = [f"Found {len(rows)} figures:", ""]
        for row in rows:
            spec_id, fig_num, caption, page, sec_num, img_path = row
            results.append(f"[{spec_id}] Figure {fig_num}: {caption} (p.{page}, sec.{sec_num or 'N/A'})")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"List figures error: {e}")
        return f"Error listing figures: {str(e)}"


@mcp.tool()
async def get_section_titles_by_level(level: int, parent_section: str = None, spec: str = None) -> str:
    """Get section titles at a specific hierarchy level.

    Browse the section hierarchy by level. Optionally filter by parent section
    to see subsections under a specific section.

    Args:
        level: The hierarchy level (1 for top-level, 2 for subsections, etc.)
        parent_section: Optional parent section number to filter subsections
                       (e.g., "9" for all sections under 9.x, "9.4" for 9.4.x)
        spec: Optional spec filter (e.g., "80211be")

    Examples:
        - get_section_titles_by_level(1) -> All top-level sections
        - get_section_titles_by_level(2, parent_section="9") -> All level-2 sections under section 9
        - get_section_titles_by_level(3, parent_section="9.4.2") -> All level-3 sections under 9.4.2
    """
    logger.info(f"Getting section titles at level {level}" +
                (f" under {parent_section}" if parent_section else "") +
                (f" in spec={spec}" if spec else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        query = "SELECT spec_id, section_number, section_title, page FROM sections WHERE level = ?"
        params = [level]

        if parent_section:
            # Filter by parent section prefix
            query += " AND section_number LIKE ?"
            params.append(f"{parent_section}.%")

        if spec:
            query += " AND spec_id = ?"
            params.append(spec)

        query += " ORDER BY spec_id, section_number"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            msg = f"No sections found at level {level}"
            if parent_section:
                msg += f" under section {parent_section}"
            return msg

        # Build output
        header = f"Level {level} sections"
        if parent_section:
            header += f" under {parent_section}"
        header += f" ({len(rows)} found):"

        results = [header, ""]
        for row in rows:
            spec_id, sec_num, title, page = row
            # Extract just the title part (remove the number prefix if present)
            title_only = title
            if title.startswith(sec_num):
                title_only = title[len(sec_num):].strip()
            results.append(f"[{spec_id}] {sec_num} - {title_only} (p.{page})")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Get section titles error: {e}")
        return f"Error getting section titles: {str(e)}"


@mcp.tool()
async def browse_section_hierarchy(spec: str = None) -> str:
    """Get an overview of the section hierarchy showing all levels.

    Returns a summary of how many sections exist at each level,
    useful for understanding the document structure before drilling down.

    Args:
        spec: Optional spec filter (e.g., "80211be")
    """
    logger.info(f"Browsing section hierarchy" + (f" for spec={spec}" if spec else ""))

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        # Get counts by level
        query = "SELECT level, COUNT(*) FROM sections"
        params = []
        if spec:
            query += " WHERE spec_id = ?"
            params.append(spec)
        query += " GROUP BY level ORDER BY level"

        cursor.execute(query, params)
        level_counts = cursor.fetchall()

        # Get sample sections at each level
        results = ["Section Hierarchy Overview:", ""]

        for level, count in level_counts:
            results.append(f"Level {level}: {count} sections")

            # Get a few samples at this level
            sample_query = "SELECT section_number, section_title FROM sections WHERE level = ?"
            sample_params = [level]
            if spec:
                sample_query += " AND spec_id = ?"
                sample_params.append(spec)
            sample_query += " LIMIT 3"

            cursor.execute(sample_query, sample_params)
            samples = cursor.fetchall()
            for sec_num, title in samples:
                title_short = title[:60] + "..." if len(title) > 60 else title
                results.append(f"  - {sec_num}: {title_short}")
            if count > 3:
                results.append(f"  ... and {count - 3} more")
            results.append("")

        conn.close()

        results.append("Use get_section_titles_by_level(level, parent_section) to drill down.")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Browse hierarchy error: {e}")
        return f"Error browsing hierarchy: {str(e)}"


@mcp.tool()
async def get_sqlite_stats() -> str:
    """Get statistics about the SQLite database.

    Returns counts of specifications, sections, tables, and figures.
    """
    logger.info("Getting SQLite database stats")

    try:
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        lines = ["IEEE 802.11 SQLite Database Statistics:", ""]

        # Specifications
        cursor.execute("SELECT spec_id, spec_name FROM specifications")
        specs = cursor.fetchall()
        lines.append(f"Specifications: {len(specs)}")
        for spec_id, spec_name in specs:
            cursor.execute("SELECT COUNT(*) FROM sections WHERE spec_id = ?", (spec_id,))
            sec_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM tables WHERE spec_id = ?", (spec_id,))
            tbl_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM figures WHERE spec_id = ?", (spec_id,))
            fig_count = cursor.fetchone()[0]

            lines.append(f"  [{spec_id}] {spec_name}")
            lines.append(f"    - Sections: {sec_count}")
            lines.append(f"    - Tables: {tbl_count}")
            lines.append(f"    - Figures: {fig_count}")

        conn.close()

        lines.append("")
        lines.append(f"Database path: {SQLITE_DB_PATH}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"SQLite stats error: {e}")
        return f"Error getting SQLite stats: {str(e)}"


def main():
    """Run the MCP server."""
    logger.info("Starting IEEE 802.11 MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
