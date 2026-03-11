def extract(root_node, filepath, entities):
    def traverse(node, current_class=None, current_func=None):
        if node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                c_name = name_node.text.decode('utf8')
                entities['classes'].append({'name': c_name, 'filepath': filepath})
                for child in node.children:
                    traverse(child, current_class=c_name, current_func=current_func)
            return

        elif node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                f_name = name_node.text.decode('utf8')
                if current_class:
                    entities['methods'].append({'name': f_name, 'class': current_class, 'filepath': filepath})
                else:
                    entities['functions'].append({'name': f_name, 'filepath': filepath})
                
                for child in node.children:
                    traverse(child, current_class=current_class, current_func=f_name)
            return

        elif node.type == 'call':
            func_node = node.child_by_field_name('function')
            if func_node:
                call_name = func_node.text.decode('utf8')
                caller = current_func or current_class or "module"
                entities['calls'].append({'caller': caller, 'callee': call_name, 'filepath': filepath})

        elif node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    entities['imports'].append({'file': filepath, 'module': child.text.decode('utf8')})
        
        elif node.type == 'import_from_statement':
            module_node = node.child_by_field_name('module_name')
            if module_node:
                entities['imports'].append({'file': filepath, 'module': module_node.text.decode('utf8')})

        for child in node.children:
            traverse(child, current_class, current_func)

    traverse(root_node)