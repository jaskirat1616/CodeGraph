# CodeGraph Feature Implementation Plan

**Status: IMPLEMENTED**

All phases completed. Summary of changes:

## Implemented

- **Export PNG**: Toolbar button, uses 3d-force-graph renderer + toBlob
- **CLI --json**: find_callers, show_dependencies, ask, path, impact, cycles
- **Shareable links**: `?view=X&highlight=id1,id2` parsed on load, URL updated on highlight
- **Explain node**: POST /ollama/explain, "Explain with AI" button in details panel
- **Path finder**: path_between in query_engine, API /graph/path, CLI `path`, chat command
- **Impact analysis**: impact_analysis in query_engine, API /graph/impact, CLI `impact`, chat command
- **Hotspots**: /graph/fan-out API, nodeValFn sizes nodes by fan-out
- **Circular deps**: find_cycles in query_engine, API /graph/cycles, CLI `cycles`, chat command
- **File watcher**: codegraph/watcher.py, index_repo --watch
- **Architecture doc**: generate_architecture_doc in ollama_agent, CLI generate_docs
- **Architecture rules**: codegraph/rules.py, codegraph_rules.json, API /graph/rules/check, CLI check_rules, chat command
