"""
Verify LLM API Configuration

This script tests if the LLM API is properly configured.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from settings import has_real_value

try:
    import openai
except ImportError:
    openai = None
    print("[ERROR] openai library not installed. Run: pip install openai")
    sys.exit(1)

load_dotenv()

print("=" * 60)
print(" LLM API Configuration Check")
print("=" * 60)

# Check API Keys
glm_key = os.getenv("ZHIPU_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

print(f"\n[1] API Keys")
print(f"    ZHIPU_API_KEY: {'✓ Configured' if has_real_value(glm_key) else '✗ Missing or placeholder'}")
print(f"    OPENAI_API_KEY: {'✓ Configured' if has_real_value(openai_key) else '✗ Missing or placeholder'}")

# Test GLM API
if has_real_value(glm_key):
    print(f"\n[2] Testing GLM API...")
    try:
        client = openai.OpenAI(
            api_key=glm_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/"
        )

        response = client.chat.completions.create(
            model="glm-4-flash",
            temperature=0.1,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "请回复'测试成功'"}
            ],
            max_tokens=50
        )

        answer = response.choices[0].message.content
        print(f"    ✓ GLM API Response: {answer}")

    except Exception as e:
        print(f"    ✗ GLM API Error: {e}")
else:
    print(f"\n[2] Skipping GLM API test (no valid key)")

# Test OpenAI API (if available)
if has_real_value(openai_key):
    print(f"\n[3] Testing OpenAI API...")
    try:
        client = openai.OpenAI(api_key=openai_key)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say 'test successful'"}
            ],
            max_tokens=50
        )

        answer = response.choices[0].message.content
        print(f"    ✓ OpenAI API Response: {answer}")

    except Exception as e:
        print(f"    ✗ OpenAI API Error: {e}")

# Recommendations
print(f"\n" + "=" * 60)
print(" Recommendations")
print("=" * 60)

if not has_real_value(glm_key):
    print("1. Get ZHIPU_API_KEY from: https://open.bigmodel.cn/")
    print("2. Add it to your .env file:")
    print("   ZHIPU_API_KEY=your_actual_api_key")

if has_real_value(glm_key):
    print("✓ Configuration looks good!")
    print("\nTo update APP_MODE, edit .env:")
    print("   APP_MODE=real")
    print("   DOCUMENT_VERSION=CCAR-33-R2-2016-real")

print()
