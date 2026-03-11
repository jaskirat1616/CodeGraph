import os
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

def explain_node_llm(node_id, model_name):
    """Generate AI explanation of a node's role in the codebase."""
    from codegraph.query_engine import _get_graph
    g = _get_graph()
    res = g.query(
        "MATCH (n) WHERE id(n) = $nid RETURN labels(n)[0], n.name, n.path, n.file",
        {'nid': int(node_id)}
    ).result_set
    if not res:
        return "Node not found."
    label, name, path, filepath = res[0]
    path = path or filepath or ""
    # Get code snippet if available
    code = ""
    try:
        code_res = g.query(
            "MATCH (n) WHERE id(n) = $nid RETURN n.start_line, n.end_line, n.path, n.file",
            {'nid': int(node_id)}
        ).result_set
        if code_res and (code_res[0][2] or code_res[0][3]):
            fp = code_res[0][2] or code_res[0][3]
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                sl, el = code_res[0][0], code_res[0][1]
                if sl and el:
                    code = "".join(lines[sl - 1:el])[:1500]
    except Exception:
        pass
    prompt = f"""This is a {label} node in a code graph:
- Name: {name}
- Path: {path}
{'- Code snippet:' + chr(10) + '```' + chr(10) + code + chr(10) + '```' if code else ''}

Explain in 2-4 sentences: what this does, its role in the codebase, and how it likely connects to other parts. Use **bold** for key terms. Be concise."""
    resp = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
    return resp["message"]["content"]


def generate_architecture_doc(topic="overview"):
    """Generate markdown architecture doc from graph + Ollama."""
    models = list_models(prefer_light=True)
    if not models:
        return "# Architecture\n\nNo Ollama models. Run: ollama pull llama3.2"
    model_name = models[0]["name"]
    db = FalkorDB(host="localhost", port=6379)
    g = db.select_graph("codegraph")
    stats = []
    for q, label in [
        ("MATCH (n:Repository) RETURN count(n)", "Repositories"),
        ("MATCH (n:File) RETURN count(n)", "Files"),
        ("MATCH (n:Class) RETURN count(n)", "Classes"),
        ("MATCH (n:Function) RETURN count(n)", "Functions"),
        ("MATCH (n:Method) RETURN count(n)", "Methods"),
        ("MATCH ()-[r:CALLS]->() RETURN count(r)", "CALLS edges"),
        ("MATCH ()-[r:IMPORTS]->() RETURN count(r)", "IMPORTS edges"),
    ]:
        try:
            r = g.query(q).result_set
            stats.append(f"- {label}: {r[0][0] if r else 0}")
        except Exception:
            pass
    try:
        r = g.query("MATCH (f:File) RETURN f.path LIMIT 20").result_set
        files = [x[0] for x in r if x and x[0]]
    except Exception:
        files = []
    ctx = "\n".join(stats) + "\n\nSample files:\n" + "\n".join(f"- " + str(f) for f in files[:15])
    prompt = f"""Given this code graph summary:
{ctx}

Generate a concise markdown architecture document (1-2 pages) for topic "{topic}". Include: high-level structure, main components, and how they connect. Use headers, bullets, and `code` for names. Be direct."""
    resp = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
    return resp["message"]["content"]


def ask_question(question, model_name=None):
    models = list_models(prefer_light=True)
    if not models:
        print("No ollama models found. Please pull a model first.")
        return
    model_name = model_name or models[0]['name']
    return chat_codegraph(question, model_name, is_cli=True)


COMMAND_INTENT_PROMPT = """The user may ask to RUN a command or QUERY the graph. Commands:
- index_repo <path>: index a repository (e.g. "index /path/to/repo")
- find_callers <name>: find what calls a function (e.g. "find callers of foo")
- show_dependencies <name>: show what a node depends on (e.g. "dependencies of X")
- path_between <from> <to>: path connecting two nodes (e.g. "path from main to validate", "how does X connect to Y")
- impact <name>: what breaks if this changes (e.g. "impact of foo", "what breaks if I change X")
- find_cycles: detect circular dependencies (e.g. "find cycles", "circular dependencies")
- check_rules: validate architecture rules (e.g. "check rules", "validate architecture")

If the user clearly wants one of these, reply EXACTLY one line (nothing else):
COMMAND:index_repo:<path>
COMMAND:find_callers:<name>
COMMAND:show_dependencies:<name>
COMMAND:path_between:<from_name>:<to_name>
COMMAND:impact:<node_name>
COMMAND:find_cycles
COMMAND:check_rules

For path_between use the two node/function names the user gave. For find_cycles and check_rules no args. For "index this repo" use .
Otherwise reply: QUERY
"""

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


def _parse_command_intent(text):
    """Parse COMMAND:name:args from model output. Returns (command, args) or None."""
    text = (text or "").strip()
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("COMMAND:"):
            rest = line[8:].strip()
            parts = rest.split(":", 1)
            name = (parts[0] or "").strip().lower()
            arg = (parts[1] if len(parts) > 1 else "").strip()
            if name == "index_repo":
                return ("index_repo", {"path": arg or "."})
            if name == "find_callers":
                return ("find_callers", {"func": arg})
            if name == "show_dependencies":
                return ("show_dependencies", {"node": arg})
            if name == "find_cycles":
                return ("find_cycles", {})
            if name == "check_rules":
                return ("check_rules", {})
            if name == "path_between" and ":" in arg:
                from_name, to_name = arg.split(":", 1)
                return ("path_between", {"from": from_name.strip(), "to": to_name.strip()})
            if name == "impact":
                return ("impact", {"node": arg})
    return None


