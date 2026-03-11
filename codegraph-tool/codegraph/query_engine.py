from falkordb import FalkorDB

def find_callers(func_name, silent=False):
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')
    res = g.query("MATCH (caller)-[:CALLS]->(callee {name: $name}) RETURN id(caller), caller.name, labels(caller)[0]", {'name': func_name}).result_set
    rows = [[str(r[0]), r[1], r[2]] for r in res]
    if not silent:
        print(f"Callers of '{func_name}':")
        for r in res:
            print(f" - {r[1]}")
    return rows

def show_dependencies(node_name, silent=False):
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')
    res = g.query("MATCH (n {name: $name})-[]->(dep) RETURN id(dep), dep.name, labels(dep)[0]", {'name': node_name}).result_set
    rows = [[str(r[0]), r[1], r[2]] for r in res]
    if not silent:
        print(f"Dependencies of '{node_name}':")
        for r in res:
            print(f" - {r[1]} ({r[2]})")
    return rows