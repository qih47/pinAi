# pinAi/llm/cleaner.py
import re

def clean_response(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'Thinking\..*?\.\.\.done thinking\.', '', text, flags=re.DOTALL)
    text = re.sub(r'【.*?】', '', text)
    return text.strip()
