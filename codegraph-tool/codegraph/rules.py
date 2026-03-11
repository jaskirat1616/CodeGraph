"""Architecture rules validation. Create codegraph_rules.json in project root to define rules.

Example rules.json:
{
  "forbidden": [
    {"from": "api", "to": "db"},
    {"from": "ui", "to": "api"}
  ]
}
"""
import os
import json

_RULES_FILE = "codegraph_rules.json"

def _load_rules():
    for path in [os.path.join(os.getcwd(), _RULES_FILE), os.path.join(os.path.dirname(__file__), "..", _RULES_FILE)]:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    return {"forbidden": []}

def check_rules():
    """Validate graph against rules. Returns list of violations."""
    rules = _load_rules()
    forbidden = rules.get("forbidden") or []
    if not forbidden:
        return []
    from codegraph.query_engine import _get_graph
    g = _get_graph()
    violations = []
    for pair in forbidden:
        src, tgt = pair.get("from", "").lower(), pair.get("to", "").lower()
        if not src or not tgt:
            continue
        try:
            res = g.query(
                "MATCH (a)-[:CALLS|IMPORTS]->(b) RETURN id(a), id(b), a.name, b.name, a.file, b.file"
            ).result_set
            for r in res:
                from_path = (r[4] or r[2] or "").lower()
                to_path = (r[5] or r[3] or "").lower()
                if src in from_path and tgt in to_path:
                    violations.append({
                        "rule": f"{pair.get('from')} must not depend on {pair.get('to')}",
                        "from": r[2] or "",
                        "to": r[3] or "",
                        "from_id": str(r[0]),
                        "to_id": str(r[1]),
                    })
        except Exception:
            pass
    return violations
