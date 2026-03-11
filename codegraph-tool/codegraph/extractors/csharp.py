def extract(root_node, filepath, entities):
    def traverse(node, current_class=None, current_func=None):
        # Handle Classes / Structs / Interfaces
        if node.type in ['class_declaration', 'struct_declaration', 'interface_declaration']:
            name_node = node.child_by_field_name('name')
            if name_node:
                c_name = name_node.text.decode('utf8')
                entities['classes'].append({'name': c_name, 'filepath': filepath})
                for child in node.children:
                    traverse(child, current_class=c_name, current_func=current_func)
            return

        # Handle Methods / Functions
        elif node.type in ['method_declaration', 'constructor_declaration', 'local_function_statement']:
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

        # Handle Method Calls
        elif node.type == 'invocation_expression':
            func_node = node.child_by_field_name('function')
            if func_node:
                # Could be identifier, member_access_expression
                # For `obj.MethodName`, `member_access_expression` has a `name` field we can grab
                if func_node.type == 'member_access_expression':
                    name_field = func_node.child_by_field_name('name')
                    call_name = name_field.text.decode('utf8') if name_field else func_node.text.decode('utf8')
                else:
                    call_name = func_node.text.decode('utf8')
                
                caller = current_func or current_class or "module"
                entities['calls'].append({'caller': caller, 'callee': call_name, 'filepath': filepath})

        # Handle using directives (Imports)
        elif node.type == 'using_directive':
            name_node = node.child_by_field_name('name')
            if name_node:
                module_name = name_node.text.decode('utf8')
                entities['imports'].append({'file': filepath, 'module': module_name})

        for child in node.children:
            traverse(child, current_class, current_func)

    traverse(root_node)