def extract(root_node, filepath, entities):
    def traverse(node, current_class=None, current_func=None):
        if node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                c_name = name_node.text.decode('utf8')
                entities['classes'].append({'name': c_name, 'filepath': filepath})
                for child in node.children:
                    traverse(child, current_class=c_name, current_func=current_func)
            return

        elif node.type in ['function_declaration', 'method_definition', 'arrow_function']:
            name_node = node.child_by_field_name('name')
            if name_node:
                f_name = name_node.text.decode('utf8')
            else:
                f_name = 'anonymous'
                
            if current_class and node.type == 'method_definition':
                entities['methods'].append({'name': f_name, 'class': current_class, 'filepath': filepath})
            else:
                entities['functions'].append({'name': f_name, 'filepath': filepath})
            
            for child in node.children:
                traverse(child, current_class=current_class, current_func=f_name)
            return

        elif node.type == 'call_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                call_name = func_node.text.decode('utf8')
                caller = current_func or current_class or "module"
                entities['calls'].append({'caller': caller, 'callee': call_name, 'filepath': filepath})

        elif node.type == 'import_statement':
            source_node = node.child_by_field_name('source')
            if source_node:
                entities['imports'].append({'file': filepath, 'module': source_node.text.decode('utf8').strip("'\"")})

        for child in node.children:
            traverse(child, current_class, current_func)

    traverse(root_node)