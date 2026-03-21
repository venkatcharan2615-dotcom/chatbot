# LLM Product Comparison Chatbot

## Overview
A modular Python FastAPI backend for comparing products across all major e-commerce sites (Amazon, Flipkart, Myntra, Snapdeal, Ajio, TataCliq, etc.) using LLMs for reasoning and summarization.

## How to Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set your OpenAI API key in `llm/openai_llm.py` or as an environment variable.
3. Start the server:
   ```bash
   uvicorn main:app --reload
   ```
4. Use the `/chatbot/compare` endpoint (POST) with JSON body:
   ```json
   {
     "query": "iPhone 13",
     "sites": ["amazon", "flipkart", "myntra", "snapdeal", "ajio", "tatacliq"]
   }
   ```

## File Structure
- `main.py`: FastAPI app
- `scrapers/`: Site scrapers (placeholders)
- `llm/`: LLM integration
- `compare.py`: Product comparison logic
- `models.py`: Data models
- `requirements.txt`: Dependencies

## Notes
- Scrapers are placeholders; add real scraping logic as needed.
- LLM integration uses OpenAI as an example.
