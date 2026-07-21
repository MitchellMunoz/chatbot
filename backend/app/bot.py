from anthropic import Anthropic
from dotenv import load_dotenv
from pathlib import Path
from app.tools import TOOLS
load_dotenv()

System_Prompt = Path("app/prompt.md").read_text()


class ChatBot:
    def __init__(self) -> None:
        self.anthropic_Amanda = Anthropic()

    def generate_response(self, messages_user: list, max_tokens: int) -> str:
        response = self.anthropic_Amanda.messages.create(
            model="claude-haiku-4-5",
            system=System_Prompt,
            max_tokens=max_tokens,
            messages=messages_user,
            tools=TOOLS,
        )

        answer = "No response"

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use":
                    answer = "Claude wants to use the tool: " + block.name
        else:
            for block in response.content:
                if block.type == "text":
                    answer = block.text

        return answer


amanda = ChatBot()