import os
import ast

def clean_stream():
    src_path = 'app/api/endpoints/chat/stream.py'
    
    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()
        lines = source.split('\n')
        
    tree = ast.parse(source)
    
    start_lineno = None
    end_lineno = None
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name == '_sequential_pipeline_generator':
                start_lineno = node.lineno - 1
                if node.decorator_list:
                    start_lineno = node.decorator_list[0].lineno - 1
                end_lineno = node.end_lineno
                break
                
    if start_lineno is not None:
        # Remove the function lines
        new_lines = lines[:start_lineno] + lines[end_lineno:]
        
        # Add import
        import_stmt = "from backend.app.services.pipeline.pipeline_orchestrator import _sequential_pipeline_generator"
        
        # Insert import near the top after imports
        for i, line in enumerate(new_lines):
            if line.startswith('from fastapi import'):
                new_lines.insert(i + 1, import_stmt)
                break
        
        with open(src_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
            
        print("stream.py cleaned up successfully")
    else:
        print("Function not found")

if __name__ == '__main__':
    clean_stream()
