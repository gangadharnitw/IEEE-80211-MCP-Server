"""
Store extracted IEEE 802.11 content (sections, tables, figures) into SQLite database.
Provides structured queries alongside ChromaDB for semantic search.
"""

import sqlite3
import json
import argparse
import re
from pathlib import Path
from datetime import datetime


def create_tables(conn: sqlite3.Connection) -> None:
    """Create database tables if they don't exist."""
    schema_path = Path(__file__).parent / "db_schema.sql"

    if schema_path.exists():
        with open(schema_path) as f:
            conn.executescript(f.read())
    else:
        # Inline schema if file not found
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_id TEXT UNIQUE NOT NULL,
                spec_name TEXT,
                source_pdf TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                page_range_start INTEGER,
                page_range_end INTEGER
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_id TEXT NOT NULL,
                section_number TEXT,
                section_title TEXT NOT NULL,
                level INTEGER,
                page INTEGER,
                text TEXT,
                FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
            );

            CREATE TABLE IF NOT EXISTS tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_id TEXT NOT NULL,
                table_number TEXT,
                caption TEXT,
                page INTEGER,
                content_markdown TEXT,
                section_number TEXT,
                level INTEGER,
                FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
            );

            CREATE TABLE IF NOT EXISTS figures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_id TEXT NOT NULL,
                figure_number TEXT,
                caption TEXT,
                page INTEGER,
                image_path TEXT,
                image_base64 TEXT,
                section_number TEXT,
                level INTEGER,
                FOREIGN KEY (spec_id) REFERENCES specifications(spec_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sections_spec ON sections(spec_id);
            CREATE INDEX IF NOT EXISTS idx_sections_number ON sections(section_number);
            CREATE INDEX IF NOT EXISTS idx_sections_page ON sections(page);
            CREATE INDEX IF NOT EXISTS idx_tables_spec ON tables(spec_id);
            CREATE INDEX IF NOT EXISTS idx_tables_number ON tables(table_number);
            CREATE INDEX IF NOT EXISTS idx_tables_section ON tables(section_number);
            CREATE INDEX IF NOT EXISTS idx_figures_spec ON figures(spec_id);
            CREATE INDEX IF NOT EXISTS idx_figures_number ON figures(figure_number);
            CREATE INDEX IF NOT EXISTS idx_figures_section ON figures(section_number);
        """)
    conn.commit()


def extract_section_number(title: str) -> str:
    """Extract section number from title (e.g., '9.4.2.322.2 Basic...' -> '9.4.2.322.2')."""
    match = re.match(r'^([\d.]+)', title.strip())
    return match.group(1).rstrip('.') if match else ""


def extract_table_number(caption: str) -> str:
    """Extract table number from caption (e.g., 'Table 9-417g-...' -> '9-417g')."""
    # Match pattern: digits, dash, digits/letters (e.g., 9-417g)
    match = re.search(r'Table\s+(\d+(?:-\d+[a-z]*)?)', caption, re.IGNORECASE)
    return match.group(1) if match else ""


def extract_figure_number(caption: str) -> str:
    """Extract figure number from caption (e.g., 'Figure 9-1074o-...' -> '9-1074o')."""
    # Match pattern: digits, dash, digits/letters (e.g., 9-1074o)
    match = re.search(r'Figure\s+(\d+(?:-\d+[a-z]*)?)', caption, re.IGNORECASE)
    return match.group(1) if match else ""


def find_section_for_page(sections: list, page: int) -> tuple:
    """
    Find the section that contains a given page.
    Returns (section_number, level) or (None, None) if not found.
    """
    # Find sections on or before this page, take the last one
    matching_sections = [s for s in sections if s.get("page", 0) <= page]
    if matching_sections:
        last_section = matching_sections[-1]
        section_number = extract_section_number(last_section.get("section_title", ""))
        level = last_section.get("level")
        return section_number, level
    return None, None


def store_to_db(json_paths: list, db_path: str = "ieee80211.db") -> None:
    """
    Load extracted data from JSON files and store in SQLite database.

    Args:
        json_paths: List of paths to JSON files
        db_path: Path for the SQLite database
    """
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    cursor = conn.cursor()

    spec_counts = {}

    for json_path in json_paths:
        print(f"\nProcessing: {json_path}")
        with open(json_path) as f:
            data = json.load(f)

        # Get spec identifier
        spec_id = data.get("spec", "")
        if not spec_id:
            filename = Path(json_path).stem
            spec_id = filename.replace("_output", "") if filename.endswith("_output") else filename

        spec_name = data.get("spec_name", f"IEEE 802.11 ({spec_id})")
        source_pdf = data.get("source_pdf", "")
        page_start = data.get("page_range_start")
        page_end = data.get("page_range_end")

        print(f"  Spec: {spec_id} ({spec_name})")

        # Upsert specification
        cursor.execute("""
            INSERT INTO specifications (spec_id, spec_name, source_pdf, extracted_at, page_range_start, page_range_end)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(spec_id) DO UPDATE SET
                spec_name = excluded.spec_name,
                source_pdf = excluded.source_pdf,
                extracted_at = excluded.extracted_at,
                page_range_start = excluded.page_range_start,
                page_range_end = excluded.page_range_end
        """, (spec_id, spec_name, source_pdf, datetime.now().isoformat(), page_start, page_end))

        # Delete existing data for this spec (for clean re-runs)
        cursor.execute("DELETE FROM sections WHERE spec_id = ?", (spec_id,))
        cursor.execute("DELETE FROM tables WHERE spec_id = ?", (spec_id,))
        cursor.execute("DELETE FROM figures WHERE spec_id = ?", (spec_id,))

        spec_counts[spec_id] = {"sections": 0, "tables": 0, "figures": 0}

        # Get sections for page-to-section mapping
        sections = data.get("sections", [])

        # Insert sections
        for section in sections:
            section_title = section.get("section_title", "")
            section_number = extract_section_number(section_title)
            cursor.execute("""
                INSERT INTO sections (spec_id, section_number, section_title, level, page, text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                spec_id,
                section_number,
                section_title,
                section.get("level"),
                section.get("page"),
                section.get("text", "")
            ))
            spec_counts[spec_id]["sections"] += 1

        # Insert tables
        for table in data.get("tables", []):
            caption = table.get("caption", "")
            table_number = extract_table_number(caption)
            page = table.get("page")
            section_number, level = find_section_for_page(sections, page) if page else (None, None)

            cursor.execute("""
                INSERT INTO tables (spec_id, table_number, caption, page, content_markdown, section_number, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                spec_id,
                table_number,
                caption,
                page,
                table.get("content", ""),
                section_number,
                level
            ))
            spec_counts[spec_id]["tables"] += 1

        # Insert figures
        for figure in data.get("figures", []):
            caption = figure.get("caption", "")
            figure_number = extract_figure_number(caption)
            page = figure.get("page")
            section_number, level = find_section_for_page(sections, page) if page else (None, None)

            cursor.execute("""
                INSERT INTO figures (spec_id, figure_number, caption, page, image_path, image_base64, section_number, level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                spec_id,
                figure_number,
                caption,
                page,
                figure.get("image_path", ""),
                figure.get("image_base64", ""),
                section_number,
                level
            ))
            spec_counts[spec_id]["figures"] += 1

    conn.commit()
    conn.close()

    # Print summary
    print(f"\n{'='*50}")
    print(f"Stored data in SQLite database: {db_path}")
    for spec_id, counts in spec_counts.items():
        total = sum(counts.values())
        print(f"\n  [{spec_id}] {total} items:")
        print(f"    - Sections: {counts['sections']}")
        print(f"    - Tables: {counts['tables']}")
        print(f"    - Figures: {counts['figures']}")


