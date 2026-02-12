import google.generativeai as genai
import os
import asyncio
import re
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

FALLBACK_CHAIN = ["models/gemma-3-27b-it", "models/gemini-2.0-flash-lite"]

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

def sanitize_input(text, max_length=2000):
    """Sanitize user input to prevent prompt injection attacks"""
    if not isinstance(text, str):
        return ""
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Escape single and double quotes to prevent string breakout
    text = text.replace('\\', '\\\\')
    
    return text.strip()

async def ask_ai(prompt, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
        return response.text.strip(), model_name
    except Exception as e:
        print(f"⚠️ Primary ({model_name}) Failed: {e}")
        
    for fallback in FALLBACK_CHAIN:
        if fallback == model_name: continue
        try:
            print(f"🔄 Switching to Fallback: {fallback}")
            model = genai.GenerativeModel(fallback)
            response = await model.generate_content_async(prompt, safety_settings=SAFETY_SETTINGS)
            return response.text.strip(), fallback
        except: continue

    return "❌ Error: All AI models failed.", "None"