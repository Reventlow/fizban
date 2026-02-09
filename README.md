# Fizban

Local documentation knowledge base with semantic search, powered by SQLite and sentence-transformers. Includes an MCP server for integration with Claude and other AI tools.

## Features

- **Semantic search** over local markdown documentation
- **Incremental indexing** — only re-indexes changed files
- **Image extraction** — tracks image references from markdown
- **MCP server** — integrates directly with Claude Code / Claude Desktop
- **SQLite-based** — single-file database, no external services
- **Vector search** — uses sqlite-vec (or sqlite-vss as fallback)

## Installation

```bash
git clone git@github.com:Reventlow/fizban.git ~/fizban
cd ~/fizban
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,vec]"
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `sentence-transformers` | Local embedding model |
| `mcp[cli]` | MCP server SDK |
| `numpy` | Vector operations |
| `sqlite-vec` | Vector similarity search (optional) |

## Quick Start

```bash
# Check system health
fizban doctor

# Pull latest changes from all repos
fizban pull

# Build the search index (first time)
fizban rebuild

# Update index incrementally (subsequent runs)
fizban update

# Start the MCP server
fizban serve-mcp
```

## Configuration

Configuration is via environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `FIZBAN_DB_PATH` | `~/.local/share/fizban/fizban.db` | SQLite database path |
| `FIZBAN_VECTOR_BACKEND` | `vec` | Vector backend: `vec` or `vss` |
| `FIZBAN_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `FIZBAN_CHUNK_SIZE` | `1000` | Characters per chunk |
| `FIZBAN_CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `FIZBAN_REPOS` | *(empty)* | Comma-separated list of repo paths to index |

## Indexed Repositories

Configure repos via `~/.config/fizban/env` (single source of truth):

```bash
mkdir -p ~/.config/fizban
cat > ~/.config/fizban/env << 'EOF'
# Comma-separated absolute paths to documentation repositories
FIZBAN_REPOS="${HOME}/Documents/repo1,${HOME}/Documents/repo2"
EOF
```

The repo ships with a `run.sh` wrapper that sources this file before running fizban.
Use it for both CLI and MCP so paths are never hardcoded in multiple places:

```bash
~/fizban/run.sh doctor
~/fizban/run.sh rebuild
```

## MCP Server

### Registering with Claude Code

Add to `~/.claude.json` (global):

```json
{
  "mcpServers": {
    "fizban": {
      "type": "stdio",
      "command": "/home/YOURUSER/fizban/run.sh",
      "args": ["serve-mcp"]
    }
  }
}
```

No `env` block needed — `run.sh` loads `~/.config/fizban/env` automatically.

> **Important**: `FIZBAN_REPOS` must be configured (either via the env file or
> in the MCP config `env` block). Without it, `repos_pull_all`, `index_rebuild`,
> and `index_update` will have no repos to operate on.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `repos_pull_all` | Git pull all configured repos |
| `index_rebuild` | Full re-index of all documents |
| `index_update` | Incremental index update |
| `search_semantic` | Semantic search (query, limit) |
| `docs_fetch` | Fetch full document by path |
| `docs_fetch_by_hit` | Fetch document from a search chunk_id |
| `system_status` | System health and stats |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev,vec]"

# Run tests
pytest tests/ -v

# Run with verbose logging
fizban -v rebuild
```

## Architecture

```
fizban/
├── pyproject.toml          # Project config & dependencies
├── README.md
├── run.sh                  # Wrapper: loads ~/.config/fizban/env, runs fizban
├── fizban/
│   ├── __init__.py
│   ├── config.py           # Configuration (env vars + defaults)
│   ├── db.py               # SQLite database (documents, chunks, images)
│   ├── embeddings.py       # Sentence-transformer wrapper
│   ├── markdown_parser.py  # Markdown parsing & image extraction
│   ├── repos.py            # Git repo management
│   ├── indexer.py          # Document indexing & chunking
│   ├── search.py           # Semantic search
│   ├── cli.py              # CLI commands (click)
│   ├── mcp_server.py       # MCP server (stdio)
│   └── vector/
│       ├── __init__.py     # Backend factory
│       ├── base.py         # Abstract interface
│       ├── vec_backend.py  # sqlite-vec backend
│       └── vss_backend.py  # sqlite-vss backend
└── tests/
    ├── __init__.py
    ├── test_markdown_parser.py
    └── test_chunking.py
```

## License

MIT
