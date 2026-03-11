from falkordb import FalkorDB

def find_callers(func_name):
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')
    res = g.query("MATCH (caller)-[:CALLS]->(callee {name: $name}) RETURN caller.name", {'name': func_name}).result_set
    print(f"Callers of '{func_name}':")
    for r in res:
        print(f" - {r[0]}")

def show_dependencies(node_name):
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')
    res = g.query("MATCH (n {name: $name})-[]->(dep) RETURN dep.name, labels(dep)[0]", {'name': node_name}).result_set
    print(f"Dependencies of '{node_name}':")
    for r in res:
        print(f" - {r[0]} ({r[1]})")