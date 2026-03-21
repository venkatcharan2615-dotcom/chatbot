from openai import OpenAI
import os
from typing import List
from models import Product

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def summarize_products(products: List[Product]) -> str:
    prompt = "Compare the following products and suggest the best one for a user who wants to save money and time. Explain your reasoning.\n\n"
    for p in products:
        prompt += f"- {p.name} | Price: {p.price} | Site: {p.site} | Rating: {p.rating}\n"
    prompt += "\nGive a clear, concise recommendation."
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