def _run_command(command, args):
    """Run command and return (ok, output, highlight_ids)."""
    try:
        if command == "index_repo":
            path = (args.get("path") or ".").strip()
            if not path:
                return (False, "Missing path", None)
            if not os.path.isdir(path) and not os.path.isfile(path):
                return (False, f"Path not found: {path}", None)
            from codegraph.repo_scanner import scan_repository
            from codegraph.graph_builder import insert_into_falkordb
            entities = scan_repository(path)
            insert_into_falkordb(path, entities)
            nf, nc, nfn, nm = len(entities["files"]), len(entities["classes"]), len(entities["functions"]), len(entities["methods"])
            return (True, f"Indexed {nf} files, {nc} classes, {nfn} functions, {nm} methods.", None)
        if command == "find_callers":
            func = (args.get("func") or args.get("name") or "").strip()
            if not func:
                return (False, "Missing function name", None)
            from codegraph.query_engine import find_callers
            rows = find_callers(func, silent=True)
            ids = [r[0] for r in rows]
            lines = [f"- {r[1]} ({r[2]})" for r in rows]
            return (True, f"Callers of `{func}`:\n" + ("\n".join(lines) if lines else "None found."), ids)
        if command == "show_dependencies":
            node = (args.get("node") or args.get("name") or "").strip()
            if not node:
                return (False, "Missing node name", None)
            from codegraph.query_engine import show_dependencies
            rows = show_dependencies(node, silent=True)
            ids = [r[0] for r in rows]
            lines = [f"- {r[1]} ({r[2]})" for r in rows]
            return (True, f"Dependencies of `{node}`:\n" + ("\n".join(lines) if lines else "None."), ids)
        if command == "path_between":
            from_name = (args.get("from") or "").strip()
            to_name = (args.get("to") or "").strip()
            if not from_name or not to_name:
                return (False, "Need both from and to node names", None)
            from codegraph.query_engine import get_node_ids_by_name, path_between
            from_ids = get_node_ids_by_name(from_name)
            to_ids = get_node_ids_by_name(to_name)
            if not from_ids or not to_ids:
                return (False, f"Could not find nodes for '{from_name}' or '{to_name}'", None)
            all_ids = []
            for fid, _ in from_ids[:3]:
                for tid, _ in to_ids[:3]:
                    paths = path_between(fid, tid)
                    for p in paths:
                        all_ids.extend(p)
            all_ids = list(dict.fromkeys(all_ids))
            if not all_ids:
                return (True, f"No path found between `{from_name}` and `{to_name}`.", [])
            return (True, f"Path between `{from_name}` and `{to_name}`: {len(all_ids)} nodes on path(s).", all_ids)
        if command == "impact":
            node = (args.get("node") or "").strip()
            if not node:
                return (False, "Missing node name", None)
            from codegraph.query_engine import get_node_ids_by_name, impact_analysis
            matches = get_node_ids_by_name(node)
            if not matches:
                return (False, f"Node '{node}' not found", None)
            nid = matches[0][0]
            out = impact_analysis(nid)
            ids = out["node_ids"]
            lines = out["summary"]
            return (True, f"Impact of `{node}` (what depends on it):\n" + ("\n".join("- " + s for s in lines[:30]) if lines else "Nothing depends on it."), ids)
        if command == "find_cycles":
            from codegraph.query_engine import find_cycles
            cycles = find_cycles()
            all_ids = list(set(n for c in cycles for n in c))
            if not cycles:
                return (True, "No circular dependencies found.", [])
            lines = [f"Cycle {i+1}: {' → '.join(c)}" for i, c in enumerate(cycles[:5])]
            return (True, "Circular dependencies:\n" + "\n".join(lines), all_ids)
        if command == "check_rules":
            from codegraph.rules import check_rules
            violations = check_rules()
            ids = list(set(v.get("from_id", "") for v in violations) | set(v.get("to_id", "") for v in violations))
            ids = [x for x in ids if x]
            if not violations:
                return (True, "No architecture rule violations found.", [])
            lines = [f"- {v.get('rule', '')}: {v.get('from')} → {v.get('to')}" for v in violations[:10]]
            return (True, "Rule violations:\n" + "\n".join(lines), ids)
    except Exception as e:
        return (False, str(e), None)
    return (False, f"Unknown command: {command}", None)


def chat_codegraph_stream(question, model_name):
    """Stream chat response for UI: yields dicts with stage, content/message."""
    import json

    yield {"stage": "thinking", "message": "Understanding your request…"}

    # Step 1: Intent detection (command vs query)
    intent_messages = [
        {"role": "system", "content": COMMAND_INTENT_PROMPT},
        {"role": "user", "content": question},
    ]
    intent_resp = ollama.chat(model=model_name, messages=intent_messages)
    intent_text = (intent_resp.get("message", {}).get("content") or "").strip()

    parsed = _parse_command_intent(intent_text)
    if parsed:
        command, args = parsed
        yield {"stage": "thinking", "message": f"Running {command}…"}
        ok, output, highlight_ids = _run_command(command, args)
        if ok:
            yield {"stage": "command_result", "content": output, "highlight_ids": highlight_ids or []}
        else:
            yield {"stage": "error", "content": output}
        yield {"stage": "done"}
        return

    # Step 2: Translate to Cypher (normal query flow)
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