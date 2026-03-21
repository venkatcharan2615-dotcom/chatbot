import os
from typing import List
from models import Product

def summarize_products(products: List[Product]) -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not groq_key and not openai_key:
        best = min(products, key=lambda p: p.price)
        return f"Recommendation: {best.name} from {best.site} at price {best.price} (lowest price). Note: AI summary unavailable - no API key set."

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
            prompt += f"- {p.name} | Price: {p.price} | Site: {p.site} | Rating: {p.rating}\n"
        prompt += "\nGive a clear, concise recommendation."

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        best = min(products, key=lambda p: p.price)
        return f"Recommendation: {best.name} from {best.site} at price {best.price} (lowest price). Note: AI summary failed - {str(e)}"


def chat_with_ai(message: str, history: list = None) -> str:
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not groq_key and not openai_key:
        return "Sorry, AI chat is not available right now. Please set up a GROQ_API_KEY or OPENAI_API_KEY."

    try:
        from openai import OpenAI

        if groq_key:
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            model = "llama-3.3-70b-versatile"
        else:
            client = OpenAI(api_key=openai_key)
            model = "gpt-3.5-turbo"

        system_msg = {
            "role": "system",
            "content": "You are ShopSmart AI, a helpful shopping assistant. You help users with product recommendations, comparisons, deals, tech specs, and general knowledge. Be concise, friendly, and helpful. If asked about prices, mention that users can use the Compare feature to check live prices across Amazon, Flipkart, Zepto, Zomato, Instamart and more."
        }

        messages = [system_msg]
        if history:
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"
