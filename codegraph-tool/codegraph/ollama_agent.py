import ollama
from falkordb import FalkorDB

def ask_question(question):
    models = ollama.list()['models']
    if not models:
        print("No ollama models found. Please pull a model first.")
        return
    model_name = models[0]['name']
    
    prompt = f"""You are a Cypher query expert for FalkorDB.
Graph schema:
Nodes: Repository, File, Class, Function, Method, Module
Edges: (Repository)-[:CONTAINS]->(File), (File)-[:CONTAINS]->(Class/Function), (Class)-[:CONTAINS]->(Method), (Function/Method/Class)-[:CALLS]->(Function/Method/Class), (File)-[:IMPORTS]->(Module).

Translate this question into a Cypher query: '{question}'
Only return the raw Cypher query, without any markdown formatting or explanation."""

    response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
    cypher = response['message']['content'].strip()
    
    if cypher.startswith("```"):
        cypher = cypher.split("\n", 1)[1].rsplit("\n", 1)[0]
    
    print(f"\n[Generated Cypher]:\n{cypher}")
    
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')
    
    try:
        results = g.query(cypher).result_set
    except Exception as e:
        results = f"Error executing query: {e}"
        
    print(f"\n[FalkorDB Results]:\n{results}")
    
    explain_prompt = f"""Question: {question}
Cypher executed: {cypher}
Database Results: {results}
Explain the results to the user simply and clearly."""

    explain_response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': explain_prompt}])
    print(f"\n[AI Explanation]:\n{explain_response['message']['content']}")