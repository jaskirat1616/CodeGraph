def extract(root_node, filepath, entities):
    def traverse(node, current_class=None, current_func=None):
        # Handle Classes / Structs
        if node.type in ['class_specifier', 'struct_specifier']:
            name_node = node.child_by_field_name('name')
            if name_node:
                c_name = name_node.text.decode('utf8')
                entities['classes'].append({'name': c_name, 'filepath': filepath})
                for child in node.children:
                    traverse(child, current_class=c_name, current_func=current_func)
            return

        # Handle Functions / Methods
        elif node.type == 'function_definition':
            declarator = node.child_by_field_name('declarator')
            if declarator:
                # In C++, declarator might be a function_declarator or wrapped in references
                # So we search downwards for the identifier
                def find_identifier(n):
                    if n.type in ['identifier', 'field_identifier', 'destructor_name']:
                        return n.text.decode('utf8')
                    for c in n.children:
                        res = find_identifier(c)
                        if res: return res
                    return None
                
                f_name = find_identifier(declarator)
                if f_name:
                    # Check if it's a method (e.g., MyClass::MyMethod)
                    # We can use current_class if we are inside a class definition,
                    # or it might be defined outside using scoped_identifier
                    scoped = declarator.child_by_field_name('declarator')
                    if scoped and scoped.type == 'scoped_identifier':
                        scope_node = scoped.child_by_field_name('namespace')
                        if scope_node:
                            current_class = scope_node.text.decode('utf8')

                    if current_class:
                        entities['methods'].append({'name': f_name, 'class': current_class, 'filepath': filepath})
                    else:
                        entities['functions'].append({'name': f_name, 'filepath': filepath})
                    
                    for child in node.children:
                        traverse(child, current_class=current_class, current_func=f_name)
                return

        # Handle Function Calls
        elif node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                # Could be identifier, field_expression, scoped_identifier, etc.
                call_name = func_node.text.decode('utf8').split('::')[-1]
                caller = current_func or current_class or "module"
                entities['calls'].append({'caller': caller, 'callee': call_name, 'filepath': filepath})

        # Handle Includes (Imports)
        elif node.type == 'preproc_include':
            path_node = node.child_by_field_name('path')
            if path_node:
                module_name = path_node.text.decode('utf8').strip('<>"\'')
                entities['imports'].append({'file': filepath, 'module': module_name})

        for child in node.children:
            traverse(child, current_class, current_func)

    traverse(root_node)