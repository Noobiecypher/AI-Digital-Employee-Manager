"""
agent_nodes.llm
-----------
Central LLM configuration for the AI Digital Employee Platform.

Every agent that needs LLM capabilities imports from here.
Never import ChatOllama or any LLM provider directly in agent files.

Usage:
    from backend.agent_nodes.llm import llm

    response = llm.invoke("your prompt here")
    print(response.content)

Switching models:
    Change MODEL_NAME below. Nothing else needs to change anywhere.

Requirements:
    1. Install Ollama:
       curl -fsSL https://ollama.com/install.sh | sh

    2. Pull the model:
       ollama pull llama3.1:8b

    3. Start Ollama server:
       ollama serve

    4. Install Python packages:
       pip install langchain langchain-ollama
"""

from langchain_ollama import ChatOllama


# ---------------------------------------------------------------------------
# Config — change only here when switching models
# ---------------------------------------------------------------------------

MODEL_NAME        = "llama3.1:8b"   # or "qwen3:8b", "mistral", etc.
OLLAMA_BASE_URL   = "http://localhost:11434"
TEMPERATURE       = 0.3             # lower = more deterministic, better for structured tasks
MAX_TOKENS        = 2048


# ---------------------------------------------------------------------------
# Shared LLM instance — import this in your agent
# ---------------------------------------------------------------------------

llm = ChatOllama(
    model       = MODEL_NAME,
    base_url    = OLLAMA_BASE_URL,
    temperature = TEMPERATURE,
    num_predict = MAX_TOKENS,
)