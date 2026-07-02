import os
import ast

def split_stream():
    src_path = 'app/api/endpoints/chat/stream.py'
    dest_path = 'app/services/pipeline/pipeline_orchestrator.py'
    
    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()
        lines = source.split('\n')
        
    tree = ast.parse(source)
    
    # We want to extract _sequential_pipeline_generator
    func_lines = []
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if node.name == '_sequential_pipeline_generator':
                start_lineno = node.lineno - 1
                if node.decorator_list:
                    start_lineno = node.decorator_list[0].lineno - 1
                end_lineno = node.end_lineno
                func_lines = lines[start_lineno:end_lineno]
                break
                
    if not func_lines:
        print("Function _sequential_pipeline_generator not found")
        return
        
    imports = """import os
import re
import json
import base64
import logging
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
from fastapi import Request, HTTPException
import asyncio

from backend.app.schemas.chat import ChatStreamRequest, SSEEventType
from backend.app.services.chat.chat_history_service import chat_history_service
from backend.app.utils.cache import get_cached_employee_fullname
from backend.app.utils.sse_formatter import format_sse
from backend.app.services.pipeline.mode_hub import mode_hub
"""
    
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(imports + "\n\n" + "\n".join(func_lines) + "\n")
        
    print("pipeline_orchestrator.py created")

if __name__ == '__main__':
    split_stream()
