from falkordb import FalkorDB

def _get_graph():
    return FalkorDB(host='localhost', port=6379).select_graph('codegraph')


def get_node_ids_by_name(name):
    """Return list of (id, label) for nodes with exact name match."""
    g = _get_graph()
    q = "MATCH (n) WHERE n.name = $name RETURN id(n), labels(n)[0] LIMIT 10"
    res = g.query(q, {'name': name}).result_set
    return [(str(r[0]), r[1]) for r in res]

def find_callers(func_name, silent=False):
    g = _get_graph()
    res = g.query("MATCH (caller)-[:CALLS]->(callee {name: $name}) RETURN id(caller), caller.name, labels(caller)[0]", {'name': func_name}).result_set
    rows = [[str(r[0]), r[1], r[2]] for r in res]
    if not silent:
        print(f"Callers of '{func_name}':")
        for r in res:
            print(f" - {r[1]}")
    return rows

def show_dependencies(node_name, silent=False):
    g = _get_graph()
    res = g.query("MATCH (n {name: $name})-[]->(dep) RETURN id(dep), dep.name, labels(dep)[0]", {'name': node_name}).result_set
    rows = [[str(r[0]), r[1], r[2]] for r in res]
    if not silent:
        print(f"Dependencies of '{node_name}':")
        for r in res:
            print(f" - {r[1]} ({r[2]})")
    return rows


def path_between(node_id_from, node_id_to, max_depth=10):
    """Find shortest path(s) between two nodes via CALLS/IMPORTS. Returns list of paths (each path = list of node ids)."""
    from collections import deque
    g = _get_graph()
    try:
        fid, tid = str(node_id_from), str(node_id_to)
    except (TypeError, ValueError):
        return []
    q = "MATCH (a)-[:CALLS|IMPORTS|CONTAINS]->(b) RETURN id(a), id(b)"
    res = g.query(q).result_set
    adj = {}
    for r in res:
        u, v = str(r[0]), str(r[1])
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    # BFS for shortest path
    queue = deque([(fid, [fid])])
    seen = {fid}
    paths = []
    while queue and len(paths) < 5:
        node, path = queue.popleft()
        if len(path) > max_depth:
            continue
        if node == tid:
            paths.append(path)
            continue
        for neighbor in adj.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return paths


def impact_analysis(node_id):
    """All nodes that depend on this node (downstream). Returns dict with node_ids and human-readable list."""
    from collections import deque
    g = _get_graph()
    try:
        nid = str(node_id)
    except (TypeError, ValueError):
        return {"node_ids": [], "summary": []}
    q = "MATCH (a)-[:CALLS|IMPORTS|CONTAINS]->(b) RETURN id(a), id(b)"
    res = g.query(q).result_set
    adj = {}
    for r in res:
        u, v = str(r[0]), str(r[1])
        adj.setdefault(u, []).append(v)
    node_q = deque([nid])
    visited = {nid}
    while node_q and len(visited) < 500:
        n = node_q.popleft()
        for neighbor in adj.get(n, []):
            if neighbor not in visited:
                visited.add(neighbor)
                node_q.append(neighbor)
    visited.discard(nid)
    if not visited:
        return {"node_ids": [], "summary": []}
    ids_list = list(visited)[:100]
    summary = []
    try:
        for i in ids_list:
            r = g.query("MATCH (n) WHERE id(n) = $i RETURN n.name, labels(n)[0]", {'i': int(i)}).result_set
            if r:
                summary.append(f"{r[0][0]} ({r[0][1]})")
    except Exception:
        summary = [f"Node {x}" for x in ids_list[:20]]
    return {"node_ids": ids_list, "summary": summary}


def find_cycles():
    """Detect cycles in CALLS and IMPORTS. Returns list of cycles (each cycle = list of node ids)."""
    from collections import defaultdict
    g = _get_graph()
    q = "MATCH (a)-[:CALLS|IMPORTS]->(b) RETURN id(a), id(b)"
    res = g.query(q).result_set
    edges = [(str(r[0]), str(r[1])) for r in res]
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
    cycles = []
    seen_sigs = set()

    def find_cycle_from(start):
        stack = [(start, [start], {start})]
        while stack:
            node, path, path_set = stack.pop()
            for neighbor in adj.get(node, []):
                if neighbor == start and len(path) > 1:
                    return path + [start]
                if neighbor not in path_set:
                    stack.append((neighbor, path + [neighbor], path_set | {neighbor}))
        return None

    for node in adj:
        cycle = find_cycle_from(node)
        if cycle:
            sig = tuple(sorted(set(cycle)))
            if sig not in seen_sigs:
                seen_sigs.add(sig)
                cycles.append(cycle)
                if len(cycles) >= 20:
                    break
    return cycles


def get_fan_out_map():
    """Return dict of node_id -> count of outgoing CALLS + IMPORTS + CONTAINS."""
    g = _get_graph()
    q = """
    MATCH (n)-[r:CALLS|IMPORTS|CONTAINS]->()
    RETURN id(n) as nid, count(r) as cnt
    """
    res = g.query(q).result_set
    return {str(r[0]): r[1] for r in res}