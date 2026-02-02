# IEEE 802.11 MCP Server

An MCP (Model Context Protocol) server that provides semantic search capabilities over IEEE 802.11 specifications. Enables AI assistants like Claude to query technical specifications, tables, and figures from multiple standards (802.11be/Wi-Fi 7, 802.11bn/Wi-Fi 8, etc.).

## Features

- **Multi-Spec Support**: Index and search across multiple IEEE 802.11 specifications
- **Semantic Search**: Uses ChromaDB with sentence-transformers embeddings for intelligent search
- **Content Types**: Search across sections, tables, and figures
- **Spec Filtering**: Filter search results by specification
- **MCP Integration**: Works with Claude Desktop and other MCP-compatible clients

## Tools

| Tool | Description |
|------|-------------|
| `search_ieee80211` | Search all content (sections, tables, figures). Optional `spec` filter. |
| `search_sections` | Search only specification text sections. Optional `spec` filter. |
| `search_tables` | Search only tables (encodings, parameters). Optional `spec` filter. |
| `search_figures` | Search only figures (diagrams, formats). Optional `spec` filter. |
| `list_specs` | List available specifications with document counts |
| `get_database_stats` | Get database statistics broken down by spec |

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
```

### 4. Store in Vector Database

Index all extracted specs together:

```bash
# Single spec
python store_to_vectordb.py --json 80211be_output.json

# Multiple specs (recommended)
python store_to_vectordb.py --json 80211be_output.json 80211bn_output.json
```

This creates the `chroma_db/` directory with embeddings from all specs.

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

## Project Structure

```
├── chunk_pdf.py            # Extract content from PDF
├── store_to_vectordb.py    # Store content in ChromaDB
├── ieee80211_mcp_server.py # MCP server
├── figures/                # Extracted figure images
│   ├── 80211be/           # Figures from 802.11be
│   └── 80211bn/           # Figures from 802.11bn
├── chroma_db/              # Vector database (generated)
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
