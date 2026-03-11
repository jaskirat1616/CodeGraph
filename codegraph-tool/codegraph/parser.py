def get_parser(language_str):
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_java as tsjava
    import tree_sitter_go as tsgo
    import tree_sitter_cpp as tscpp
    import tree_sitter_rust as tsrust
    import tree_sitter_c_sharp as tscsharp
    from tree_sitter import Language, Parser
    
    lang_map = {
        'python': tspython.language(),
        'javascript': tsjavascript.language(),
        'typescript': tstypescript.language_typescript(),
        'tsx': tstypescript.language_tsx(),
        'java': tsjava.language(),
        'go': tsgo.language(),
        'cpp': tscpp.language(),
        'rust': tsrust.language(),
        'csharp': tscsharp.language(),
    }
    
    if language_str not in lang_map:
        return None
        
    language = Language(lang_map[language_str])
    parser = Parser(language)
    return parser