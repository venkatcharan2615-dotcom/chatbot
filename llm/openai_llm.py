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
