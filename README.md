# CodeGraph

A local developer tool that converts a codebase into a graph database stored in FalkorDB, allows natural-language querying via Ollama, and provides visual exploration of the graph through a web UI and Gource animation.

## Features

- **Multi-language parsing**: Python, JavaScript/TypeScript (`.js`, `.ts`, `.jsx`, `.tsx`, `.cjs`, `.mjs`, `.cts`, `.mts`), Java, Go, C/C++ (`.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`), Rust, C#
- **Graph model**: Extracts files, classes, functions, methods, calls, and imports into a FalkorDB property graph
- **Natural language queries**: Ask questions in plain English; Ollama generates Cypher and explains results
- **Interactive web UI**: Cytoscape.js-based graph with lazy-loading, code preview, Gource-style animation, and light/dark mode
- **Ollama chat**: Natural-language queries with model selector (light models like `llama3.2:1b` prioritized)
- **Gource visualization**: Export the code graph to an animated tree visualization

## Prerequisites

- **Python 3.9+**
- **Docker** (for FalkorDB)
- **Ollama** (optional, for AI queries) – [install](https://ollama.ai)

## Quick Start

### 1. Start FalkorDB

```bash
docker run -p 6379:6379 -p 3000:3000 -it --rm falkordb/falkordb:latest
```

Leave this running in a separate terminal.

### 2. Install dependencies

```bash
cd codegraph-tool
pip install -r requirements.txt
```

### 3. Index a repository (or single file)

```bash
python3 codegraph/cli.py index_repo /path/to/your/repo
```

You can also index a single file:

```bash
python3 codegraph/cli.py index_repo ./src/main.py
```

Example for a directory:

```bash
python3 codegraph/cli.py index_repo ./my-project
```

### 4. Run the web UI

```bash
python3 codegraph/cli.py ui
```

Open **http://localhost:8000** in your browser.

### 5. (Optional) Query with Ollama

Ensure Ollama is running and you have at least one model (e.g. `ollama pull llama3`):

```bash
python3 codegraph/cli.py ask "Which functions call the database?"
```

### 6. (Optional) Gource visualization

Install Gource (`brew install gource` on macOS), then:

```bash
python3 codegraph/cli.py gource
```

Options:
- `--detailed` – Export full graph (no limit), slower animation to show all classes/functions/methods
- `--files-only` – Export only Repository + Files (faster for huge graphs)
- `--limit N` – Max nodes per type (default 10000)

### Full visualization

For the fullest visualization of your indexed graph:

- **Web UI (complete)**: Run `python3 codegraph/cli.py ui`, then open **http://localhost:8000?view=complete**. This loads all node types (Repository, File, Class, Module, Function, Method) and edges (CONTAINS, CALLS, IMPORTS). Use this to explore call graphs and import relationships.
- **Gource**: Run `python3 codegraph/cli.py gource --detailed` for an animated tree with all files, classes, functions, and methods. Nodes appear over time with slower animation and longer visibility. Note: Gource shows nodes only; for relationship edges (CALLS, IMPORTS), use the Web UI.

---

## Project structure

```
codegraph-tool/
├── codegraph/
│   ├── cli.py              # CLI entry point
│   ├── repo_scanner.py      # Walks repo, collects source files
│   ├── parser.py            # Tree-sitter language parsers
│   ├── relationship_extractor.py  # Dispatches to language-specific extractors
│   ├── extractors/          # Per-language AST extractors (python, javascript, cpp, csharp, etc.)
│   ├── graph_builder.py     # Inserts graph into FalkorDB (bulk UNWIND)
│   ├── ollama_agent.py      # Converts questions to Cypher via Ollama
│   ├── query_engine.py      # find_callers, show_dependencies
│   └── gource_exporter.py   # Exports graph to Gource custom log
├── server/
│   └── api.py              # FastAPI backend: /graph/nodes, /graph/edges, /graph/expand/{id}
├── ui/
│   ├── index.html
│   ├── theme.js             # Light/dark mode toggle
│   ├── graph.js             # Cytoscape.js visualization with lazy expand
│   ├── chat.js              # Ollama chat panel
│   └── style.css            # Theming (no gradients, flat design)
├── requirements.txt
└── README.md
```

---

## CLI commands

| Command | Description |
|--------|-------------|
| `index_repo <path>` | Scan and parse a repository, insert into FalkorDB (clears existing graph) |
| `update_repo <path>` | Re-index (currently same as index_repo) |
| `ui [--port 8000]` | Start the web visualization server |
| `ask "<question>"` | Ask a natural language question; Ollama generates Cypher and explains results |
| `find_callers <func>` | List functions/methods that call the given name |
| `show_dependencies <node>` | List outgoing dependencies of a node |
| `gource [--detailed] [--files-only] [--limit N]` | Export to Gource; `--detailed` for full graph, `--files-only` for light export |

---

## Graph model

### Node types

- **Repository** – Root of the indexed repo
- **File** – Source file path
- **Class** – Class/struct/interface
- **Function** – Top-level function
- **Method** – Class method
- **Module** – Imported module

### Relationship types

- `CONTAINS` – File → Class/Function; Class → Method; Repository → File
- `CALLS` – Function/Method → Function/Method
- `IMPORTS` – File → Module

---

## Web UI behavior

- **File-level view (default)**: For large graphs, the UI loads only **Repository + Files** (up to 500 nodes) so it stays responsive. Click a **File** to expand and see its classes, functions, and methods.
- **Full view**: Add `?view=full` to the URL (e.g. `http://localhost:8000?view=full`) to also include Classes and Modules in the initial load.
- **Complete view**: Add `?view=complete` to load all nodes (including Functions and Methods) and all edges (CALLS, IMPORTS). Best for exploring the full call graph.
- **Code preview**: Click any File, Class, Function, or Method node to see its source code in the details panel.
- **Gource-style animation**: On load, nodes reveal sequentially (Repository → File → Class → Module → Function → Method). Add `?animate=false` to disable.
- **Ollama chat**: Click "Chat" in the toolbar to open the AI panel. Use the **Model** dropdown to choose any available Ollama model (light models like `llama3.2:1b`, `phi3:mini` appear first with a ⚡ indicator). Ask questions in plain English about your code graph.
- **Light/dark mode**: Click the sun/moon icon in the toolbar to toggle themes. Preference is saved in localStorage.
- **Expand on click**: Click any node to lazy-load its children (e.g. a File shows its Classes/Functions; a Class shows its Methods).
- **Node colors**: Repository (purple), File (blue), Class (red), Function (green), Method (yellow), Module (gray).
- **Layout**: Uses Cytoscape.js `cose` (force-directed) layout; zoom and pan with mouse.
- **Design**: Flat UI, no gradients; DM Sans and JetBrains Mono fonts; emerald accent; light and dark themes.

---

## Troubleshooting

### UI is blank

1. **FalkorDB must be running** – Start the Docker container (see Quick Start).
2. **Index first** – Run `index_repo` successfully before opening the UI. If the graph is empty, `/graph/nodes` returns `[]` and the UI will show a blank canvas.
3. **Check the browser console** (F12 → Console) – Look for network errors or JavaScript errors.
4. **Verify the API** – Open http://localhost:8000/graph/nodes in a new tab. You should see JSON with `data` arrays. If you get an error or empty arrays, the graph has no data or FalkorDB is unreachable.

### "Address already in use" when running `ui`

Another process is using port 8000. Either:

- Use the existing server and open http://localhost:8000, or
- Stop the other process, or
- Use a different port: `python3 codegraph/cli.py ui --port 8080`

### "No module named 'falkordb'" / "No module named 'codegraph'"

- Install dependencies: `pip install -r requirements.txt`
- If using Conda, ensure you run `pip install` in the active environment: `python3 -m pip install -r requirements.txt`
- Run from the `codegraph-tool` directory so the path resolution works correctly.

### Indexer finds only 1 file

- **File extensions**: The scanner only processes known extensions (`.py`, `.js`, `.ts`, `.cpp`, `.cs`, etc.). Check what extensions your repo uses.
- **Ignored directories**: By default only `.git` is ignored. If you previously had `node_modules` ignored, the scanner now includes it.

### Indexer hangs on "Inserting X functions..."

- Older versions sent one query per node; this was slow for large repos. The current version uses bulk `UNWIND` batches. If you still see hangs, ensure you have the latest `graph_builder.py` with `chunks()` and `UNWIND` logic.

### Ollama "No models found"

- Install and run Ollama, then pull a model: `ollama pull llama3`

### Gource "command not found"

- Install Gource: `brew install gource` (macOS) or your system’s package manager.

---

## Example workflows

### 1. Index and explore a small repo

```bash
python3 codegraph/cli.py index_repo ./small-python-project
python3 codegraph/cli.py ui
# Open http://localhost:8000, click nodes to expand
```

### 2. Ask questions about the codebase

```bash
python3 codegraph/cli.py ask "What functions does the auth module use?"
python3 codegraph/cli.py find_callers validate_token
python3 codegraph/cli.py show_dependencies UserService
```

### 3. Animate the graph with Gource

```bash
python3 codegraph/cli.py gource
```

---

## License

MIT
