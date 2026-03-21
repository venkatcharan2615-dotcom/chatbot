import openai
from typing import List
from models import Product

# Set your OpenAI API key here or use environment variable
openai.api_key = "YOUR_OPENAI_API_KEY"

def summarize_products(products: List[Product]) -> str:
    prompt = f"""
Compare the following products and suggest the best one for a user who wants to save money and time. Explain your reasoning.

"""
    for p in products:
        prompt += f"- {p.name} | Price: {p.price} | Site: {p.site} | Rating: {p.rating}\n"
    prompt += "\nGive a clear, concise recommendation."
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message['content'].strip()
