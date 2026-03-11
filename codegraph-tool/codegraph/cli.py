import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import uvicorn
from codegraph.repo_scanner import scan_repository
from codegraph.graph_builder import insert_into_falkordb
from codegraph.ollama_agent import ask_question
from codegraph.query_engine import find_callers, show_dependencies
from codegraph.gource_exporter import run_gource

def main():
    parser = argparse.ArgumentParser(description="CodeGraph Developer Tool")
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser("index_repo")
    index_parser.add_argument("path", help="Path to repository")
    
    update_parser = subparsers.add_parser("update_repo")
    update_parser.add_argument("path", help="Path to repository (re-indexes for now)")

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question", help="Question to ask Ollama")
    
    find_parser = subparsers.add_parser("find_callers")
    find_parser.add_argument("func", help="Function name to find callers for")
    
    deps_parser = subparsers.add_parser("show_dependencies")
    deps_parser.add_argument("node", help="Node name to find dependencies for")
    
    ui_parser = subparsers.add_parser("ui")
    ui_parser.add_argument("--port", default=8000, type=int)

    gource_parser = subparsers.add_parser("gource")
    gource_parser.add_argument("--files-only", action="store_true", help="Export only files (faster for huge graphs)")
    gource_parser.add_argument("--detailed", action="store_true", help="Export full graph (no limit), slower animation for detail")
    gource_parser.add_argument("--limit", type=int, default=10000, help="Max nodes per type (default 10000)")
    
    args = parser.parse_args()

    if args.command in ("index_repo", "update_repo"):
        entities = scan_repository(args.path)
        insert_into_falkordb(args.path, entities)
    elif args.command == "ask":
        ask_question(args.question)
    elif args.command == "find_callers":
        find_callers(args.func)
    elif args.command == "show_dependencies":
        show_dependencies(args.node)
    elif args.command == "ui":
        uvicorn.run("server.api:app", host="0.0.0.0", port=args.port, reload=True)
    elif args.command == "gource":
        run_gource(files_only=args.files_only, limit=args.limit, detailed=args.detailed)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()