"""
api_providers.py
----------------
Handles calling external LLM APIs (Claude, Gemini, OpenAI)
with the same JSON knowledge base context.
"""

SYSTEM_PROMPT = """You are a helpful assistant answering questions from document content.

Instructions:
- Answer the questions, with respect to the knowledge provided in context to Indian Patent rights and its SOPs.
- The context was fetched specifically for the user query — use all relevant parts.
- Reference specific sections or pages when helpful.
- Use conversation history only to resolve pronouns like "it" or "that".
# - If the context does not contain the answer, say: "I couldn't find that in the documents.
 - Always use all relevant context, even if the question seems answerable without it. The context is there to help you answer better!
 - If the question is ambiguous, use the context to disambiguate and provide a more specific answer.
 - If the context contains multiple relevant sections, synthesize them into a comprehensive answer.
 -If no relevant information is found in the context, answer it but say specifically "I couldn't find that in the documents, but based on my general knowledge..." to ensure the user knows the answer is not grounded in the provided context.
"""

def call_claude(api_key: str, context: str, history: list, question: str, model: str = "claude-sonnet-4-5") -> str:
    import anthropic
    client   = anthropic.Anthropic(api_key=api_key)
    messages = _build_messages(history, context, question)
    response = client.messages.create(
        model      = model,
        max_tokens = 1024,
        system     = SYSTEM_PROMPT,
        messages   = messages,
    )
    return response.content[0].text


def call_gemini(api_key: str, context: str, history: list, question: str, model: str = "gemini-1.5-flash") -> str:
    import google.generativeai as genai
    import time

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name         = model,
        system_instruction = SYSTEM_PROMPT,
    )

    chat_history = []
    for h, a in history[:-1]:
        chat_history.append({"role": "user",  "parts": [h]})
        chat_history.append({"role": "model", "parts": [a]})

    chat   = model.start_chat(history=chat_history)
    prompt = f"USER QUERY:\n{question}\n\nRETRIEVED CONTEXT:\n{context}"

    # Truncate context to stay well within free tier token limits
    max_context = 2000
    if len(context) > max_context:
        context = context[:max_context] + "\n[context truncated]"
        # Rebuild prompt with truncated context
        prompt = (
            f"USER QUERY:\n{question}\n\n"
            f"RETRIEVED CONTEXT:\n{context}"
        )

    try:
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            raise Exception(
                "RATE_LIMIT: Gemini free tier quota reached (daily or per-minute limit). "
                "Options: (1) Wait until tomorrow for daily quota reset. "
                "(2) Use Claude or OpenAI instead. "
                "(3) Add billing to your Google Cloud project for paid tier."
            )
        raise


def call_openai(api_key: str, context: str, history: list, question: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client   = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _build_messages(history, context, question)
    response  = client.chat.completions.create(
        model     = model,
        messages  = messages,
        max_tokens = 1024,
    )
    return response.choices[0].message.content


def _build_messages(history: list, context: str, question: str) -> list:
    """Build message list — explicitly passes both query and retrieved context."""
    messages = []
    for h, a in history:
        messages.append({"role": "user",      "content": h})
        messages.append({"role": "assistant", "content": a})
    messages.append({
        "role": "user",
        "content": (
            f"USER QUERY:\n{question}\n\n"
            f"RETRIEVED CONTEXT (passages fetched from documents for this query):\n{context}"
        )
    })
    return messages


def call_groq(api_key: str, context: str, history: list, question: str, model: str = "llama3-70b-8192") -> str:
    from openai import OpenAI   # Groq uses OpenAI-compatible API
    client = OpenAI(
        api_key  = api_key,
        base_url = "https://api.groq.com/openai/v1",
    )
    messages  = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _build_messages(history, context, question)
    response  = client.chat.completions.create(
        model      = model,
        messages   = messages,
        max_tokens = 1024,
    )
    return response.choices[0].message.content


PROVIDERS = {
    "claude": call_claude,
    "gemini": call_gemini,
    "openai": call_openai,
    "groq":   call_groq,
}

PROVIDER_INFO = {
    "claude": {
        "name": "Claude", "icon": "◆", "color": "#e8a87c",
        "default_model": "claude-sonnet-4-5",
        "models": [
            {"id": "claude-sonnet-4-5",      "label": "Claude Sonnet 4.5 (latest)"},
            {"id": "claude-opus-4-5",         "label": "Claude Opus 4.5 (powerful)"},
            {"id": "claude-haiku-4-5-20251001","label": "Claude Haiku 4.5 (fast/cheap)"},
        ]
    },
    "gemini": {
        "name": "Gemini", "icon": "✦", "color": "#4fc3f7",
        "default_model": "gemini-2.0-flash-lite",
        "models": [
            {"id": "gemini-1.5-flash",   "label": "Gemini 1.5 Flash (free, generous limits)"},
            {"id": "gemini-1.5-pro",     "label": "Gemini 1.5 Pro (smarter, lower limits)"},
            {"id": "gemini-2.0-flash",   "label": "Gemini 2.0 Flash (latest, strict limits)"},
            {"id": "gemini-2.0-flash-lite","label": "Gemini 2.0 Flash Lite (30 RPM free — best for rate limits)"},
        ]
    },
    "openai": {
        "name": "OpenAI", "icon": "⬡", "color": "#4ade80",
        "default_model": "gpt-4o-mini",
        "models": [
            {"id": "gpt-4o-mini",  "label": "GPT-4o Mini (cheap, fast)"},
            {"id": "gpt-4o",       "label": "GPT-4o (powerful)"},
            {"id": "gpt-3.5-turbo","label": "GPT-3.5 Turbo (cheapest)"},
        ]
    },
    "groq": {
        "name": "Groq", "icon": "⚡", "color": "#a78bfa",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            {"id": "llama-3.3-70b-versatile",  "label": "Llama 3.3 70B — best quality (FREE)"},
            {"id": "llama-3.1-8b-instant",     "label": "Llama 3.1 8B — fastest (FREE)"},
            {"id": "gemma2-9b-it",             "label": "Gemma 2 9B — Google model (FREE)"},
            {"id": "qwen-qwq-32b",             "label": "Qwen QwQ 32B — reasoning (FREE)"},
            {"id": "mistral-saba-24b",         "label": "Mistral Saba 24B (FREE)"},
        ]
    },
}
