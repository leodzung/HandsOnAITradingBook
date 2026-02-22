"""LLM client wrapper for MVP - Gemini (primary) with Ollama fallback"""
import json
import re
import requests
import config


class LLMClient:
    """LLM client: Uses Gemini by default, falls back to Ollama on failure"""

    def __init__(self):
        self.gemini_available = False
        self.ollama_available = False
        self.gemini_model = None

        # Try to initialize Gemini
        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL)
                self.gemini_available = True
                print(f"  [LLM] Gemini ({config.GEMINI_MODEL}) initialized")
            except Exception as e:
                print(f"  [LLM] Gemini init failed: {e}")

        # Check if Ollama is available
        try:
            response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=2)
            if response.status_code == 200:
                self.ollama_available = True
                print(f"  [LLM] Ollama ({config.OLLAMA_MODEL}) available as fallback")
        except:
            pass

        if not self.gemini_available and not self.ollama_available:
            raise RuntimeError(
                "No LLM backend available!\n"
                "  - Gemini: Set GEMINI_API_KEY in .env\n"
                "  - Ollama: Run 'ollama serve' and 'ollama pull qwen2.5:14b'"
            )

    def complete(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
        """Get completion - tries Gemini first, falls back to Ollama"""
        # Try Gemini first
        if self.gemini_available:
            result = self._gemini_complete(system_prompt, user_message, temperature)
            if result:
                return result
            print("  [LLM] Gemini failed, trying Ollama fallback...")

        # Fallback to Ollama
        if self.ollama_available:
            return self._ollama_complete(system_prompt, user_message, temperature)

        return ""

    def complete_json(self, system_prompt: str, user_message: str) -> dict:
        """Get JSON response - tries Gemini first, falls back to Ollama"""
        # Try Gemini first
        if self.gemini_available:
            result = self._gemini_complete_json(system_prompt, user_message)
            if result:  # Non-empty dict means success
                return result
            print("  [LLM] Gemini failed, trying Ollama fallback...")

        # Fallback to Ollama
        if self.ollama_available:
            return self._ollama_complete_json(system_prompt, user_message)

        return {}

    # ===== Gemini Backend =====

    def _gemini_complete(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
        """Get completion from Gemini"""
        try:
            import google.generativeai as genai
            full_prompt = f"{system_prompt}\n\n{user_message}"
            response = self.gemini_model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            return response.text
        except Exception as e:
            print(f"  [Gemini Error] {e}")
            self.gemini_available = False  # Disable for this session
            return ""

    def _gemini_complete_json(self, system_prompt: str, user_message: str) -> dict:
        """Get JSON response from Gemini"""
        try:
            import google.generativeai as genai
            full_prompt = f"{system_prompt}\n\nYou must respond with valid JSON only. No markdown code blocks, no explanations, just raw JSON.\n\n{user_message}"
            response = self.gemini_model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7
                )
            )
            content = response.text
            # Try to extract JSON if wrapped in code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                content = json_match.group(1)
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            print(f"  [Gemini JSON Error] {e}")
            return {}
        except Exception as e:
            print(f"  [Gemini Error] {e}")
            self.gemini_available = False  # Disable for this session
            return {}

    # ===== Ollama Backend =====

    def _ollama_complete(self, system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
        """Get completion from Ollama"""
        try:
            response = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": f"{system_prompt}\n\n{user_message}",
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                },
                timeout=300  # 5 minutes for reasoning models like DeepSeek R1
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.ConnectionError:
            print(f"  [Ollama Error] Cannot connect to {config.OLLAMA_BASE_URL}")
            print("    Make sure Ollama is running: ollama serve")
            self.ollama_available = False
            return ""
        except Exception as e:
            print(f"  [Ollama Error] {e}")
            return ""

    def _ollama_complete_json(self, system_prompt: str, user_message: str) -> dict:
        """Get JSON response from Ollama"""
        try:
            json_prompt = f"{system_prompt}\n\nIMPORTANT: You must respond with valid JSON only. No markdown code blocks, no explanations, just raw JSON."

            response = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": f"{json_prompt}\n\n{user_message}",
                    "stream": False,
                    "format": "json",  # Ollama's native JSON mode
                    "options": {
                        "temperature": 0.7
                    }
                },
                timeout=300  # 5 minutes for reasoning models like DeepSeek R1
            )
            response.raise_for_status()
            content = response.json().get("response", "")

            # Try to extract JSON if wrapped in code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                content = json_match.group(1)

            return json.loads(content.strip())
        except requests.exceptions.ConnectionError:
            print(f"  [Ollama Error] Cannot connect to {config.OLLAMA_BASE_URL}")
            print("    Make sure Ollama is running: ollama serve")
            self.ollama_available = False
            return {}
        except json.JSONDecodeError as e:
            print(f"  [Ollama JSON Error] {e}")
            print(f"    Raw response: {content[:200]}...")
            return {}
        except Exception as e:
            print(f"  [Ollama Error] {e}")
            return {}


if __name__ == '__main__':
    # Test the client
    config.validate_config()

    print("\n" + "=" * 50)
    print("LLM Client Test")
    print("=" * 50)

    llm = LLMClient()

    print(f"\nGemini available: {llm.gemini_available}")
    print(f"Ollama available: {llm.ollama_available}")

    print("\n--- Testing text completion ---")
    response = llm.complete(
        system_prompt="You are a helpful assistant.",
        user_message="Say 'Hello World' and explain what you can do in 2 sentences."
    )
    print(f"Response: {response[:200]}..." if len(response) > 200 else f"Response: {response}")

    print("\n--- Testing JSON completion ---")
    json_response = llm.complete_json(
        system_prompt="You are a financial analyst.",
        user_message="Analyze AAPL stock briefly. Respond with JSON: {symbol, recommendation (buy/sell/hold), conviction (0-100), reasoning}"
    )
    print(f"JSON Response: {json.dumps(json_response, indent=2)}")
