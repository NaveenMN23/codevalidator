import requests
from infrastructure.logger import log

class LLMService:
    def __init__(self):
        self.enabled = True # Feature flag
        self.backend_url = "http://platform-backend:8080/api/admin"
    
    def generate_gold_repo(self, prompt: str) -> str:
        """
        Stub for future LLM-driven Gold Master generation.
        """
        if not self.enabled:
            log.warning("LLM generation is currently disabled.")
            return "LLM generation is currently disabled."
        return "Not implemented yet."

    def generate_blueprint(self, problem_id: str, challenge_name: str, language: str) -> dict:
        """
        Generates a Blueprint JSON for a given problem.
        In production, this would call Claude 3.5 Sonnet or GPT-4o with the repo context.
        """
        if not self.enabled:
            log.warning("LLM generation is currently disabled.")
            return {}

        log.info(f"Generating blueprint for {challenge_name} ({problem_id})")
        
        # This structure matches the "Required DTO" from the blueprint architecture document
        blueprint = {
            "problemId": problem_id,
            "task": {
                "taskType": "FEATURE_IMPLEMENTATION",
                "title": challenge_name,
                "description": f"Implement the core logic for {challenge_name}. Ensure all edge cases are handled.",
                "constraints": [
                    "Preserve O(n) time complexity",
                    "Handle empty input cases"
                ],
                "difficulty": "MEDIUM",
                "targetRole": "SDE-2",
                "language": language,
                "framework": "Spring Boot" if language == "java" else "Node.js",
                "expectedComplexity": {
                    "time": "O(n)",
                    "space": "O(n)"
                },
                "concurrencyRequired": False
            },
            "repo": {
                "targetFile": "src/main/java/com/example/Task.java" if language == "java" else "src/index.ts",
                "relevantFiles": []
            },
            "followUpContext": {
                "interviewerFocusAreas": [
                    {
                        "area": "CORRECTNESS",
                        "scope": "Validation of input parameters and boundary conditions"
                    }
                ],
                "expectedApproaches": [
                    {
                        "approach": "Iterative",
                        "tradeoff": "Simple and space-efficient"
                    }
                ],
                "followUpIntent": {
                    "type": "EVALUATOR_DECIDES",
                    "hint": "Ask about scaling the solution to larger datasets",
                    "minimumTimeRemainingSeconds": 600
                }
            }
        }
        return blueprint

    def dispatch_blueprint(self, blueprint: dict):
        """
        Sends the generated blueprint to the backend for storage and caching.
        """
        try:
            url = f"{self.backend_url}/blueprints"
            response = requests.post(url, json=blueprint, timeout=10)
            response.raise_for_status()
            log.info(f"Successfully dispatched blueprint for {blueprint.get('problemId')}")
        except Exception as e:
            log.error(f"Failed to dispatch blueprint to {self.backend_url}: {e}")

llm_service = LLMService()
