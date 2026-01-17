import asyncio
import json

from google import genai
from google.genai import types
from fastmcp import Client

REMOTE_SERVER_URL = "http://localhost:8000/mcp"


def safe_json_load(text: str):
    try:
        text = text.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()

        return json.loads(text)
    except Exception:
        return None


async def main():
    user_prompt = input("Enter request / intake text: ")

    gemini = genai.Client()
    mcp_client = Client(REMOTE_SERVER_URL)

    try:
        async with mcp_client:
            await mcp_client.initialize()

            print("\n📌 Fetching config resources from MCP server...\n")

            taxonomy_res = await mcp_client.read_resource("config://taxonomy")
            severity_res = await mcp_client.read_resource("config://severity_rules")
            routing_res = await mcp_client.read_resource("config://routing")

            taxonomy_text = taxonomy_res[0].text if taxonomy_res else ""
            severity_text = severity_res[0].text if severity_res else ""
            routing_text = routing_res[0].text if routing_res else ""

            print("✅ Taxonomy loaded")
            print("✅ Severity rules loaded")
            print("✅ Routing rules loaded")

            # --------------------------------------------------
            # Strong system prompt for tool flow
            # --------------------------------------------------
            history = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text=(
                                "You are an Intelligent Intake and Triage assistant.\n"
                                "You MUST use MCP tools to triage.\n\n"
                                "TOOLS AVAILABLE:\n"
                                "- triage_intake(text)\n"
                                "- classify_intake(text)\n"
                                "- score_severity(text, category)\n"
                                "- route_case(category, score)\n\n"
                                "RULES:\n"
                                "1) ALWAYS call triage_intake(text) first.\n"
                                "2) If triage_intake returns needs_llm=true, then:\n"
                                "   a) Choose the best category yourself using taxonomy\n"
                                "   b) Call score_severity(text, category)\n"
                                "   c) Call route_case(category, score)\n"
                                "3) FINAL output MUST be JSON exactly in this format:\n\n"
                                "{\n"
                                '  "needs_llm": true,\n'
                                '  "llm_decision": {\n'
                                '    "selected_category": "...",\n'
                                '    "reason": "..."\n'
                                "  },\n"
                                '  "category": "...",\n'
                                '  "severity_level": "...",\n'
                                '  "severity_score": 0,\n'
                                '  "priority": "...",\n'
                                '  "destination": "...",\n'
                                '  "reason": "..."\n'
                                "}\n\n"
                                "IMPORTANT:\n"
                                "- If triage_intake returns needs_llm=false, then:\n"
                                "  - set needs_llm=false\n"
                                "  - set llm_decision=null\n\n"
                                "CONFIG RESOURCES (REFERENCE ONLY):\n"
                                f"Taxonomy:\n{taxonomy_text}\n\n"
                                f"Severity Rules:\n{severity_text}\n\n"
                                f"Routing Rules:\n{routing_text}\n\n"
                                "Now triage the user intake."
                            )
                        )
                    ]
                ),
                types.Content(role="user", parts=[types.Part(text=user_prompt)])
            ]

            gemini_tools = [mcp_client.session]

            print("\n🔵 Starting Gemini + MCP tool execution...")

            while True:
                response = await gemini.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=history,
                    config=types.GenerateContentConfig(tools=gemini_tools)
                )

                # ✅ final answer
                if response.text:
                    parsed = safe_json_load(response.text)

                    if parsed:
                        # ----------------------------
                        # 1) Print JSON (optional)
                        # ----------------------------

                        # ----------------------------
                        # 2) Print formatted output
                        # ----------------------------
                        print("\n🟢 Final Triage Result (Formatted):\n")
                        print("====================================")
                        print(f"📌 Category      : {parsed.get('category')}")
                        print(f"🔥 Severity      : {parsed.get('severity_level')}")
                        print(f"📊 Score         : {parsed.get('severity_score')}")
                        print(f"⚡ Priority      : {parsed.get('priority')}")
                        print(f"🏥 Destination   : {parsed.get('destination')}")
                        print(f"📝 Reason        : {parsed.get('reason')}")
                        print("====================================\n")

                        # ✅ EXTRA: Print what LLM decided (ONLY if needs_llm=True)
                        if parsed.get("needs_llm") is True:
                            llm_decision = parsed.get("llm_decision") or {}
                            print("------------------------------------")
                            print(f"✅ Selected Category : {llm_decision.get('selected_category')}")
                            print(f"📝 LLM Reason        : {llm_decision.get('reason')}")
                            print("------------------------------------\n")

                    else:
                        print("\n🟢 Final Answer (Raw):")
                        print(response.text)
                    break

                # ✅ tool call requested
                if response.function_calls:
                    fc = response.function_calls[0]
                    tool_name = fc.name
                    tool_args = dict(fc.args)

                    print(f"\n🤖 Gemini calls tool: {tool_name}")
                    print(f"Args: {tool_args}")

                    result = await mcp_client.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text

                    print("\n🛠 MCP Tool Output:")
                    print(result_text)

                    history.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_function_call(fc)]
                        )
                    )

                    history.append(
                        types.Content(
                            role="function",
                            parts=[
                                types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": result_text}
                                )
                            ]
                        )
                    )

                else:
                    print("\n⚠️ No tool call and no final answer. Stopping.")
                    break

    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("🚀 Starting Intake Triage MCP Client...")
    asyncio.run(main())
