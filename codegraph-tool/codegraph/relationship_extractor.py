def extract_file_entities(root_node, filepath, entities, lang_str):
    import importlib
    try:
        extractor_module = importlib.import_module(f'codegraph.extractors.{lang_str}')
        extractor = getattr(extractor_module, 'extract')
        extractor(root_node, filepath, entities)
    except ModuleNotFoundError:
        print(f"No extractor found for language: {lang_str}, falling back to minimal generic extraction.")
        pass