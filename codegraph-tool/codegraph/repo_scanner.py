import os
from .parser import get_parser
from .relationship_extractor import extract_file_entities

def get_language_from_ext(ext):
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.cjs': 'javascript',
        '.mjs': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.cts': 'typescript',
        '.mts': 'typescript',
        '.tsx': 'tsx',
        '.java': 'java',
        '.go': 'go',
        '.cpp': 'cpp',
        '.c': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c++': 'cpp',
        '.h': 'cpp',
        '.hpp': 'cpp',
        '.hxx': 'cpp',
        '.hh': 'cpp',
        '.rs': 'rust',
        '.cs': 'csharp'
    }
    return ext_map.get(ext)

def scan_repository(repo_path):
    entities = {'files': [], 'classes': [], 'functions': [], 'methods': [], 'calls': [], 'imports': []}
    parsers = {}
    
    # Support single-file indexing
    if os.path.isfile(repo_path):
        ext = os.path.splitext(repo_path)[1].lower()
        lang_str = get_language_from_ext(ext)
        if lang_str:
            files_to_scan = [(repo_path, lang_str)]
        else:
            print(f"Unsupported file extension: {ext}")
            return entities
    else:
        # Collect files first for progress reporting
        files_to_scan = []
        ignore_dirs = {'.git'}
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                lang_str = get_language_from_ext(ext)
                if lang_str:
                    files_to_scan.append((os.path.join(root, file), lang_str))
                
    print(f"Found {len(files_to_scan)} supported source files. Parsing...")
    
    for i, (filepath, lang_str) in enumerate(files_to_scan):
        if i % 100 == 0:
            print(f"Parsing file {i+1}/{len(files_to_scan)}...")
            
        if lang_str not in parsers:
            parsers[lang_str] = get_parser(lang_str)
            
        parser = parsers.get(lang_str)
        if not parser:
            continue

        entities['files'].append(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            tree = parser.parse(bytes(code, 'utf8'))
            extract_file_entities(tree.root_node, filepath, entities, lang_str)
        except Exception as e:
            # Silently ignore parsing errors to prevent console spam
            pass
            
    print(f"Parsing complete. Extracted:")
    print(f" - {len(entities['classes'])} classes")
    print(f" - {len(entities['functions']) + len(entities['methods'])} functions/methods")
    print(f" - {len(entities['calls'])} calls")
    return entities