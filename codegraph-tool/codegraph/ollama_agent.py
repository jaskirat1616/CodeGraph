import ollama
from falkordb import FalkorDB

# Light/small model name patterns for prioritization
LIGHT_PATTERNS = ['1b', '3b', '0.5b', '2b', ':1b', ':3b', ':0.5b', ':2b', 'mini', 'small', 'tiny', 'nano']

def _is_light_model(name):
    if not name:
        return False
    n = name.lower()
    return any(p in n for p in LIGHT_PATTERNS)

def _model_name(m):
    """Extract model name from various Ollama API response formats."""
    if isinstance(m, str):
        return m
    name = m.get('name') or m.get('model_name')
    if name:
        return name
    model = m.get('model')
    if isinstance(model, str):
        return model
    if isinstance(model, dict):
        return model.get('name', model.get('model_name', ''))
    return ''


def list_models(prefer_light=True):
    """List Ollama models; optionally sort light models first."""
    try:
        data = ollama.list()
        models = data.get('models', []) or []
    except Exception:
        return []
    if not models:
        return []
    result = []
    for m in models:
        name = _model_name(m)
        if name:
            result.append({
                'name': name,
                'size': m.get('size', 0) if isinstance(m, dict) else 0,
                'light': _is_light_model(name)
            })
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


SYSTEM_PROMPT = """You are an expert at querying codebases using Cypher for FalkorDB. Your role is to translate natural language questions about a code graph into precise, correct Cypher queries.

## Graph schema

**Nodes:** Repository, File, Class, Function, Method, Module

**Relationships:**
- (Repository)-[:CONTAINS]->(File)
- (File)-[:CONTAINS]->(Class|Function)
- (Class)-[:CONTAINS]->(Method)
- (Function|Method|Class)-[:CALLS]->(Function|Method|Class)
- (File)-[:IMPORTS]->(Module)

**Properties:**
- File, Class, Function, Method: `name`, `file` (path)
- Use `labels(n)[0]` for node type, `id(n)` for node id

## Rules
- Return ONLY the raw Cypher query. No markdown, no code blocks, no explanation.
- Use MATCH, OPTIONAL MATCH, RETURN. Prefer concise queries. Limit results when appropriate (e.g. LIMIT 50).
- When returning nodes, include id(n) as the first column so the UI can highlight them: RETURN id(n), n.name, ...
- Match exact names with {name: 'value'}. For partial matches use CONTAINS or =~."""


def chat_codegraph(question, model_name, is_cli=False):
    """
    Ask a question about the code graph; returns cypher, results, explanation.
    If is_cli, also prints to stdout.
    """
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': f"Translate this question into a Cypher query: {question}"},
    ]
    response = ollama.chat(model=model_name, messages=messages)
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

    explain_prompt = f"""The user asked: "{question}"

You ran this Cypher query:
```cypher
{cypher}
```

Results: {results}

Respond in **markdown**: 1-3 concise sentences explaining what the results mean. Use **bold** for emphasis, `code` for names, and lists if there are multiple items. Be direct and helpful."""

    explain_response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': explain_prompt}])
    explanation = explain_response['message']['content']

    if is_cli:
        print(f"\n[AI Explanation]:\n{explanation}")

    return {'cypher': cypher, 'results': results, 'explanation': explanation}


def chat_codegraph_stream(question, model_name):
    """Stream chat response for UI: yields dicts with stage, content/message."""
    import json

    yield {"stage": "thinking", "message": "Translating to Cypher…"}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Translate this question into a Cypher query: {question}"},
    ]
    response = ollama.chat(model=model_name, messages=messages)
    cypher = response["message"]["content"].strip()
    if cypher.startswith("```"):
        cypher = cypher.split("\n", 1)[1].rsplit("\n", 1)[0]

    yield {"stage": "cypher", "content": cypher}

    db = FalkorDB(host="localhost", port=6379)
    g = db.select_graph("codegraph")
    try:
        raw = g.query(cypher).result_set
        results = [[str(c) if c is not None else None for c in row] for row in raw]
    except Exception as e:
        results = [str(e)]

    yield {"stage": "results", "content": results}

    yield {"stage": "thinking", "message": "Explaining results…"}

    explain_prompt = f'''The user asked: "{question}"

Cypher executed:
```cypher
{cypher}
```

Results: {results}

Respond in **markdown**: 1-3 concise sentences explaining what the results mean. Use **bold**, `code`, and lists as needed. Be direct and helpful.'''

    stream = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": explain_prompt}],
        stream=True,
    )
    for chunk in stream:
        part = chunk.get("message", {}).get("content", "")
        if part:
            yield {"stage": "explanation", "content": part}

    yield {"stage": "done"}