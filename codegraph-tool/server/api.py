import os
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/graph/nodes")
def get_nodes(
    limit: int = Query(500, description="Max nodes to return"),
    view: str = Query("files", description="'files' = Repository+File only (lightweight), 'full' = +Class+Module")
):
    # File-level view: Repository + Files only - lightweight for huge graphs
    if view == "files":
        labels_filter = ["Repository", "File"]
    else:
        labels_filter = ["Repository", "File", "Class", "Module"]
    labels_str = "', '".join(labels_filter)
    query = f"""
    MATCH (n)
    WHERE labels(n)[0] IN ['{labels_str}']
    RETURN id(n), labels(n)[0], n.name, n.path 
    LIMIT {limit}
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
    view: str = Query("files", description="'files' or 'full' - must match nodes view")
):
    if view == "files":
        labels_filter = ["Repository", "File"]
    else:
        labels_filter = ["Repository", "File", "Class", "Module"]
    labels_str = "', '".join(labels_filter)
    query = f"""
    MATCH (a)-[r]->(b)
    WHERE labels(a)[0] IN ['{labels_str}']
      AND labels(b)[0] IN ['{labels_str}']
    RETURN id(a), id(b), type(r)
    LIMIT {limit}
    """
    res = g.query(query).result_set
    return [{"data": {"source": str(r[0]), "target": str(r[1]), "label": r[2]}} for r in res]

@app.get("/graph/node/{node_id}")
def get_node_details(node_id: int):
    """Return details for a single node (path, label, name)."""
    res = g.query(
        "MATCH (n) WHERE id(n) = $nid RETURN id(n), labels(n)[0], n.name, n.path",
        {'nid': node_id}
    ).result_set
    if not res:
        return {"error": "Node not found"}
    r = res[0]
    name = r[2] if r[2] else (r[3] or "")
    path = r[3] if r[3] else ""
    return {
        "id": str(r[0]),
        "label": r[1],
        "name": name or path or "",
        "path": path
    }

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

ui_path = os.path.join(os.path.dirname(__file__), "..", "ui")
app.mount("/", StaticFiles(directory=ui_path, html=True), name="ui")