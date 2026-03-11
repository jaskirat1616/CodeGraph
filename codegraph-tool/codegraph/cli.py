import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import uvicorn
from codegraph.repo_scanner import scan_repository
from codegraph.graph_builder import insert_into_falkordb
from codegraph.ollama_agent import ask_question
from codegraph.query_engine import find_callers, show_dependencies, path_between, impact_analysis, find_cycles, get_node_ids_by_name
from codegraph.rules import check_rules as rules_check
from codegraph.gource_exporter import run_gource

def main():
    parser = argparse.ArgumentParser(description="CodeGraph Developer Tool")
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index_repo")
    index_parser.add_argument("path", help="Path to repository")
    index_parser.add_argument("--watch", action="store_true", help="Watch for changes and re-index")
    
    update_parser = subparsers.add_parser("update_repo")
    update_parser.add_argument("path", help="Path to repository (re-indexes for now)")

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question", help="Question to ask Ollama")
    ask_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    find_parser = subparsers.add_parser("find_callers")
    find_parser.add_argument("func", help="Function name to find callers for")
    find_parser.add_argument("--json", action="store_true", help="Output JSON for piping")
    
    deps_parser = subparsers.add_parser("show_dependencies")
    deps_parser.add_argument("node", help="Node name to find dependencies for")
    deps_parser.add_argument("--json", action="store_true", help="Output JSON for piping")
    
    path_parser = subparsers.add_parser("path")
    path_parser.add_argument("from_name", help="Source node/function name")
    path_parser.add_argument("to_name", help="Target node/function name")
    path_parser.add_argument("--json", action="store_true", help="Output JSON")
    
    impact_parser = subparsers.add_parser("impact")
    impact_parser.add_argument("node", help="Node name for impact analysis")
    impact_parser.add_argument("--json", action="store_true", help="Output JSON")
    
    cycles_parser = subparsers.add_parser("cycles")
    cycles_parser.add_argument("--json", action="store_true", help="Output JSON")
    
    docs_parser = subparsers.add_parser("generate_docs")
    docs_parser.add_argument("--topic", default="overview", help="Topic, e.g. 'auth', 'overview'")
    docs_parser.add_argument("--output", "-o", default="-", help="Output file (- for stdout)")
    
    rules_parser = subparsers.add_parser("check_rules")
    rules_parser.add_argument("--json", action="store_true", help="Output JSON")
    
    ui_parser = subparsers.add_parser("ui")
    ui_parser.add_argument("--port", default=8000, type=int)

    gource_parser = subparsers.add_parser("gource")
    gource_parser.add_argument("--files-only", action="store_true", help="Export only files (faster for huge graphs)")
    gource_parser.add_argument("--detailed", action="store_true", help="Export full graph (no limit), slower animation for detail")
    gource_parser.add_argument("--limit", type=int, default=10000, help="Max nodes per type (default 10000)")
    
    args = parser.parse_args()

    if args.command in ("index_repo", "update_repo"):
        if getattr(args, 'watch', False):
            from codegraph.watcher import watch_and_index
            watch_and_index(args.path)
        else:
            entities = scan_repository(args.path)
            insert_into_falkordb(args.path, entities)
    elif args.command == "ask":
        from codegraph.ollama_agent import chat_codegraph, list_models
        models = list_models(prefer_light=True)
        if not models:
            print("No Ollama models. Run: ollama pull llama3.2", file=sys.stderr)
            sys.exit(1)
        out = chat_codegraph(args.question, models[0]["name"], is_cli=not getattr(args, 'json', False))
        if getattr(args, 'json', False) and out:
            print(json.dumps(out))
    elif args.command == "find_callers":
        rows = find_callers(args.func, silent=True)
        if getattr(args, 'json', False):
            print(json.dumps([{"id": r[0], "name": r[1], "label": r[2]} for r in rows]))
        else:
            print(f"Callers of '{args.func}':")
            for r in rows:
                print(f" - {r[1]}")
    elif args.command == "show_dependencies":
        rows = show_dependencies(args.node, silent=True)
        if getattr(args, 'json', False):
            print(json.dumps([{"id": r[0], "name": r[1], "label": r[2]} for r in rows]))
        else:
            print(f"Dependencies of '{args.node}':")
            for r in rows:
                print(f" - {r[1]} ({r[2]})")
    elif args.command == "path":
        from_ids = get_node_ids_by_name(args.from_name)
        to_ids = get_node_ids_by_name(args.to_name)
        if not from_ids or not to_ids:
            print("Could not find nodes", file=sys.stderr)
            sys.exit(1)
        paths = []
        for fid, _ in from_ids[:2]:
            for tid, _ in to_ids[:2]:
                p = path_between(fid, tid)
                paths.extend(p)
        if getattr(args, 'json', False):
            print(json.dumps({"paths": paths}))
        else:
            for i, p in enumerate(paths[:5]):
                print(f"Path {i+1}: {' -> '.join(p)}")
    elif args.command == "impact":
        matches = get_node_ids_by_name(args.node)
        if not matches:
            print(f"Node '{args.node}' not found", file=sys.stderr)
            sys.exit(1)
        out = impact_analysis(matches[0][0])
        if getattr(args, 'json', False):
            print(json.dumps(out))
        else:
            print(f"Impact of '{args.node}' ({len(out['node_ids'])} downstream nodes):")
            for s in out["summary"][:20]:
                print(f" - {s}")
    elif args.command == "cycles":
        cycles = find_cycles()
        if getattr(args, 'json', False):
            print(json.dumps({"cycles": cycles}))
        else:
            if not cycles:
                print("No circular dependencies found.")
            else:
                print(f"Found {len(cycles)} cycle(s):")
                for i, c in enumerate(cycles[:10]):
                    print(f"  {i+1}: {' -> '.join(c)}")
    elif args.command == "ui":
        uvicorn.run("server.api:app", host="0.0.0.0", port=args.port, reload=True)
    elif args.command == "gource":
        run_gource(files_only=args.files_only, limit=args.limit, detailed=args.detailed)
    elif args.command == "generate_docs":
        from codegraph.ollama_agent import generate_architecture_doc
        doc = generate_architecture_doc(args.topic)
        if args.output == "-":
            print(doc)
        else:
            with open(args.output, "w") as f:
                f.write(doc)
            print(f"Wrote {args.output}")
    elif args.command == "check_rules":
        violations = rules_check()
        if getattr(args, 'json', False):
            print(json.dumps({"violations": violations}))
        else:
            if not violations:
                print("No rule violations found.")
            else:
                print(f"Found {len(violations)} violation(s):")
                for v in violations:
                    print(f"  - {v.get('rule', '')}: {v.get('from')} -> {v.get('to')}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()