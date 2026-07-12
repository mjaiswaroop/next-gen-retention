import os
import re
import traceback
import logging
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from config import settings
from google import genai

logger = logging.getLogger("retention_core.autoheal")

try:
    gemini_client = genai.Client(api_key=settings.gemini_api_key or "DUMMY")
except Exception as e:
    logger.warning(f"Failed to init Gemini client: {e}")
    gemini_client = None

class AutoHealPatch(BaseModel):
    reasoning: str = Field(description="Explanation of the root cause of the error.")
    fixed_code: str = Field(description="The complete, corrected source code for the file.")
    target_file: str = Field(description="The absolute or relative path to the file that needs to be modified.")

class AutoHealService:
    def __init__(self, log_path: str = "uvicorn_error.log"):
        self.log_path = log_path

    def get_recent_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Parses the log file for recent exceptions."""
        if not os.path.exists(self.log_path):
            return []
            
        errors = []
        try:
            # Simple heuristic: read backwards or read all and find tracebacks
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Split by Traceback (most recent call last):
            blocks = content.split("Traceback (most recent call last):")
            
            # The first block is logs before any traceback
            for block in reversed(blocks[1:]):
                if len(errors) >= limit:
                    break
                    
                lines = block.strip().split('\n')
                # Last line of the block is usually the exception itself
                exception_msg = lines[-1] if lines else "Unknown Exception"
                
                # Extract file path and line number from the traceback
                target_file = None
                line_number = None
                for line in reversed(lines[:-1]):
                    match = re.search(r'File "(.*?)", line (\d+)', line)
                    if match and not ("site-packages" in match.group(1) or "lib" in match.group(1).lower()):
                        target_file = match.group(1)
                        line_number = int(match.group(2))
                        break
                        
                errors.append({
                    "id": len(errors) + 1,
                    "exception": exception_msg,
                    "traceback": "Traceback (most recent call last):\n" + block.strip(),
                    "target_file": target_file,
                    "line_number": line_number,
                })
        except Exception as e:
            logger.error(f"Failed to parse error logs: {e}")
            
        return errors

    def generate_patch(self, target_file: str, traceback_str: str) -> Optional[Dict[str, Any]]:
        """Sends the broken code and stack trace to LLM for a fix."""
        if not gemini_client or not settings.gemini_api_key:
            raise ValueError("Gemini API key not configured.")
            
        if not target_file or not os.path.exists(target_file):
            raise ValueError(f"Target file {target_file} not found.")
            
        with open(target_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
            
        system_prompt = (
            "You are an autonomous Auto-Heal Agent. Your job is to fix broken Python code.\n"
            "You will be given a stack trace and the content of the file that caused the error.\n"
            "You must return a JSON object with 'reasoning', the full 'fixed_code' for the file, and the 'target_file' path.\n"
            "Ensure the fixed code is structurally complete and fixes the specific exception provided."
        )
        
        user_prompt = f"Target File: {target_file}\n\nStack Trace:\n{traceback_str}\n\nSource Code:\n{source_code}"
        
        res = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[system_prompt + "\n\n" + user_prompt],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AutoHealPatch,
                temperature=0.1
            )
        )
        
        data = json.loads(res.text)
        return data

    def apply_patch(self, target_file: str, fixed_code: str) -> bool:
        """Writes the corrected code to the filesystem."""
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            return True
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            return False
