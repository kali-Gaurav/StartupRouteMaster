import re
import os
import glob

def fix_table_args(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Fix dict-style __table_args__
    def dict_replacer(match):
        inner = match.group(1).strip()
        if 'extend_existing' in inner:
            return match.group(0)
        if inner == "":
            return '__table_args__ = {"extend_existing": True}'
        return f'__table_args__ = {{{inner}, "extend_existing": True}}'
    
    content = re.sub(r'__table_args__\s*=\s*\{([^\}]*)\}', dict_replacer, content)
    
    # 2. Fix tuple-style __table_args__
    # Strategy: find the end of the tuple and insert the dict before the last closing paren.
    # But wait, we must handle the case where a dict already exists at the end.
    
    def tuple_replacer(match):
        inner = match.group(1).strip()
        if 'extend_existing' in inner:
            return match.group(0)
        
        # Check if it ends with a dict
        if inner.endswith('}'):
            # Find the start of that last dict
            last_brace_index = inner.rfind('{')
            if last_brace_index != -1:
                dict_content = inner[last_brace_index+1:-1].strip()
                if dict_content == "":
                    new_dict = '{"extend_existing": True}'
                else:
                    new_dict = f'{{{dict_content}, "extend_existing": True}}'
                new_inner = inner[:last_brace_index] + new_dict
                return f'__table_args__ = ({new_inner})'
        
        # No dict at the end, just append one
        if inner.endswith(','):
            inner = inner[:-1].strip()
        if inner == "":
            return '__table_args__ = ({"extend_existing": True},)'
        return f'__table_args__ = ({inner}, {{"extend_existing": True}})'
    
    # Use a more specific regex for the whole line to avoid partial matches
    content = re.sub(r'__table_args__\s*=\s*\((.*?)\)\s*$', 
                     lambda m: tuple_replacer(m), 
                     content, flags=re.MULTILINE | re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# Process all files
model_files = glob.glob('database/models/*.py')
for f in model_files:
    if f.endswith('__init__.py'): continue
    print(f"Fixing {f}...")
    fix_table_args(f)