def verify_db(db_path: str = "ieee80211.db") -> None:
    """Print database statistics for verification."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"\nDatabase: {db_path}")
    print("-" * 40)

    # Specifications
    cursor.execute("SELECT spec_id, spec_name FROM specifications")
    specs = cursor.fetchall()
    print(f"\nSpecifications ({len(specs)}):")
    for spec_id, spec_name in specs:
        print(f"  - {spec_id}: {spec_name}")

    # Counts per table
    for table in ["sections", "tables", "figures"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"\n{table.capitalize()}: {count}")

        # Sample
        if table == "sections":
            cursor.execute(f"SELECT section_number, section_title FROM {table} LIMIT 3")
        elif table == "tables":
            cursor.execute(f"SELECT table_number, caption, section_number FROM {table} LIMIT 3")
        else:
            cursor.execute(f"SELECT figure_number, caption, section_number FROM {table} LIMIT 3")

        samples = cursor.fetchall()
        for sample in samples:
            print(f"    {sample}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store IEEE 802.11 content in SQLite database")
    parser.add_argument(
        "--json",
        nargs="+",
        default=["sections_output.json"],
        help="Path(s) to JSON file(s). Can specify multiple files."
    )
    parser.add_argument("--db", default="ieee80211.db", help="Path for SQLite database")
    parser.add_argument("--verify", action="store_true", help="Verify database contents after storing")

    args = parser.parse_args()

    store_to_db(args.json, args.db)

    if args.verify:
        verify_db(args.db)
