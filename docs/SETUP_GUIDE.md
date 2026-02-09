# Fizban Setup Guide — New Machine

How to set up Fizban on a new computer with Claude Code.

## Prerequisites

- Python 3.12+
- Git
- Claude Code installed and authenticated

## Step 1: Clone and install Fizban

```bash
git clone git@github.com:Reventlow/fizban.git ~/fizban
cd ~/fizban

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

## Step 3: Configure repo paths

Repo paths are stored in a single env file so they are not hardcoded in the MCP
config. This makes it easy to move between machines — just edit the env file.

```bash
mkdir -p ~/.config/fizban
```

Create `~/.config/fizban/env` with your repo paths:

```bash
# Comma-separated absolute paths to documentation repositories
FIZBAN_REPOS="${HOME}/Documents/repo1,${HOME}/Documents/repo2"
```

`${HOME}` is expanded at runtime, so the file is portable across users.

## Step 4: Register Fizban as an MCP server in Claude Code

The repo ships with a `run.sh` wrapper script that loads `~/.config/fizban/env`
before running fizban. This keeps repo paths out of the MCP config.

Add to `~/.claude.json`:

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

Replace `YOURUSER` with your actual username. No `env` block is needed — the
wrapper script handles that.

> **Alternatively**, you can skip the wrapper and pass `FIZBAN_REPOS` directly
> in the MCP config `env` block, but then you have hardcoded paths in two places.

## Step 5: Build the index

```bash
~/fizban/run.sh rebuild
```

Or start Claude Code and ask it to rebuild the index.

Verify with:

```bash
~/fizban/run.sh doctor
```

## Step 6: Verify in Claude Code

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
