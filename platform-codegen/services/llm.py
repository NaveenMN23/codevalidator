from infrastructure.logger import log

class LLMService:
    def __init__(self):
        self.enabled = False # Feature flag
    
    def generate_gold_repo(self, prompt: str) -> str:
        """
        Stub for future LLM-driven Gold Master generation.
        """
        if not self.enabled:
            log.warning("LLM generation is currently disabled.")
            return "LLM generation is currently disabled."
        
        # In the future:
        # 1. Call Gemini/GPT-4 API with prompt
        # 2. Parse response into file structure
        # 3. Save to challenges/ folder
        return "Not implemented yet."

llm_service = LLMService()
