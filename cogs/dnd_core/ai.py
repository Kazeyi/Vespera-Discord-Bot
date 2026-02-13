import asyncio
import os
import sys
import json
from typing import Optional, Dict
from groq import Groq
from dotenv import load_dotenv

from .constants import FAST_MODEL
from ..utility_core.personality import VesperaPersonality as VP

# Import governor from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from ai_request_governor import queue_ai_request
except ImportError:
    # Fallback if not found (during testing or if path issue)
    queue_ai_request = None

load_dotenv()

# Initialize Groq client
GROQ_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_text(prompt: str, model: str, max_tokens: int = 150, temperature: float = 0.3, user_id: str = None) -> Optional[str]:
    """
    Generate text using AI Governor to respect CPU limits.
    Returns the generated text or None if failed/timed out.
    """
    if queue_ai_request is None:
        # Fallback to direct call if governor not available
        return await _direct_generate(prompt, model, max_tokens, temperature)

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    async def _worker(p: str, m: str):
        try:
            # Execute blocking call in thread pool to avoid blocking main loop
            response = await loop.run_in_executor(
                None,
                lambda: GROQ_CLIENT.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": VP.SYSTEM_PROMPT},
                        {"role": "user", "content": p}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            result_text = response.choices[0].message.content.strip()
            if not future.done():
                future.set_result(result_text)
        except Exception as e:
            if not future.done():
                future.set_exception(e)

    # Queue request
    start_time = loop.time()
    try:
        success = await queue_ai_request(
            request_id=f"dnd_{start_time}",
            prompt=prompt,
            model_name=model,
            callback=_worker,
            user_id=str(user_id) if user_id else None
        )
        
        if not success:
            print("[DND AI] Request rate-limited")
            return None

        # Wait for result
        result = await asyncio.wait_for(future, timeout=20.0) # 20s global timeout
        return result
        
    except asyncio.TimeoutError:
        print("[DND AI] Generation timed out")
        return None
    except Exception as e:
        print(f"[DND AI] Generation error: {e}")
        return None

async def _direct_generate(prompt: str, model: str, max_tokens: int, temperature: float) -> Optional[str]:
    """Fallback generator"""
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: GROQ_CLIENT.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[DND AI] Direct generation error: {e}")
        return None

# --- DM OVERSIGHT ---
class DMOversight:
    """Ghost DM mode for suggesting outcomes"""
    
    @staticmethod
    async def suggest_outcome(guild_id: int, player_action: str, context: str) -> Dict:
        """Suggest a DM response before posting"""
        prompt = f"""As a DM assistant, suggest 3 possible outcomes for this player action:
        
        Context: {context[:200]}
        Action: {player_action}
        
        Provide 3 options: 
        1. A favorable outcome
        2. A challenging outcome
        3. A dramatic twist
        
        Return as JSON: {{"options": ["option1", "option2", "option3"], "recommended": "index"}}"""
        
        try:
            loop = asyncio.get_running_loop()
            
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: GROQ_CLIENT.chat.completions.create(
                        model=FAST_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=300,
                        response_format={"type": "json_object"}
                    )
                ),
                timeout=15.0
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"[DM Oversight] Error: {e}")
            return {
                "options": [
                    "The action succeeds as expected.",
                    "The action succeeds with a complication.",
                    "The action fails but reveals something important."
                ],
                "recommended": 0
            }
