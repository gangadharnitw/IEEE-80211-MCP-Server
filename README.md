# IEEE 802.11 MCP Server

An MCP (Model Context Protocol) server that provides semantic search capabilities over the IEEE 802.11be (Wi-Fi 7) specification. Enables AI assistants like Claude to query technical specifications, tables, and figures from the standard.

## Features

- **Semantic Search**: Uses ChromaDB with sentence-transformers embeddings for intelligent search
- **Content Types**: Search across sections, tables, and figures
- **MCP Integration**: Works with Claude Desktop and other MCP-compatible clients

## Tools

| Tool | Description |
|------|-------------|
| `search_ieee80211` | Search all content (sections, tables, figures) |
| `search_sections` | Search only specification text sections |
| `search_tables` | Search only tables (encodings, parameters) |
| `search_figures` | Search only figures (diagrams, formats) |
| `get_database_stats` | Get database statistics |

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

Place your IEEE 802.11be PDF in the project directory, then run:

```bash
python chunk_pdf.py
```

This creates `sections_output.json` and extracts figures to `figures/`.

### 4. Store in Vector Database

```bash
python store_to_vectordb.py
```

This creates the `chroma_db/` directory with embeddings.

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
- "Search for MLD capabilities in the 802.11 spec"

### Command Line

```bash
# Search the database
python store_to_vectordb.py --search-only --query "EMLSR transition delay"

# Run MCP server directly (for testing)
python ieee80211_mcp_server.py
```

## Project Structure

```
├── chunk_pdf.py           # Extract content from PDF
├── store_to_vectordb.py   # Store content in ChromaDB
├── ieee80211_mcp_server.py # MCP server
├── figures/               # Extracted figure images
├── chroma_db/             # Vector database (generated)
└── sections_output.json   # Extracted content (generated)
```

## Requirements

- Python 3.12+
- ChromaDB
- sentence-transformers
- MCP SDK

## License

MIT
