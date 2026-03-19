"""Quick test to find which GLM model works with user's API key."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import os
from dotenv import load_dotenv
load_dotenv()

import openai

api_key = os.getenv("ZHIPU_API_KEY")
client = openai.OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")

models_to_try = [
    "glm-4-flash",
    "glm-4-plus", 
    "glm-4-air",
    "glm-4-airx",
    "glm-4.5-flash",
    "glm-4-0520",
    "glm-4-long",
    "glm-4",
]

for model in models_to_try:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello, respond with just OK"}],
            max_tokens=10,
        )
        content = resp.choices[0].message.content
        print(f"[OK]  {model:25s} -> {content.strip()}")
    except Exception as e:
        err_msg = str(e)[:80]
        print(f"[FAIL] {model:25s} -> {err_msg}")
