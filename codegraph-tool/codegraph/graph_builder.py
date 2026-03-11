from falkordb import FalkorDB
import os

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def insert_into_falkordb(repo_path, entities):
    db = FalkorDB(host='localhost', port=6379)
    
    # Optional: Clear existing graph before inserting new data
    try:
        db.delete_graph('codegraph')
        print("Cleared existing graph database.")
    except Exception:
        pass
        
    g = db.select_graph('codegraph')
    repo_name = os.path.basename(os.path.abspath(repo_path))
    
    print("Connecting to FalkorDB and inserting graph...")
    g.query("MERGE (r:Repository {name: $name})", {'name': repo_name})
    
    BATCH_SIZE = 1000

    print(f"Inserting {len(entities['files'])} files...")
    for chunk in chunks(entities['files'], BATCH_SIZE):
        g.query("""
        UNWIND $batch AS path
        MERGE (f:File {path: path})
        WITH f
        MATCH (r:Repository {name: $repo})
        MERGE (r)-[:CONTAINS]->(f)
        """, {'batch': chunk, 'repo': repo_name})
        
    print(f"Inserting {len(entities['classes'])} classes...")
    for chunk in chunks(entities['classes'], BATCH_SIZE):
        batch = [dict(c, start_line=c.get('start_line'), end_line=c.get('end_line')) for c in chunk]
        g.query("""
        UNWIND $batch AS c
        MERGE (cls:Class {name: c.name, file: c.filepath})
        SET cls.start_line = c.start_line, cls.end_line = c.end_line
        WITH cls, c
        MATCH (f:File {path: c.filepath})
        MERGE (f)-[:CONTAINS]->(cls)
        """, {'batch': batch})
        
    print(f"Inserting {len(entities['functions'])} functions...")
    for chunk in chunks(entities['functions'], BATCH_SIZE):
        batch = [dict(fn, start_line=fn.get('start_line'), end_line=fn.get('end_line')) for fn in chunk]
        g.query("""
        UNWIND $batch AS fn
        MERGE (func:Function {name: fn.name, file: fn.filepath})
        SET func.start_line = fn.start_line, func.end_line = fn.end_line
        WITH func, fn
        MATCH (f:File {path: fn.filepath})
        MERGE (f)-[:CONTAINS]->(func)
        """, {'batch': batch})
                
    print(f"Inserting {len(entities['methods'])} methods...")
    for chunk in chunks(entities['methods'], BATCH_SIZE):
        batch = [dict(m, start_line=m.get('start_line'), end_line=m.get('end_line')) for m in chunk]
        g.query("""
        UNWIND $batch AS m
        MERGE (meth:Method {name: m.name, class: m.class, file: m.filepath})
        SET meth.start_line = m.start_line, meth.end_line = m.end_line
        WITH meth, m
        MATCH (c:Class {name: m.class, file: m.filepath})
        MERGE (c)-[:CONTAINS]->(meth)
        """, {'batch': batch})

    print(f"Inserting {len(entities['calls'])} calls...")
    call_chunks = list(chunks(entities['calls'], BATCH_SIZE))
    for i, chunk in enumerate(call_chunks):
        if i % 10 == 0 and i > 0:
            print(f"  ... inserted {i * BATCH_SIZE} calls")
        g.query("""
        UNWIND $batch AS call
        MATCH (caller {name: call.caller, file: call.filepath})
        MATCH (callee {name: call.callee})
        MERGE (caller)-[:CALLS]->(callee)
        """, {'batch': chunk})
        
    print(f"Inserting {len(entities['imports'])} imports...")
    for chunk in chunks(entities['imports'], BATCH_SIZE):
        g.query("""
        UNWIND $batch AS imp
        MERGE (m:Module {name: imp.module})
        WITH m, imp
        MATCH (f:File {path: imp.file})
        MERGE (f)-[:IMPORTS]->(m)
        """, {'batch': chunk})
                
    print(f"Graph constructed for {repo_name}!")