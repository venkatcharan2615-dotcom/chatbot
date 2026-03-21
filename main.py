from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from models import ComparisonRequest, ComparisonResult, Product, ChatRequest, ChatResponse
from scrapers.amazon import scrape_amazon
from scrapers.flipkart import scrape_flipkart
from scrapers.others import (
    scrape_myntra, scrape_snapdeal, scrape_ajio, scrape_tatacliq,
    scrape_zepto, scrape_zomato, scrape_instamart
)
from compare import compare_products
from llm.openai_llm import summarize_products, chat_with_ai
import asyncio

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopSmart - Compare & Chat</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); color: #e2e8f0; min-height: 100vh; }
        .container { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; }
        header { text-align: center; padding: 2rem 0 1rem; }
        .logo { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #38bdf8, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.25rem; }
        .tagline { color: #94a3b8; font-size: 1.05rem; margin-bottom: 1.5rem; }

        /* Tabs */
        .tabs { display: flex; justify-content: center; gap: 0.5rem; margin-bottom: 2rem; }
        .tab { padding: 0.6rem 1.8rem; border-radius: 10px; border: 2px solid #334155; background: transparent; color: #94a3b8; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .tab:hover { border-color: #6366f1; color: #c4b5fd; }
        .tab.active { background: linear-gradient(135deg, #6366f1, #8b5cf6); border-color: transparent; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Compare Tab */
        .search-wrapper { display: flex; gap: 0.75rem; max-width: 650px; margin: 0 auto 1rem; }
        .search-input { flex: 1; padding: 0.9rem 1.2rem; border-radius: 12px; border: 2px solid #334155; background: rgba(30,41,59,0.8); backdrop-filter: blur(8px); color: #f1f5f9; font-size: 1rem; transition: border-color 0.2s; }
        .search-input:focus { outline: none; border-color: #818cf8; box-shadow: 0 0 0 3px rgba(129,140,248,0.15); }
        .search-input::placeholder { color: #64748b; }
        .search-btn { padding: 0.9rem 2rem; border-radius: 12px; border: none; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; font-size: 1rem; font-weight: 600; cursor: pointer; transition: transform 0.15s, box-shadow 0.2s; white-space: nowrap; }
        .search-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(99,102,241,0.4); }
        .search-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
        .sites-bar { display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
        .site-tag { background: rgba(51,65,85,0.6); padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; color: #94a3b8; }
        .loading { display: none; text-align: center; padding: 3rem; }
        .spinner { display: inline-block; width: 40px; height: 40px; border: 3px solid #334155; border-top-color: #818cf8; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { margin-top: 1rem; color: #94a3b8; }
        .summary-card { background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1)); border: 1px solid rgba(129,140,248,0.2); padding: 1.25rem 1.5rem; border-radius: 16px; margin-bottom: 2rem; line-height: 1.6; }
        .summary-card strong { color: #a5b4fc; }
        .section-title { font-size: 1.1rem; font-weight: 600; color: #c4b5fd; margin-bottom: 1rem; }
        .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
        .product-card { background: rgba(30,41,59,0.7); backdrop-filter: blur(8px); border-radius: 16px; padding: 1.25rem; border: 1px solid #334155; transition: transform 0.2s, border-color 0.2s; position: relative; overflow: hidden; }
        .product-card:hover { transform: translateY(-3px); border-color: #475569; }
        .product-card.best { border-color: #4ade80; box-shadow: 0 0 20px rgba(74,222,128,0.1); }
        .best-badge { position: absolute; top: 12px; right: -28px; background: linear-gradient(135deg, #16a34a, #22c55e); color: white; padding: 4px 36px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; transform: rotate(45deg); letter-spacing: 0.5px; }
        .product-name { font-weight: 600; color: #f1f5f9; margin-bottom: 0.75rem; font-size: 0.95rem; line-height: 1.4; padding-right: 1rem; }
        .product-meta { display: flex; justify-content: space-between; align-items: flex-end; }
        .product-price { color: #4ade80; font-size: 1.5rem; font-weight: 700; }
        .product-info { text-align: right; }
        .product-site { display: inline-block; background: rgba(99,102,241,0.15); color: #a5b4fc; padding: 3px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 500; margin-bottom: 4px; }
        .product-rating { color: #fbbf24; font-size: 0.85rem; }
        .product-link { display: inline-block; margin-top: 0.75rem; color: #818cf8; text-decoration: none; font-size: 0.85rem; font-weight: 500; }
        .product-link:hover { color: #a5b4fc; text-decoration: underline; }
        .error-card { background: rgba(127,29,29,0.3); border: 1px solid rgba(239,68,68,0.3); padding: 1.25rem; border-radius: 12px; text-align: center; color: #fca5a5; }

        /* Chat Tab */
        .chat-container { max-width: 750px; margin: 0 auto; display: flex; flex-direction: column; height: 65vh; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 1rem; background: rgba(15,23,42,0.6); border-radius: 16px 16px 0 0; border: 1px solid #334155; border-bottom: none; display: flex; flex-direction: column; gap: 0.75rem; }
        .chat-messages::-webkit-scrollbar { width: 6px; }
        .chat-messages::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
        .msg { max-width: 80%; padding: 0.75rem 1rem; border-radius: 14px; font-size: 0.92rem; line-height: 1.55; word-wrap: break-word; }
        .msg.user { align-self: flex-end; background: linear-gradient(135deg, #6366f1, #7c3aed); color: white; border-bottom-right-radius: 4px; }
        .msg.assistant { align-self: flex-start; background: rgba(51,65,85,0.8); color: #e2e8f0; border-bottom-left-radius: 4px; }
        .msg.assistant .typing-dots span { display: inline-block; width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; margin: 0 2px; animation: bounce 1.2s infinite; }
        .msg.assistant .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .msg.assistant .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }
        .chat-input-row { display: flex; gap: 0.5rem; background: rgba(30,41,59,0.9); padding: 0.75rem; border-radius: 0 0 16px 16px; border: 1px solid #334155; border-top: none; }
        .chat-input { flex: 1; padding: 0.75rem 1rem; border-radius: 10px; border: 2px solid #334155; background: rgba(15,23,42,0.8); color: #f1f5f9; font-size: 0.95rem; resize: none; }
        .chat-input:focus { outline: none; border-color: #818cf8; }
        .chat-input::placeholder { color: #64748b; }
        .chat-send { padding: 0.75rem 1.5rem; border-radius: 10px; border: none; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: transform 0.15s; }
        .chat-send:hover { transform: translateY(-1px); }
        .chat-send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .welcome-msg { text-align: center; color: #64748b; padding: 3rem 1rem; font-size: 0.95rem; }
        .welcome-msg .welcome-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
        .welcome-msg strong { color: #a5b4fc; }

        .footer { text-align: center; margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #1e293b; color: #475569; font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">ShopSmart</div>
            <p class="tagline">Compare prices & chat with AI &mdash; your smart shopping assistant</p>
        </header>

        <div class="tabs">
            <button class="tab active" onclick="switchTab('compare')">&#128269; Compare</button>
            <button class="tab" onclick="switchTab('chat')">&#128172; Chat</button>
        </div>

        <!-- COMPARE TAB -->
        <div class="tab-content active" id="tab-compare">
            <div class="search-wrapper">
                <input class="search-input" type="text" id="query" placeholder="Search any product... (e.g., iPhone 15, running shoes)" onkeypress="if(event.key==='Enter')search()">
                <button class="search-btn" id="searchBtn" onclick="search()">Compare</button>
            </div>
            <div class="sites-bar">
                <span class="site-tag">Amazon</span>
                <span class="site-tag">Flipkart</span>
                <span class="site-tag">Myntra</span>
                <span class="site-tag">Snapdeal</span>
                <span class="site-tag">Ajio</span>
                <span class="site-tag">TataCliq</span>
                <span class="site-tag">Zepto</span>
                <span class="site-tag">Zomato</span>
                <span class="site-tag">Instamart</span>
            </div>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div class="loading-text">Searching across all sites...</div>
            </div>
            <div id="results"></div>
        </div>

        <!-- CHAT TAB -->
        <div class="tab-content" id="tab-chat">
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="welcome-msg">
                        <div class="welcome-icon">&#129302;</div>
                        <strong>Hi! I'm ShopSmart AI</strong><br>
                        Ask me anything &mdash; product advice, comparisons, tech specs, deals, or any question!
                    </div>
                </div>
                <div class="chat-input-row">
                    <input class="chat-input" type="text" id="chatInput" placeholder="Ask me anything..." onkeypress="if(event.key==='Enter')sendChat()">
                    <button class="chat-send" id="chatSendBtn" onclick="sendChat()">Send</button>
                </div>
            </div>
        </div>

        <div class="footer">ShopSmart &mdash; AI-Powered Product Comparison & Chat</div>
    </div>
    <script>
        let chatHistory = [];

        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            event.target.classList.add('active');
            if (tab === 'chat') document.getElementById('chatInput').focus();
            if (tab === 'compare') document.getElementById('query').focus();
        }

        async function search() {
            const query = document.getElementById('query').value.trim();
            if (!query) return;
            const btn = document.getElementById('searchBtn');
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            btn.disabled = true;
            loading.style.display = 'block';
            results.innerHTML = '';
            try {
                const res = await fetch('/chatbot/compare', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Request failed'); }
                const data = await res.json();
                let html = '<div class="summary-card"><strong>AI Recommendation:</strong> ' + data.summary + '</div>';
                html += '<div class="section-title">Found ' + data.all_products.length + ' products</div>';
                html += '<div class="product-grid">';
                data.all_products.forEach(p => {
                    const isBest = p.name === data.best_product.name && p.site === data.best_product.site;
                    html += '<div class="product-card ' + (isBest ? 'best' : '') + '">';
                    if (isBest) html += '<div class="best-badge">Best Deal</div>';
                    html += '<div class="product-name">' + p.name + '</div>';
                    if (p.details) html += '<div style="color:#94a3b8;font-size:0.8rem;margin-bottom:0.5rem;">' + p.details + '</div>';
                    html += '<div class="product-meta">';
                    html += '<div class="product-price">' + (p.price > 0 ? '&#8377;' + p.price.toLocaleString('en-IN') : 'Click to check') + '</div>';
                    html += '<div class="product-info">';
                    html += '<div class="product-site">' + p.site + '</div>';
                    if (p.rating) html += '<div class="product-rating">&#9733; ' + p.rating + '</div>';
                    html += '</div></div>';
                    if (p.url) html += '<a class="product-link" href="' + p.url + '" target="_blank" rel="noopener">View on ' + p.site + ' &rarr;</a>';
                    html += '</div>';
                });
                html += '</div>';
                results.innerHTML = html;
            } catch(e) {
                results.innerHTML = '<div class="error-card">' + e.message + '</div>';
            }
            btn.disabled = false;
            loading.style.display = 'none';
        }

        function escapeHtml(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        async function sendChat() {
            const input = document.getElementById('chatInput');
            const msg = input.value.trim();
            if (!msg) return;
            input.value = '';
            const btn = document.getElementById('chatSendBtn');
            const box = document.getElementById('chatMessages');
            // Remove welcome message
            const welcome = box.querySelector('.welcome-msg');
            if (welcome) welcome.remove();
            // Add user message
            box.innerHTML += '<div class="msg user">' + escapeHtml(msg) + '</div>';
            // Add typing indicator
            box.innerHTML += '<div class="msg assistant" id="typing"><div class="typing-dots"><span></span><span></span><span></span></div></div>';
            box.scrollTop = box.scrollHeight;
            btn.disabled = true;
            try {
                const res = await fetch('/chatbot/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, history: chatHistory})
                });
                const typing = document.getElementById('typing');
                if (typing) typing.remove();
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Request failed'); }
                const data = await res.json();
                chatHistory.push({role: 'user', content: msg});
                chatHistory.push({role: 'assistant', content: data.reply});
                // Keep last 20 messages
                if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
                box.innerHTML += '<div class="msg assistant">' + escapeHtml(data.reply) + '</div>';
            } catch(e) {
                const typing = document.getElementById('typing');
                if (typing) typing.remove();
                box.innerHTML += '<div class="msg assistant" style="color:#fca5a5;">Error: ' + escapeHtml(e.message) + '</div>';
            }
            box.scrollTop = box.scrollHeight;
            btn.disabled = false;
            input.focus();
        }
    </script>
</body>
</html>
"""

SCRAPER_MAP = {
    "amazon": scrape_amazon,
    "flipkart": scrape_flipkart,
    "myntra": scrape_myntra,
    "snapdeal": scrape_snapdeal,
    "ajio": scrape_ajio,
    "tatacliq": scrape_tatacliq,
    "zepto": scrape_zepto,
    "zomato": scrape_zomato,
    "instamart": scrape_instamart,
}

@app.post("/chatbot/compare", response_model=ComparisonResult)
async def compare_endpoint(request: ComparisonRequest):
    try:
        sites = request.sites or list(SCRAPER_MAP.keys())
        tasks = [SCRAPER_MAP[site](request.query) for site in sites if site in SCRAPER_MAP]
        if not tasks:
            raise HTTPException(status_code=400, detail="No valid e-commerce sites specified.")
        results = await asyncio.gather(*tasks)
        all_products = [p for sublist in results for p in sublist]
        if not all_products:
            raise HTTPException(status_code=404, detail="No products found.")
        best = compare_products(all_products)
        summary = summarize_products(all_products)
        return ComparisonResult(best_product=best, all_products=all_products, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chatbot/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
        reply = chat_with_ai(request.message, history)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
