import os
import sys
import ast

def find_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return []
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    
    return imports

def find_unused_files():
    root_dir = 'virtual_assistant'
    all_files = []
    all_modules = set()
    
    # Get all Python files and extract their module names
    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith('.py'):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path)
                module_path = rel_path[:-3].replace(os.path.sep, '.')
                all_files.append((module_path, full_path))
                all_modules.add(module_path)
    
    # Get imports from all files
    imported_modules = set()
    for _, file_path in all_files:
        file_imports = find_imports(file_path)
        for imp in file_imports:
            # Add the module and its parents
            parts = imp.split('.')
            for i in range(1, len(parts) + 1):
                imported_modules.add('.'.join(parts[:i]))
    
    # Special case for __init__.py files that might be implicitly imported
    for module_path in list(all_modules):
        if module_path.endswith('.__init__'):
            parent_module = module_path[:-9]  # Remove .__init__
            if parent_module in imported_modules:
                imported_modules.add(module_path)
    
    # Find unused modules
    unused_modules = all_modules - imported_modules
    
    # Filter out special cases
    unused_modules = {m for m in unused_modules if not m.endswith('.__main__')}
    
    # Output unused files
    for module_path, file_path in all_files:
        if module_path in unused_modules:
            print(f'Unused file: {file_path}')

if __name__ == "__main__":
    find_unused_files() 