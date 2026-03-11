import json
import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from falkordb import FalkorDB

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = FalkorDB(host='localhost', port=6379)
g = db.select_graph('codegraph')

def _labels_for_view(view: str):
    if view == "files":
        return ["Repository", "File"]
    if view == "full":
        return ["Repository", "File", "Class", "Module"]
    if view == "complete":
        return ["Repository", "File", "Class", "Module", "Function", "Method"]
    return ["Repository", "File"]

@app.get("/graph/nodes")
def get_nodes(
    limit: int = Query(500, description="Max nodes to return"),
    view: str = Query("files", description="'files' = Repo+File, 'full' = +Class+Module, 'complete' = +Function+Method (all nodes + CALLS/IMPORTS)")
):
    labels_filter = _labels_for_view(view)
    limit_actual = 2000 if view == "complete" else limit
    labels_str = "', '".join(labels_filter)
    query = f"""
    MATCH (n)
    WHERE labels(n)[0] IN ['{labels_str}']
    RETURN id(n), labels(n)[0], n.name, COALESCE(n.path, n.file, '')
    LIMIT {limit_actual}
    """
    res = g.query(query).result_set
    nodes = []
    for r in res:
        name = r[2] if r[2] else (r[3] or "")
        path = r[3] if r[3] else ""
        nodes.append({"data": {"id": str(r[0]), "label": r[1], "name": name or path or "", "path": path}})
    return nodes

@app.get("/graph/edges")
def get_edges(
    limit: int = Query(1000, description="Max edges to return"),
    view: str = Query("files", description="'files', 'full', or 'complete' - must match nodes view")
):
    labels_filter = _labels_for_view(view)
    limit_actual = 5000 if view == "complete" else limit
    labels_str = "', '".join(labels_filter)
    query = f"""
    MATCH (a)-[r]->(b)
    WHERE labels(a)[0] IN ['{labels_str}']
      AND labels(b)[0] IN ['{labels_str}']
    RETURN id(a), id(b), type(r)
    LIMIT {limit_actual}
    """
    res = g.query(query).result_set
    return [{"data": {"source": str(r[0]), "target": str(r[1]), "label": r[2]}} for r in res]

@app.get("/graph/node/{node_id}")
def get_node_details(node_id: int):
    """Return details for a single node (path, label, name, line numbers)."""
    res = g.query(
        "MATCH (n) WHERE id(n) = $nid RETURN id(n), labels(n)[0], n.name, n.path, n.file, n.start_line, n.end_line",
        {'nid': node_id}
    ).result_set
    if not res:
        return {"error": "Node not found"}
    r = res[0]
    name = r[2] if r[2] else (r[3] or r[4] or "")
    path = r[3] or r[4] or ""  # path for File, file for Class/Function/Method
    start_line = r[5] if len(r) > 5 and r[5] is not None else None
    end_line = r[6] if len(r) > 6 and r[6] is not None else None
    return {
        "id": str(r[0]),
        "label": r[1],
        "name": name or path or "",
        "path": path,
        "start_line": start_line,
        "end_line": end_line
    }


@app.get("/graph/node/{node_id}/code")
def get_node_code(node_id: int):
    """Return source code for a node (File: full file; Class/Function/Method: line range)."""
    res = g.query(
        "MATCH (n) WHERE id(n) = $nid RETURN labels(n)[0], n.path, n.file, n.start_line, n.end_line",
        {'nid': node_id}
    ).result_set
    if not res:
        return {"error": "Node not found", "code": None}
    label, path, file_path, start_line, end_line = res[0]
    filepath = path or file_path or ""
    if not filepath or not os.path.exists(filepath):
        return {"error": "File not found or not accessible", "code": None}

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return {"error": str(e), "code": None}

    if label == "File":
        code = "".join(lines)
    elif start_line is not None and end_line is not None:
        code = "".join(lines[start_line - 1 : end_line])
    else:
        code = "".join(lines)

    return {"code": code, "path": filepath, "start_line": start_line, "end_line": end_line}

@app.get("/graph/path")
def get_path(from_id: int = Query(..., description="Source node id"), to_id: int = Query(..., description="Target node id")):
    """Shortest path between two nodes."""
    from codegraph.query_engine import path_between
    paths = path_between(from_id, to_id)
    return {"paths": paths, "node_ids": list(set(n for p in paths for n in p))}


@app.get("/graph/impact/{node_id}")
def get_impact(node_id: int):
    """Downstream impact: all nodes that depend on this node."""
    from codegraph.query_engine import impact_analysis
    return impact_analysis(node_id)


@app.get("/graph/cycles")
def get_cycles():
    """Detect circular dependencies in CALLS/IMPORTS."""
    from codegraph.query_engine import find_cycles
    cycles = find_cycles()
    all_ids = list(set(n for c in cycles for n in c))
    return {"cycles": cycles, "node_ids": all_ids}


@app.get("/graph/rules/check")
def check_architecture_rules():
    """Check graph against codegraph_rules.json. Returns violations."""
    try:
        from codegraph.rules import check_rules
        violations = check_rules()
        ids = list(set(v["from_id"] for v in violations) | set(v["to_id"] for v in violations))
        return {"violations": violations, "highlight_ids": ids}
    except Exception as e:
        return {"violations": [], "error": str(e)}


