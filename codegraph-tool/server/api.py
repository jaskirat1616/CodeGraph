import os
from fastapi import FastAPI, Query, HTTPException
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


ui_path = os.path.join(os.path.dirname(__file__), "..", "ui")
app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")