# IEEE 802.11 MCP Server

An MCP (Model Context Protocol) server that provides semantic search and structured queries over IEEE 802.11 specifications. Enables AI assistants like Claude to query technical specifications, tables, and figures from multiple standards (802.11be/Wi-Fi 7, 802.11bn/Wi-Fi 8, etc.).

## Features

- **Multi-Spec Support**: Index and search across multiple IEEE 802.11 specifications
- **Hybrid Storage**: ChromaDB for semantic search + SQLite for structured queries
- **Semantic Search**: Uses sentence-transformers embeddings for intelligent search
- **Structured Queries**: Exact lookups by section/table/figure number, hierarchy browsing
- **Content Types**: Search across sections, tables, and figures
- **Spec Filtering**: Filter search results by specification
- **MCP Integration**: Works with Claude Desktop and other MCP-compatible clients

## Tools

### Semantic Search (ChromaDB)

| Tool | Description |
|------|-------------|
| `search_ieee80211` | Search all content (sections, tables, figures). Optional `spec` filter. |
| `search_sections` | Search only specification text sections. Optional `spec` filter. |
| `search_tables` | Search only tables (encodings, parameters). Optional `spec` filter. |
| `search_figures` | Search only figures (diagrams, formats). Optional `spec` filter. |
| `list_specs` | List available specifications with document counts |
| `get_database_stats` | Get ChromaDB statistics broken down by spec |

### Structured Queries (SQLite)

| Tool | Description |
|------|-------------|
| `get_section` | Get a specific section by number (e.g., "9.4.2.322.2") |
| `get_table` | Get a specific table by number (e.g., "9-417g") |
| `get_figure` | Get a specific figure by number (e.g., "9-1074o") |
| `list_sections` | List sections with optional filters (spec, level, page) |
| `list_tables` | List tables with optional filters (spec, section_number) |
| `list_figures` | List figures with optional filters (spec, section_number) |
| `get_section_titles_by_level` | Get section titles at a specific hierarchy level |
| `browse_section_hierarchy` | Overview of section counts by level with samples |
| `get_sqlite_stats` | Get SQLite database statistics |

## Setup

### 1. Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install chromadb sentence-transformers "mcp[cli]"
```

### 3. Extract PDF Content

Extract content from one or more IEEE 802.11 specification PDFs:

```bash
# Extract 802.11be (Wi-Fi 7)
python chunk_pdf.py --pdf 80211be-2024.pdf --spec 80211be
# Creates: 80211be_output.json, figures/80211be/

# Extract 802.11bn (Wi-Fi 8)
python chunk_pdf.py --pdf 80211bn-2025.pdf --spec 80211bn
# Creates: 80211bn_output.json, figures/80211bn/

# Extract specific page range (for large PDFs)
python chunk_pdf.py --pdf 80211be-2024.pdf --spec 80211be --start-page 240 --end-page 500
```

### 4. Store in Databases

#### Vector Database (ChromaDB) - for semantic search

```bash
# Single spec
python store_to_vectordb.py --json 80211be_output.json

# Multiple specs (recommended)
python store_to_vectordb.py --json 80211be_output.json 80211bn_output.json
```

This creates the `chroma_db/` directory with embeddings from all specs.

#### SQLite Database - for structured queries

```bash
# Single spec
python store_to_db.py --json 80211be_output.json --db ieee80211.db

# Multiple specs
python store_to_db.py --json 80211be_output.json 80211bn_output.json --db ieee80211.db

# Verify the data
python store_to_db.py --json 80211be_output.json --db ieee80211.db --verify
```

This creates `ieee80211.db` with tables for specifications, sections, tables, and figures.

### 5. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ieee80211": {
      "command": "/path/to/venv/bin/python3",
      "args": ["/path/to/ieee80211_mcp_server.py"]
    }
  }
}
```

### 6. Restart Claude Desktop

## Usage

### In Claude Desktop

Ask questions like:
- "What is EMLSR padding delay?"
- "Show me the Multi-Link element format"
- "Search for MLD capabilities in the 802.11be spec"
- "Compare EMLSR between 802.11be and 802.11bn"
- "List available specs"

### Command Line

```bash
# Search the database
python store_to_vectordb.py --search-only --query "EMLSR transition delay"

# Run MCP server directly (for testing)
python ieee80211_mcp_server.py
```

### Search with Spec Filter

All search tools support an optional `spec` parameter:

```python
# Search all specs
search_ieee80211("EMLSR")

# Search specific spec only
search_ieee80211("EMLSR", spec="80211be")
search_sections("Multi-Link", spec="80211bn")
```

### Structured Queries (SQLite)

Exact lookups by number:

```python
# Get specific section
get_section("9.4.2.322.2")

# Get specific table
get_table("9-417g")

# Get specific figure
get_figure("9-1074o")
```

Browse section hierarchy:

```python
# Get hierarchy overview
browse_section_hierarchy()

# Get all level 5 sections
get_section_titles_by_level(5)

# Get level 6 sections under a parent
get_section_titles_by_level(6, parent_section="9.4.2.322.2")

# List all tables in a section
list_tables(section_number="9.4.2")
```

## Project Structure

```
├── chunk_pdf.py            # Extract content from PDF
├── store_to_vectordb.py    # Store content in ChromaDB (semantic search)
├── store_to_db.py          # Store content in SQLite (structured queries)
├── db_schema.sql           # SQLite schema definition
├── ieee80211_mcp_server.py # MCP server (ChromaDB + SQLite)
├── figures/                # Extracted figure images
│   ├── 80211be/           # Figures from 802.11be
│   └── 80211bn/           # Figures from 802.11bn
├── chroma_db/              # Vector database (generated)
├── ieee80211.db            # SQLite database (generated)
├── 80211be_output.json     # Extracted content (generated)
└── 80211bn_output.json     # Extracted content (generated)
```

## Requirements

- Python 3.12+
- ChromaDB
- sentence-transformers
- MCP SDK

## License

MIT