@app.get("/graph/fan-out")
def get_fan_out():
    """Map of node_id -> outgoing edge count (for hotspot sizing)."""
    from codegraph.query_engine import get_fan_out_map
    return get_fan_out_map()


@app.get("/graph/expand/{node_id}")
def expand_node(node_id: int):
    # Endpoint to fetch children dynamically when a node is clicked
    res = g.query(
        "MATCH (a)-[r]->(b) WHERE id(a) = $nid RETURN id(b), labels(b)[0], b.name, b.path, type(r)",
        {'nid': node_id}
    ).result_set
    
    nodes = []
    edges = []
    for r in res:
        name = r[2] if r[2] else (r[3] or "")
        path = r[3] if r[3] else ""
        child_id = str(r[0])
        nodes.append({"data": {"id": child_id, "label": r[1], "name": name or path or "", "path": path}})
        edges.append({"data": {"source": str(node_id), "target": child_id, "label": r[4]}})
        
    return {"nodes": nodes, "edges": edges}


# --- Command execution ---
class CommandRequest(BaseModel):
    command: str
    args: dict = {}

@app.post("/command/execute")
def execute_command(req: CommandRequest):
    """Execute CLI-like commands: index_repo, find_callers, show_dependencies."""
    try:
        if req.command == "index_repo":
            path = (req.args.get("path") or "").strip()
            if not path:
                return {"ok": False, "error": "Missing path", "output": None}
            if not os.path.isdir(path) and not os.path.isfile(path):
                return {"ok": False, "error": f"Path not found: {path}", "output": None}
            from codegraph.repo_scanner import scan_repository
            from codegraph.graph_builder import insert_into_falkordb
            entities = scan_repository(path)
            insert_into_falkordb(path, entities)
            nf = len(entities["files"])
            nc = len(entities["classes"])
            nfn = len(entities["functions"])
            nm = len(entities["methods"])
            return {"ok": True, "output": f"Indexed {nf} files, {nc} classes, {nfn} functions, {nm} methods."}
        if req.command == "find_callers":
            func = (req.args.get("func") or req.args.get("name") or "").strip()
            if not func:
                return {"ok": False, "error": "Missing function name", "output": None}
            from codegraph.query_engine import find_callers
            rows = find_callers(func, silent=True)
            return {"ok": True, "output": rows, "highlight_ids": [r[0] for r in rows]}
        if req.command == "show_dependencies":
            node = (req.args.get("node") or req.args.get("name") or "").strip()
            if not node:
                return {"ok": False, "error": "Missing node name", "output": None}
            from codegraph.query_engine import show_dependencies
            rows = show_dependencies(node, silent=True)
            return {"ok": True, "output": rows, "highlight_ids": [r[0] for r in rows]}
        return {"ok": False, "error": f"Unknown command: {req.command}", "output": None}
    except Exception as e:
        return {"ok": False, "error": str(e), "output": None}


# --- Ollama explain ---
class ExplainRequest(BaseModel):
    node_id: int
    model: str | None = None

@app.post("/ollama/explain")
def explain_node(req: ExplainRequest):
    """AI explanation of a node's role in the codebase."""
    try:
        from codegraph.ollama_agent import explain_node_llm, list_models
        models = list_models(prefer_light=True)
        if not models:
            raise HTTPException(status_code=503, detail="No Ollama models. Run: ollama pull llama3.2")
        model_name = req.model or models[0]["name"]
        explanation = explain_node_llm(req.node_id, model_name)
        return {"explanation": explanation}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Ollama chat ---
class ChatRequest(BaseModel):
    question: str
    model: str | None = None


@app.get("/ollama/models")
def get_ollama_models():
    """List available Ollama models; light models first."""
    try:
        from codegraph.ollama_agent import list_models
        models = list_models(prefer_light=True)
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@app.post("/ollama/chat")
def ollama_chat(req: ChatRequest):
    """Chat with Ollama about the code graph."""
    try:
        from codegraph.ollama_agent import chat_codegraph, list_models
        models = list_models(prefer_light=True)
        if not models:
            raise HTTPException(status_code=503, detail="No Ollama models found. Pull one first: ollama pull llama3.2")
        model_name = req.model or models[0]["name"]
        out = chat_codegraph(req.question, model_name, is_cli=False)
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ollama/chat/stream")
def ollama_chat_stream(req: ChatRequest):
    """Stream chat with thinking steps."""
    def gen():
        try:
            from codegraph.ollama_agent import chat_codegraph_stream, list_models
            models = list_models(prefer_light=True)
            if not models:
                yield json.dumps({"stage": "error", "content": "No Ollama models"}) + "\n"
                return
            model_name = req.model or models[0]["name"]
            for obj in chat_codegraph_stream(req.question, model_name):
                yield json.dumps(obj) + "\n"
        except Exception as e:
            yield json.dumps({"stage": "error", "content": str(e)}) + "\n"

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
    )


ui_path = os.path.join(os.path.dirname(__file__), "..", "ui")
app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")