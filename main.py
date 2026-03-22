import asyncio
import logging
import time
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from affiliate import tag_products
from compare import compare_products
from llm.openai_llm import summarize_products, chat_with_ai
from models import ComparisonRequest, ComparisonResult, Product, ChatRequest, ChatResponse
from scrapers._google_helper import batch_search_all_sites
from scrapers.others import scrape_zepto, scrape_zomato, scrape_instamart

app = FastAPI()
logger = logging.getLogger("shopsmart.compare")

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

        /* Comparison Table */
        .compare-table { width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 16px; overflow: hidden; background: rgba(30,41,59,0.7); backdrop-filter: blur(8px); border: 1px solid #334155; }
        .compare-table thead th { background: rgba(99,102,241,0.15); color: #a5b4fc; padding: 0.85rem 1rem; text-align: left; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #334155; }
        .compare-table thead th:first-child { border-radius: 16px 0 0 0; }
        .compare-table thead th:last-child { border-radius: 0 16px 0 0; }
        .compare-table tbody tr { transition: background 0.15s; }
        .compare-table tbody tr:hover { background: rgba(99,102,241,0.06); }
        .compare-table tbody tr:not(:last-child) td { border-bottom: 1px solid rgba(51,65,85,0.5); }
        .compare-table tbody td { padding: 0.9rem 1rem; font-size: 0.9rem; vertical-align: middle; }
        .compare-table .rank { font-weight: 700; color: #64748b; text-align: center; width: 40px; }
        .compare-table .site-cell { white-space: nowrap; }
        .compare-table .site-pill { display: inline-block; background: rgba(99,102,241,0.15); color: #a5b4fc; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }
        .compare-table .name-cell { color: #cbd5e1; line-height: 1.4; max-width: 350px; }
        .compare-table .price-cell { font-weight: 700; font-size: 1.05rem; color: #4ade80; white-space: nowrap; }
        .compare-table .action-cell { text-align: center; }
        .compare-table .visit-btn { display: inline-block; padding: 6px 16px; border-radius: 8px; background: rgba(99,102,241,0.15); color: #818cf8; text-decoration: none; font-size: 0.8rem; font-weight: 600; transition: all 0.15s; border: 1px solid rgba(99,102,241,0.2); }
        .compare-table .visit-btn:hover { background: rgba(99,102,241,0.3); color: #a5b4fc; border-color: rgba(99,102,241,0.4); }
        .compare-table tr.best-row { background: rgba(74,222,128,0.06); }
        .compare-table tr.best-row td { border-bottom-color: rgba(74,222,128,0.2); }
        .best-tag { display: inline-block; background: linear-gradient(135deg, #16a34a, #22c55e); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.65rem; font-weight: 700; text-transform: uppercase; margin-left: 6px; vertical-align: middle; letter-spacing: 0.3px; }
        .no-price-section { margin-top: 1.5rem; }
        .no-price-toggle { cursor: pointer; user-select: none; display: flex; align-items: center; gap: 0.5rem; }
        .no-price-toggle .arrow { transition: transform 0.2s; display: inline-block; }
        .no-price-toggle.open .arrow { transform: rotate(180deg); }
        .no-price-list { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
        .no-price-chip { background: rgba(51,65,85,0.5); border: 1px solid #334155; padding: 6px 14px; border-radius: 10px; display: flex; align-items: center; gap: 0.5rem; }
        .no-price-chip .chip-site { color: #94a3b8; font-size: 0.85rem; font-weight: 500; }
        .no-price-chip a { color: #64748b; text-decoration: none; font-size: 0.75rem; }
        .no-price-chip a:hover { color: #818cf8; text-decoration: underline; }

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

        /* Responsive table */
        @media (max-width: 640px) {
            .compare-table { font-size: 0.82rem; }
            .compare-table thead th, .compare-table tbody td { padding: 0.6rem 0.5rem; }
            .compare-table .name-cell { max-width: 150px; }
            .compare-table .rank { width: 28px; }
        }

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
        .welcome-msg { text-align: center; color: #94a3b8; padding: 2rem 1.5rem; font-size: 0.95rem; line-height: 1.6; }
        .welcome-msg .welcome-icon { font-size: 3rem; margin-bottom: 0.5rem; }
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
            <button class="tab active" onclick="switchTab('compare', this)">&#128269; Compare</button>
            <button class="tab" onclick="switchTab('chat', this)">&#128172; Chat</button>
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
                <span class="site-tag">+ Zepto, Zomato, Instamart for groceries</span>
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
                        <div class="welcome-icon">&#128722;</div>
                        <strong>Welcome to ShopSmart!</strong><br><br>
                        I'm <strong>SmartBot</strong>, your personal shopping assistant. &#128075;<br><br>
                        <span style="color:#94a3b8;">Here's what I can help you with:</span><br>
                        <div style="display:inline-block;text-align:left;margin-top:0.5rem;line-height:2;">
                            &#127993; Product recommendations<br>
                            &#128176; Price &amp; deal tips<br>
                            &#128295; Tech specs &amp; comparisons<br>
                            &#11088; Best brand suggestions
                        </div><br><br>
                        <span style="color:#818cf8;">Try: &quot;Best phone under 20k&quot; or &quot;iPhone vs Samsung&quot;</span>
                    </div>
                </div>
                <div class="chat-input-row">
                    <input class="chat-input" type="text" id="chatInput" placeholder="Ask me anything..." onkeypress="if(event.key==='Enter')sendChat()">
                    <button class="chat-send" id="chatSendBtn" onclick="sendChat()">Send</button>
                </div>
            </div>
        </div>

        <div class="footer">
            ShopSmart &mdash; AI-Powered Product Comparison & Chat<br>
            <span style="font-size:0.7rem;color:#374151;margin-top:4px;display:inline-block;">Some links may earn us a small commission at no extra cost to you. This helps keep ShopSmart free.</span>
        </div>
    </div>
    <script>
        let chatHistory = [];

        function escapeHtml(value) {
            const d = document.createElement('div');
            d.textContent = value == null ? '' : String(value);
            return d.innerHTML;
        }

        function safeUrl(value) {
            if (!value) return '';
            try {
                const url = new URL(value, window.location.origin);
                return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
            } catch (_err) {
                return '';
            }
        }

        function switchTab(tab, btn) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            btn.classList.add('active');
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
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 90000);
                const res = await fetch('/chatbot/compare', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query}),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Request failed'); }
                const data = await res.json();
                const priced = data.all_products.filter(p => p.price > 0).sort((a,b) => a.price - b.price);
                const unpriced = data.all_products.filter(p => p.price <= 0);
                let html = '<div class="summary-card"><strong>&#129302; AI Recommendation:</strong> ' + escapeHtml(data.summary) + '</div>';

                if (priced.length > 0) {
                    html += '<div class="section-title">Price Comparison &mdash; ' + priced.length + ' results found</div>';
                    html += '<table class="compare-table"><thead><tr>';
                    html += '<th>#</th><th>Site</th><th>Product</th><th>Price</th><th>Action</th>';
                    html += '</tr></thead><tbody>';
                    priced.forEach((p, i) => {
                        const isBest = i === 0;
                        const safeSite = escapeHtml(p.site);
                        const safeName = escapeHtml(p.name);
                        const safeHref = safeUrl(p.url);
                        html += '<tr class="' + (isBest ? 'best-row' : '') + '">';
                        html += '<td class="rank">' + (i+1) + '</td>';
                        html += '<td class="site-cell"><span class="site-pill">' + safeSite + '</span></td>';
                        html += '<td class="name-cell">' + safeName;
                        if (isBest) html += '<span class="best-tag">&#9733; Best Price</span>';
                        html += '</td>';
                        html += '<td class="price-cell">&#8377;' + p.price.toLocaleString('en-IN') + '</td>';
                        html += '<td class="action-cell">';
                        if (safeHref) html += '<a class="visit-btn" href="' + safeHref + '" target="_blank" rel="noopener">Visit &rarr;</a>';
                        html += '</td></tr>';
                    });
                    html += '</tbody></table>';
                } else {
                    html += '<div class="section-title">No prices found &mdash; check the sites below</div>';
                }

                if (unpriced.length > 0) {
                    html += '<div class="no-price-section">';
                    html += '<div class="section-title no-price-toggle" id="npToggle" onclick="toggleNp()">'; 
                    html += 'Also check on ' + unpriced.length + ' more site' + (unpriced.length>1?'s':'') + ' <span class="arrow">&#9660;</span></div>';
                    html += '<div class="no-price-list" id="npList" style="display:none;">';
                    unpriced.forEach(p => {
                        const safeSite = escapeHtml(p.site);
                        const safeHref = safeUrl(p.url);
                        html += '<div class="no-price-chip">';
                        html += '<span class="chip-site">' + safeSite + '</span>';
                        if (safeHref) html += '<a href="' + safeHref + '" target="_blank" rel="noopener">Search &rarr;</a>';
                        html += '</div>';
                    });
                    html += '</div></div>';
                }
                results.innerHTML = html;
            } catch(e) {
                results.innerHTML = '<div class="error-card">' + escapeHtml(e.message) + '</div>';
            }
            btn.disabled = false;
            loading.style.display = 'none';
        }

        function toggleNp() {
            var t = document.getElementById('npToggle');
            var l = document.getElementById('npList');
            if (t) t.classList.toggle('open');
            if (l) l.style.display = l.style.display === 'none' ? 'flex' : 'none';
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

# Sites handled by batch search (ONE search covers all of these)
BATCH_SITES = {"amazon", "flipkart", "myntra", "snapdeal", "ajio", "tatacliq"}

# Grocery scrapers still use individual approach
GROCERY_SCRAPER_MAP = {
    "zepto": scrape_zepto,
    "zomato": scrape_zomato,
    "instamart": scrape_instamart,
}

ALL_KNOWN_SITES = BATCH_SITES | set(GROCERY_SCRAPER_MAP.keys())

# Category-aware site selection
GROCERY_SITES = {"zepto", "zomato", "instamart"}
ELECTRONICS_SITES = {"amazon", "flipkart", "snapdeal", "tatacliq"}
FASHION_SITES = {"myntra", "ajio"}
GENERAL_SITES = {"amazon", "flipkart"}  # Always search these

_GROCERY_KW = {"milk", "bread", "rice", "dal", "sugar", "atta", "oil", "eggs", "butter", "cheese",
               "vegetables", "fruits", "snacks", "chips", "biscuits", "chocolate", "juice", "water",
               "grocery", "groceries", "food", "drink", "beverages", "masala", "spice"}
_ELECTRONICS_KW = {"phone", "mobile", "laptop", "tablet", "tv", "television", "headphone", "earbuds",
                   "camera", "watch", "smartwatch", "speaker", "monitor", "printer", "router",
                   "iphone", "samsung", "pixel", "oneplus", "macbook", "ipad", "airpods", "galaxy",
                   "snapdragon", "processor", "chipset", "mediatek", "dimensity", "exynos", "bionic",
                   "smartphone", "5g", "amoled", "oled"}
_FASHION_KW = {"shirt", "tshirt", "jeans", "dress", "shoes", "sneakers", "jacket", "kurta", "saree",
               "kurti", "sandals", "heels", "handbag", "bag", "backpack", "sunglasses", "perfume",
               "makeup", "cosmetics", "lipstick", "foundation", "clothing", "fashion", "wear"}

_EXPENSIVE_KW = {"phone", "mobile", "laptop", "tablet", "tv", "television", "monitor",
                 "iphone", "samsung", "pixel", "oneplus", "macbook", "ipad", "galaxy",
                 "refrigerator", "washing", "microwave", "ac", "air conditioner"}
_MIN_PRICE_EXPENSIVE = 3000  # Phones/laptops won't be Rs 399
_COMPARE_CACHE_TTL_SECONDS = 900
_COMPARE_CACHE = {}


def _site_display_name(site_key: str) -> str:
    return {
        "amazon": "Amazon",
        "flipkart": "Flipkart",
        "myntra": "Myntra",
        "snapdeal": "Snapdeal",
        "ajio": "Ajio",
        "tatacliq": "TataCliq",
        "zepto": "Zepto",
        "zomato": "Zomato",
        "instamart": "Instamart",
    }.get(site_key, site_key.title())


def _site_fallback_url(site_key: str, query: str) -> str:
    encoded_query = quote_plus(query)
    hyphen_query = query.replace(" ", "-")
    if site_key == "amazon":
        return f"https://www.amazon.in/s?k={encoded_query}"
    if site_key == "flipkart":
        return f"https://www.flipkart.com/search?q={encoded_query}"
    if site_key == "myntra":
        return f"https://www.myntra.com/{hyphen_query}"
    if site_key == "snapdeal":
        return f"https://www.snapdeal.com/search?keyword={encoded_query}"
    if site_key == "ajio":
        return f"https://www.ajio.com/search/?text={encoded_query}"
    if site_key == "tatacliq":
        return f"https://www.tatacliq.com/search/?searchCategory=all&text={encoded_query}"
    if site_key == "zepto":
        return f"https://www.zeptonow.com/search?query={encoded_query}"
    if site_key == "zomato":
        return f"https://www.zomato.com/search?q={encoded_query}"
    if site_key == "instamart":
        return f"https://www.swiggy.com/instamart/search?query={encoded_query}"
    return ""


def _build_site_fallback_product(site_key: str, query: str) -> Product:
    display = _site_display_name(site_key)
    return Product(
        name=f"{display} search for {query}",
        price=0,
        url=_site_fallback_url(site_key, query),
        site=display,
        rating=None,
        details=f"Open {display} search results",
    )


def _merge_products(primary_products, fallback_products):
    merged = []
    seen = set()
    for product in list(primary_products) + list(fallback_products):
        key = (product.site.strip().lower(), product.url.strip().lower(), round(product.price, 2))
        if key in seen:
            continue
        seen.add(key)
        merged.append(product)
    return merged


def _build_compare_summary(products, diagnostics, cached=False) -> str:
    priced = [p for p in products if p.price > 0]
    if priced:
        summary = summarize_products(priced)
        if diagnostics.get("partial_failure"):
            return f"{summary} Note: some sites are showing fallback search links because live search was unavailable."
        if cached:
            return f"{summary} Cached results shown from a recent successful search."
        return summary

    fallback_count = len(products)
    source = "cached search results" if cached else "live search"
    if diagnostics.get("partial_failure"):
        return (
            f"Live prices were temporarily unavailable, so showing {fallback_count} site search link"
            f"{'s' if fallback_count != 1 else ''}. Try again shortly for fresh prices."
        )
    return (
        f"No live prices found from {source}. Showing {fallback_count} site search link"
        f"{'s' if fallback_count != 1 else ''} so you can continue manually."
    )


def _cache_key(query: str, sites) -> tuple:
    return query.lower(), tuple(sites)


def _get_cached_compare_result(query: str, sites):
    cached = _COMPARE_CACHE.get(_cache_key(query, sites))
    if not cached:
        return None
    if time.time() - cached["timestamp"] > _COMPARE_CACHE_TTL_SECONDS:
        _COMPARE_CACHE.pop(_cache_key(query, sites), None)
        return None
    return cached["result"]


def _set_cached_compare_result(query: str, sites, result: ComparisonResult) -> None:
    _COMPARE_CACHE[_cache_key(query, sites)] = {
        "timestamp": time.time(),
        "result": result,
    }


def _log_compare_diagnostics(query: str, diagnostics: dict) -> None:
    logger.warning(
        "compare diagnostics | query=%r sites=%s batch_requested=%s batch_error=%r grocery_errors=%s raw_products=%s filtered_products=%s fallback_products=%s partial_failure=%s cache_hit=%s",
        query,
        diagnostics.get("sites"),
        diagnostics.get("batch_requested"),
        diagnostics.get("batch_error"),
        diagnostics.get("grocery_errors"),
        diagnostics.get("raw_products"),
        diagnostics.get("filtered_products"),
        diagnostics.get("fallback_products"),
        diagnostics.get("partial_failure"),
        diagnostics.get("cache_hit", False),
    )

def _pick_sites(query: str) -> list:
    """Pick relevant sites based on query keywords."""
    q_lower = query.lower().split()
    q_words = set(q_lower)
    is_grocery = bool(q_words & _GROCERY_KW)
    is_electronics = bool(q_words & _ELECTRONICS_KW)
    is_fashion = bool(q_words & _FASHION_KW)

    if is_grocery and not is_electronics and not is_fashion:
        return list(GROCERY_SITES | GENERAL_SITES)
    if is_electronics and not is_grocery:
        return list(ELECTRONICS_SITES)  # Only electronics sites for electronics
    if is_fashion and not is_grocery:
        return list(FASHION_SITES | GENERAL_SITES | {"snapdeal", "tatacliq"})
    # Default: all non-grocery sites
    return [s for s in ALL_KNOWN_SITES if s not in GROCERY_SITES]

def _filter_junk_prices(products, query: str):
    """Remove obviously wrong prices (e.g. Rs 399 for a phone = accessory)."""
    q_words = set(query.lower().split())
    if q_words & _EXPENSIVE_KW:
        return [p for p in products if p.price == 0 or p.price >= _MIN_PRICE_EXPENSIVE]
    return products


@app.post("/chatbot/compare", response_model=ComparisonResult)
async def compare_endpoint(request: ComparisonRequest):
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Please enter a product to search for.")
        query = request.query.strip()[:200]  # Limit query length
        if request.sites:
            sites = list(dict.fromkeys(site.strip().lower() for site in request.sites if site and site.strip()))
        else:
            sites = _pick_sites(query)
        
        batch_keys = [s for s in sites if s in BATCH_SITES]
        grocery_keys = [s for s in sites if s in GROCERY_SCRAPER_MAP]
        diagnostics = {
            "sites": sites,
            "batch_requested": batch_keys,
            "batch_error": None,
            "grocery_errors": [],
            "raw_products": 0,
            "filtered_products": 0,
            "fallback_products": 0,
            "partial_failure": False,
        }

        if not batch_keys and not grocery_keys:
            raise HTTPException(status_code=400, detail="No valid e-commerce sites specified.")

        cached_result = _get_cached_compare_result(query, sites)
        if cached_result:
            diagnostics["cache_hit"] = True
            _log_compare_diagnostics(query, diagnostics)
            return cached_result

        # Batch search: ONE search covers all e-commerce sites (2-4 HTTP requests)
        all_products = []
        if batch_keys:
            try:
                all_products = await asyncio.wait_for(
                    batch_search_all_sites(query, batch_keys), timeout=25,
                )
            except (asyncio.TimeoutError, Exception) as exc:
                diagnostics["batch_error"] = type(exc).__name__
                diagnostics["partial_failure"] = True
                all_products = []

        # Grocery sites still use individual scrapers
        if grocery_keys:
            async def _scrape_grocery(site):
                try:
                    return await asyncio.wait_for(GROCERY_SCRAPER_MAP[site](query), timeout=15)
                except (asyncio.TimeoutError, Exception) as exc:
                    diagnostics["grocery_errors"].append({site: type(exc).__name__})
                    diagnostics["partial_failure"] = True
                    return []
            grocery_results = await asyncio.gather(*[_scrape_grocery(s) for s in grocery_keys])
            for sublist in grocery_results:
                all_products.extend(sublist)
        diagnostics["raw_products"] = len(all_products)

        all_products = _filter_junk_prices(all_products, query)
        diagnostics["filtered_products"] = len(all_products)
        fallback_products = [
            _build_site_fallback_product(site, query)
            for site in sites
            if _site_display_name(site) not in {product.site for product in all_products}
        ]
        diagnostics["fallback_products"] = len(fallback_products)
        all_products = _merge_products(all_products, fallback_products)

        if not all_products:
            _log_compare_diagnostics(query, diagnostics)
            raise HTTPException(status_code=404, detail="No products found.")

        best = compare_products(all_products)
        tag_products(all_products)
        summary = _build_compare_summary(all_products, diagnostics)
        result = ComparisonResult(best_product=best, all_products=all_products, summary=summary)
        if any(product.price > 0 for product in all_products):
            _set_cached_compare_result(query, sites, result)
        _log_compare_diagnostics(query, diagnostics)
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong while comparing products.")

@app.post("/chatbot/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Please enter a message.")
        history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
        reply = await chat_with_ai(request.message.strip()[:1000], history)
        return ChatResponse(reply=reply)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong while generating a reply.")
