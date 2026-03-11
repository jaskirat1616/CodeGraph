import ollama
from falkordb import FalkorDB

# Light/small model name patterns for prioritization
LIGHT_PATTERNS = ['1b', '3b', '0.5b', '2b', ':1b', ':3b', ':0.5b', ':2b', 'mini', 'small', 'tiny', 'nano']

def _is_light_model(name):
    if not name:
        return False
    n = name.lower()
    return any(p in n for p in LIGHT_PATTERNS)

def list_models(prefer_light=True):
    """List Ollama models; optionally sort light models first."""
    try:
        data = ollama.list()
        models = data.get('models', [])
    except Exception:
        return []
    if not models:
        return []
    result = [
        {
            'name': m.get('name', m.get('model_name', '')),
            'size': m.get('size', 0),
            'light': _is_light_model(m.get('name', m.get('model_name', '')))
        }
        for m in models
    ]
    if prefer_light:
        result.sort(key=lambda x: (0 if _is_light_model(x['name']) else 1, x['name']))
    else:
        result.sort(key=lambda x: x['name'])
    return result

def ask_question(question, model_name=None):
    models = list_models(prefer_light=True)
    if not models:
        print("No ollama models found. Please pull a model first.")
        return
    model_name = model_name or models[0]['name']
    return chat_codegraph(question, model_name, is_cli=True)


def chat_codegraph(question, model_name, is_cli=False):
    """
    Ask a question about the code graph; returns cypher, results, explanation.
    If is_cli, also prints to stdout.
    """
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

    if is_cli:
        print(f"\n[Generated Cypher]:\n{cypher}")

    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')

    try:
        raw = g.query(cypher).result_set
        results = [[str(c) if c is not None else None for c in row] for row in raw]
    except Exception as e:
        results = [f"Error executing query: {e}"]

    if is_cli:
        print(f"\n[FalkorDB Results]:\n{results}")

    explain_prompt = f"""Question: {question}
Cypher executed: {cypher}
Database Results: {results}
Explain the results to the user simply and clearly."""

    explain_response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': explain_prompt}])
    explanation = explain_response['message']['content']

    if is_cli:
        print(f"\n[AI Explanation]:\n{explanation}")

    return {'cypher': cypher, 'results': results, 'explanation': explanation}