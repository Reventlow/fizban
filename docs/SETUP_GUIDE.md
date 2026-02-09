# Fizban Setup Guide — New Machine

How to set up Fizban on a new computer with Claude Code.

## Prerequisites

- Python 3.12+
- Git
- Claude Code installed and authenticated

## Step 1: Clone and install Fizban

```bash
git clone git@github.com:Reventlow/fizban.git
cd fizban

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with vector search support
pip install -e ".[vec]"
```

Verify the install:

```bash
fizban doctor
```

## Step 2: Clone your documentation repos

Fizban indexes local markdown files. Clone the repos you want to search:

```bash
mkdir -p ~/Documents
cd ~/Documents
git clone <your-docs-repo-1>
git clone <your-docs-repo-2>
```

## Step 3: Register Fizban as an MCP server in Claude Code

```bash
claude mcp add fizban \
  --scope user \
  -e FIZBAN_REPOS="/home/YOURUSER/Documents/repo1,/home/YOURUSER/Documents/repo2" \
  -- fizban serve-mcp
```

Replace `YOURUSER` and the repo paths with your actual values.

Alternatively, add it manually to `~/.claude.json`:

```json
{
  "mcpServers": {
    "fizban": {
      "command": "fizban",
      "args": ["serve-mcp"],
      "env": {
        "FIZBAN_REPOS": "/home/YOURUSER/Documents/repo1,/home/YOURUSER/Documents/repo2"
      }
    }
  }
}
```

> **Note**: If you installed Fizban in a venv, use the full path to the binary:
> `"command": "/path/to/fizban/.venv/bin/fizban"`

## Step 4: Build the index

Start Claude Code and ask it to rebuild the index, or run it directly:

```bash
fizban rebuild
```

Verify with:

```bash
fizban serve-mcp
# Then in Claude Code, use system_status to check document/chunk counts
```

## Step 5: Verify in Claude Code

Start a new Claude Code session and test:

1. Check connectivity — Claude should list Fizban in its MCP tools
2. Run `system_status` — should show your documents and chunks
3. Try a `search_semantic` query — should return results from your docs

## Troubleshooting

### Fizban MCP server not connecting

- Check the command path: `which fizban` (must be on PATH or use absolute path)
- If using a venv, make sure the MCP config points to `.venv/bin/fizban`
- Restart Claude Code after changing MCP config

### Empty database after rebuild

- Verify `FIZBAN_REPOS` is set in the MCP server env config
- Check that the repo paths exist and contain `.md` files
- Run `fizban -v rebuild` for verbose output

### Search returns no results

- The default distance threshold (0.85) is strict — try increasing it to 1.2-1.5
- Verify the index has chunks: `fizban doctor` or `system_status`
- Try broader search terms

### Slow search performance

Fizban runs the embedding model (`all-MiniLM-L6-v2`) locally on CPU by default. This is intentional for data sovereignty — nothing leaves your machine. For most setups with <1000 documents, the latency is acceptable.

## What stays local

Everything. Fizban has no external service dependencies:

- Embeddings are generated locally via `sentence-transformers`
- The database is a single SQLite file at `~/.local/share/fizban/fizban.db`
- Search is local vector similarity (sqlite-vec)
- Documentation repos are your own local git clones

The index is machine-specific (built from local file paths) and does not transfer between machines. Each machine builds its own index.
