import os


def fix_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    original = content
    content = content.replace('str | None', 'Optional[str]')
    content = content.replace('int | None', 'Optional[int]')
    content = content.replace('I18n | None', 'Optional[I18n]')
    content = content.replace('AppConfig | None', 'Optional[AppConfig]')
    content = content.replace('list[Edge] | None', 'Optional[List[Edge]]')
    
    content = content.replace('list[', 'List[')
    content = content.replace('dict[', 'Dict[')
    content = content.replace('tuple[', 'Tuple[')

    if content != original:
        lines = content.splitlines()
        import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('from __future__'):
                import_idx = i + 1
                break
        
        needed = []
        if 'Optional[' in content: needed.append('Optional')
        if 'List[' in content: needed.append('List')
        if 'Dict[' in content: needed.append('Dict')
        if 'Tuple[' in content: needed.append('Tuple')
        
        # Only add if not already imported
        final_needed = []
        for n in needed:
            if f"import {n}" not in content and f"{n}," not in content:
                final_needed.append(n)
                
        if needed:
            import_str = f"from typing import {', '.join(needed)}"
            # Avoid duplicate typing imports, just prepend to the next line
            lines.insert(import_idx, import_str)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

for root, _, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
