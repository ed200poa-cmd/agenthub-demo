from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from agent.tools import ALL_TOOLS
from agent.memory import get_memory
from providers.chat_model import get_chat_model

SYSTEM_PROMPT = """You are an AI sales agent for AgentHub. Your job is to help the sales team manage leads, score contacts, and automate CRM workflows.

IMPORTANT: Always use your tools before answering. Do not guess — look up real data.

Your capabilities:
- crm_lookup: Find contacts by name, email, or phone
- lead_scorer: Score leads as Hot/Warm/Cold with reasoning
- email_drafter: Write personalized follow-up emails
- calendar_checker: Check available appointment slots
- gohighlevel_sync: Push contacts to GoHighLevel CRM
- zapier_trigger: Fire Zapier automation workflows

When handling a new lead:
1. Look them up in CRM first
2. Score them based on their profile
3. If Hot → sync to GHL + trigger Zapier
4. Draft a personalized email
5. Check calendar for available meeting slots

Be concise, professional, and action-oriented."""


def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


def get_agent_executor(session_id: str) -> AgentExecutor:
    # Vendor is selected by the LLM_PROVIDER env var; everything below is
    # unchanged because all providers return a LangChain BaseChatModel.
    llm = get_chat_model(temperature=0, max_tokens=2048)
    prompt = build_prompt()
    agent = create_tool_calling_agent(llm=llm, tools=ALL_TOOLS, prompt=prompt)
    memory = get_memory(session_id)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=6,
        return_intermediate_steps=True,
    )


async def run_agent(session_id: str, message: str) -> dict:
    executor = get_agent_executor(session_id)
    result = await executor.ainvoke({"input": message})
    steps = []
    for action, observation in result.get("intermediate_steps", []):
        steps.append({
            "tool": action.tool,
            "input": action.tool_input,
            "output": observation,
        })
    return {
        "session_id": session_id,
        "input": message,
        "output": result["output"],
        "steps": steps,
    }
