import os
import ast

def split_chat_history():
    src_path = 'app/services/chat/chat_history_service.py'
    repos_dir = 'app/services/chat/repositories'
    
    os.makedirs(repos_dir, exist_ok=True)
    open(os.path.join(repos_dir, '__init__.py'), 'w').close()
    
    with open(src_path, 'r', encoding='utf-8') as f:
        source = f.read()
        lines = source.split('\n')
        
    tree = ast.parse(source)
    
    # Mapping methods to repositories
    session_methods = [
        'create_new_session', 'get_user_sessions', '_resolve_session_pk',
        'toggle_pin_session', 'update_session_title', 'soft_delete_session',
        'assign_session_to_user', 'update_session_settings', 'get_session_settings',
        'auto_update_session_title'
    ]
    
    message_methods = [
        '_resolve_session_pk', # Needed in message repository too
        'save_chat_message', 'update_chat_message', 'trim_session_messages',
        'get_session_messages', 'save_chat_attachment', 'save_document_chunk',
        'get_session_document_chunks', 'save_dialogue_corpus'
    ]
    
    feedback_methods = [
        '_resolve_session_pk', # Needed here too
        'save_message_feedback', 'update_message_feedback'
    ]
    
    method_blocks = {}
    
    class_def = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ChatHistoryService')
    
    nodes = sorted(class_def.body, key=lambda n: getattr(n, 'lineno', 0))
    for i, node in enumerate(nodes):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_lineno = node.lineno - 1
            if node.decorator_list:
                start_lineno = node.decorator_list[0].lineno - 1
            while start_lineno > 0 and (lines[start_lineno-1].strip().startswith('#') or lines[start_lineno-1].strip() == ''):
                start_lineno -= 1
            end_lineno = node.end_lineno
            
            # dedent 4 spaces
            block = '\n'.join([line[4:] if line.startswith('    ') else line for line in lines[start_lineno:end_lineno]])
            method_blocks[node.name] = block
            
    # Write session_repository.py
    session_repo_content = '''import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class SessionRepository:
'''
    for fn in session_methods:
        if fn in method_blocks:
            session_repo_content += "    " + method_blocks[fn].replace("\n", "\n    ") + "\n\n"
            
    with open(os.path.join(repos_dir, 'session_repository.py'), 'w', encoding='utf-8') as f:
        f.write(session_repo_content)
        
    # Write message_repository.py
    message_repo_content = '''import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class MessageRepository:
'''
    for fn in message_methods:
        if fn in method_blocks:
            message_repo_content += "    " + method_blocks[fn].replace("\n", "\n    ") + "\n\n"
            
    with open(os.path.join(repos_dir, 'message_repository.py'), 'w', encoding='utf-8') as f:
        f.write(message_repo_content)
        
    # Write feedback_repository.py
    feedback_repo_content = '''import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class FeedbackRepository:
'''
    for fn in feedback_methods:
        if fn in method_blocks:
            feedback_repo_content += "    " + method_blocks[fn].replace("\n", "\n    ") + "\n\n"
            
    with open(os.path.join(repos_dir, 'feedback_repository.py'), 'w', encoding='utf-8') as f:
        f.write(feedback_repo_content)
        
    # Re-write chat_history_service.py as an orchestrator
    orchestrator_content = '''import logging
from typing import List, Dict, Any, Optional
from .repositories.session_repository import SessionRepository
from .repositories.message_repository import MessageRepository
from .repositories.feedback_repository import FeedbackRepository

logger = logging.getLogger("CAKRA_CHAT_HISTORY")

class ChatHistoryService(SessionRepository, MessageRepository, FeedbackRepository):
    """
    Orchestrator class for Chat History that inherits from all specific repositories
    to maintain backward compatibility with existing codebase.
    """
    pass

chat_history_service = ChatHistoryService()
'''
    with open(src_path, 'w', encoding='utf-8') as f:
        f.write(orchestrator_content)
        
    print("Chat History Service refactored successfully.")

if __name__ == '__main__':
    split_chat_history()
