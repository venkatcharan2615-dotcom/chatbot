import os
from typing import List
from models import Product


def summarize_products(products: List[Product]) -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not groq_key and not openai_key:
        priced = [p for p in products if p.price > 0]
        if priced:
            best = min(priced, key=lambda p: p.price)
            return f"Recommendation: {best.name} from {best.site} at ₹{best.price:,.0f} (lowest price). Note: AI summary unavailable - no API key set."
        return "No priced products found. Please check the sites directly for current prices."

    try:
        from openai import OpenAI

        if groq_key:
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            model = "llama-3.3-70b-versatile"
        else:
            client = OpenAI(api_key=openai_key)
            model = "gpt-3.5-turbo"

        prompt = "Compare the following products and suggest the best one for a user who wants to save money and time. Explain your reasoning.\n\n"
        for p in products:
            if p.price > 0:
                prompt += f"- {p.name} | Price: ₹{p.price:,.0f} | Site: {p.site}"
                if p.rating:
                    prompt += f" | Rating: {p.rating}"
                prompt += "\n"
        prompt += "\nGive a clear, concise recommendation in 2-3 sentences."

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        priced = [p for p in products if p.price > 0]
        if priced:
            best = min(priced, key=lambda p: p.price)
            return f"Recommendation: {best.name} from {best.site} at ₹{best.price:,.0f} (lowest price)."
        return "Could not determine best price. Please check the sites directly."


async def chat_with_ai(message: str, history: list = None) -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not groq_key and not openai_key:
        return "Sorry, AI chat is not available right now. Please set up a GROQ_API_KEY or OPENAI_API_KEY."

    try:
        # Web search grounding — fetch current info from the web
        from scrapers._google_helper import brave_web_search
        web_context = await brave_web_search(message)

        from openai import OpenAI

        if groq_key:
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            model = "llama-3.3-70b-versatile"
        else:
            client = OpenAI(api_key=openai_key)
            model = "gpt-3.5-turbo"

        system_content = (
            "You are SmartBot, ShopSmart's shopping assistant. Rules: "
            "1) Give SHORT replies — 2-3 lines max with key info only. "
            "2) End with 'Want detailed specs/comparison? Just ask!' when relevant. "
            "3) Use bullet points for lists. "
            "4) Be friendly and casual. "
            "5) For prices say 'check the Compare tab for live prices'. "
            "6) Never write long paragraphs."
        )
        if web_context:
            system_content += (
                "\n\nIMPORTANT: Use the following CURRENT web search results to answer accurately. "
                "Do NOT rely on your training data for recent product info.\n\n"
                f"Web search results for \"{message}\":\n{web_context}"
            )

        system_msg = {"role": "system", "content": system_content}

        messages = [system_msg]
        if history:
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=250
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"
