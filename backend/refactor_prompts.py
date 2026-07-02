import os
import ast

def split_prompts():
    src_path = 'app/services/pipeline/system_prompts.py'
    prompts_dir = 'app/services/pipeline/prompts'
    
    os.makedirs(prompts_dir, exist_ok=True)
    open(os.path.join(prompts_dir, '__init__.py'), 'w').close()
    
    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()
        
    tree = ast.parse(source)
    
    # We'll map each function to a file
    mapping = {
        'core_prompts': [
            'build_call1_routing_prompt',
            '_get_base_persona',
            '_get_tone_guidance',
            'build_response_prompt_ambiguous',
            'build_response_prompt_general_expert',
            'build_response_prompt_chitchat',
            'build_intent_analysis_prompt'
        ],
        'coding_prompts': [
            'build_response_prompt_coding'
        ],
        'rag_prompts': [
            'build_response_prompt_rag',
            'build_response_prompt_multi_document',
            'build_response_prompt_analytic',
            'build_attachment_system_prompt',
            'build_response_prompt_self_correction'
        ],
        'file_prompts': [
            'build_generate_file_call1_prompt',
            'build_edit_file_call1_prompt',
            'build_generate_file_call2_analyst_prompt'
        ]
    }
    
    # Helper to get source segment
    lines = source.split('\n')
    def get_source(node):
        start = node.lineno - 1
        end = node.end_lineno
        return '\n'.join(lines[start:end])
        
    extracted_funcs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            # include preceding comments or decorators if needed? 
            # ast doesn't capture comments easily, but we can do a hack: 
            # just slice from the end of the previous node or start of file
            pass

    # A better way to preserve comments is regex or finding 'def ' boundaries
    import re
    func_blocks = {}
    
    # split by '\ndef ' to preserve things. Actually, let's use AST lineno
    
    # Sort nodes by lineno
    nodes = sorted(tree.body, key=lambda n: getattr(n, 'lineno', 0))
    
    for i, node in enumerate(nodes):
        if isinstance(node, ast.FunctionDef):
            # find start line (include decorators)
            start_lineno = node.lineno - 1
            if node.decorator_list:
                start_lineno = node.decorator_list[0].lineno - 1
                
            # include preceding comments by backtracking
            while start_lineno > 0 and (lines[start_lineno-1].strip().startswith('#') or lines[start_lineno-1].strip() == ''):
                start_lineno -= 1
                
            # end line
            end_lineno = node.end_lineno
            
            func_blocks[node.name] = '\n'.join(lines[start_lineno:end_lineno])
            
    imports_header = '''import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CAKRA_PROMPTS")

_RAG_CONTEXT_MAX_CHARS = 60_000
'''

    for file_name, func_names in mapping.items():
        out_path = os.path.join(prompts_dir, f"{file_name}.py")
        content = imports_header + "\n"
        
        if file_name != 'core_prompts':
            content += "from .core_prompts import _get_base_persona, _get_tone_guidance\n\n"
            
        if file_name == 'rag_prompts':
            pass
            
        if file_name == 'core_prompts':
            # handle circular dep if build_intent_analysis_prompt needs build_call1_routing_prompt? It's in the same file.
            pass
            
        for fn in func_names:
            if fn in func_blocks:
                content += func_blocks[fn] + "\n\n"
                
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    # Write the barrel export
    barrel_content = '"""\nSystem Prompts Barrel Export\n"""\n'
    for file_name, func_names in mapping.items():
        public_funcs = [fn for fn in func_names if not fn.startswith('_')]
        if public_funcs:
            barrel_content += f"from .prompts.{file_name} import (\n    " + ",\n    ".join(public_funcs) + "\n)\n"
            
    with open(src_path, 'w', encoding='utf-8') as f:
        f.write(barrel_content)
        
    print("Prompts refactored successfully.")

if __name__ == '__main__':
    split_prompts()
