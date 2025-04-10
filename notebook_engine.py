# notebook_engine.py
class AIDebugAgent:
    def get_suggestion(self, error_message):
        # Simulated AI debugging logic.
        suggestion = "Please check your syntax."
        if "NameError" in error_message:
            suggestion = "A variable might be undefined—review your declarations."
        elif "IndentationError" in error_message:
            suggestion = "Check your indentation levels; they must be consistent."
        elif "TypeError" in error_message:
            suggestion = "Ensure you're not mixing incompatible types in operations."
        return suggestion

class NotebookEngine:
    def __init__(self):
        self.cells = []  # List of cell dictionaries
        self.ai_agent = AIDebugAgent()
    
    def add_cell(self, cell_type="code", content=""):
        cell = {"type": cell_type, "content": content, "output": ""}
        self.cells.append(cell)
        return cell

    def execute_code(self, code):
        # This function simulates code execution.
        # In a production system, you would run the code in a safe, sandboxed environment.
        if "error" in code:
            error_message = "Simulated NameError: name 'error' is not defined."
            suggestion = self.ai_agent.get_suggestion(error_message)
            return {"status": "error", "message": error_message, "suggestion": suggestion}
        else:
            output = f"Executed code: {code}"
            return {"status": "success", "output": output}
    
    def run_cell(self, cell):
        if cell["type"] == "code":
            result = self.execute_code(cell["content"])
            if result["status"] == "success":
                cell["output"] = result["output"]
            else:
                cell["output"] = f"Error: {result['message']}\nAI Suggestion: {result['suggestion']}"
        else:
            cell["output"] = "Markdown cell does not execute."

