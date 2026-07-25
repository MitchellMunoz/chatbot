import json
from anthropic import Anthropic
from dotenv import load_dotenv
from pathlib import Path
from app.tools import TOOLS, current_datetime_text, run_tool

load_dotenv()

System_Prompt = Path("app/prompt.md").read_text()

MODEL = "claude-sonnet-4-5"

MAX_TOOL_ITERATIONS = 8


class ChatBot:
    def __init__(self):
        self.anthropic_Amanda = Anthropic()

    def generate_response(self, messages_user, max_tokens):
        messages = list(messages_user)

        for iteration in range(MAX_TOOL_ITERATIONS):
            system_prompt = System_Prompt + f"\n\n## Fecha y hora actual\nHoy es {current_datetime_text()}."

            response = self.anthropic_Amanda.messages.create(
                model=MODEL,
                system=system_prompt,
                max_tokens=max_tokens,
                messages=messages,
                tools=TOOLS,
            )

            if response.stop_reason != "tool_use":
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                answer = "\n".join(text_parts).strip()
                if answer:
                    return answer
                return "No response"

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_tool(block.name, block.input)
                    result_json = json.dumps(result, ensure_ascii=False, default=str)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    })

            messages.append({"role": "user", "content": tool_results})

        return (
            "Lo siento, no pude completar la solicitud en este momento. "
            "Permítame trasladarlo con un agente de reservaciones."
        )


amanda = ChatBot()
