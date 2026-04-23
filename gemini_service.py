"""
Shared Gemini + Text Search service (DRY - tránh trùng lặp giữa các module)
"""
import os
import re
import time
import pickle
import numpy as np

import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TEXT_EMBEDDINGS_FILE = "vector_store.pkl"

# Dùng model tiếng Việt thay vì all-MiniLM-L6-v2 (tối ưu tiếng Anh)
EMBEDDING_MODEL = "keepitreal/vietnamese-sbert"

PRICE_BOOST = 0.3
PRICE_PENALTY = 0.1
TOP_K_DEFAULT = 15
MAX_HISTORY_TURNS = 5        # Giữ tối đa 5 lượt hội thoại gần nhất
MAX_RETRIES = 3

# ── Init ──────────────────────────────────────────────────────────────────────
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

print(f"   - Loading Text Embedding Model: {EMBEDDING_MODEL}...")
model_text = SentenceTransformer(EMBEDDING_MODEL)
print("   ✓ Embedding model loaded.")

store_text = None
if os.path.exists(TEXT_EMBEDDINGS_FILE):
    with open(TEXT_EMBEDDINGS_FILE, "rb") as f:
        store_text = pickle.load(f)
    print(f"   ✓ Text vector store loaded ({len(store_text['texts'])} items).")
else:
    print(f"   ⚠️  {TEXT_EMBEDDINGS_FILE} not found.")


# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_price_query(query: str):
    """Trích xuất tầm giá từ câu hỏi tiếng Việt."""
    query = query.lower().replace("tr", "triệu").replace("k", "000")
    million_matches = re.findall(r"(\d+[\.,]?\d*)\s*triệu", query)

    prices = []
    for m in million_matches:
        try:
            prices.append(float(m.replace(",", ".")) * 1_000_000)
        except ValueError:
            continue

    if not prices:
        return None, None

    if any(kw in query for kw in ["dưới", "nhỏ hơn"]):
        return 0, max(prices)
    if any(kw in query for kw in ["trên", "hơn", "lớn hơn"]):
        return min(prices), 999_999_999
    if len(prices) >= 2:
        return min(prices), max(prices)

    # Một mức giá cụ thể → biên ±20%
    p = prices[0]
    return p * 0.8, p * 1.2


def search_products(query: str, top_k: int = TOP_K_DEFAULT) -> list:
    """Tìm kiếm sản phẩm bằng semantic search + price boosting."""
    if not store_text:
        return []

    query_embedding = model_text.encode([query])
    similarities = cosine_similarity(query_embedding, store_text["embeddings"])[0]

    min_p, max_p = parse_price_query(query)

    results = []
    for idx, base_score in enumerate(similarities):
        score = float(base_score)
        item_price = store_text["metadata"][idx].get("price", 0)

        if min_p is not None:
            if min_p <= item_price <= max_p:
                score += PRICE_BOOST
            else:
                score -= PRICE_PENALTY

        results.append({
            "score": score,
            "text": store_text["texts"][idx],
            "metadata": store_text["metadata"][idx],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def ask_gemini(query: str, context_results: list, history: list | None = None) -> str:
    """
    Gọi Gemini với context sản phẩm và lịch sử hội thoại.

    Args:
        query: Câu hỏi hiện tại.
        context_results: Kết quả tìm kiếm từ vector store.
        history: Danh sách dict {"role": "user"/"model", "parts": [str]}.
                 Nếu None → stateless (không nhớ ngữ cảnh).
    """
    if not GEMINI_API_KEY:
        return "Xin lỗi, chatbot chưa được cấu hình API Key."

    context = "\n\n".join(
        f"--- Thông tin {i+1} ---\n{r['text']}"
        for i, r in enumerate(context_results)
    )

    system_prompt = """Bạn là chuyên gia tư vấn công nghệ smartphone với hơn 10 năm kinh nghiệm.
Nhiệm vụ: hỗ trợ khách hàng tìm điện thoại phù hợp từ dữ liệu FPT Shop, Thế Giới Di Động, Hoàng Hà Mobile, Shopee, Lazada.

QUY TẮC PHẢI TUÂN THỦ:
1. PHÂN TÍCH CHUYÊN SÂU: Giải thích TẠI SAO sản phẩm phù hợp (cấu hình, camera, giá trị lâu dài).
2. SO SÁNH QUYẾT ĐOÁN: Chỉ ra "Best Buy" và lý do rõ ràng.
3. ĐỘ TIN CẬY: Nêu nguồn bán (FPT, TGDĐ, Shopee...) để khách cân nhắc bảo hành.
4. ĐỊNH DẠNG: Dùng Markdown (in đậm, danh sách, bảng so sánh) cho dễ đọc.
5. GIỌNG VĂN: Chuyên nghiệp, am hiểu, gần gũi.
6. NHỚ NGỮ CẢNH: Nếu khách hỏi tiếp theo, hãy liên kết với câu hỏi trước."""

    current_message = f"""Dữ liệu sản phẩm từ hệ thống:
{context}

Câu hỏi của khách: {query}

Trả lời bằng Tiếng Việt:"""

    gemini_model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )

    # Giới hạn lịch sử để tránh context quá dài
    trimmed_history = (history or [])[-MAX_HISTORY_TURNS * 2:]

    chat = gemini_model.start_chat(history=trimmed_history)

    for attempt in range(MAX_RETRIES):
        try:
            response = chat.send_message(current_message)
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < MAX_RETRIES - 1:
                wait = 10 * (attempt + 1)
                print(f"   ⚠️  Gemini 429 – đợi {wait}s (lần {attempt+1})...")
                time.sleep(wait)
            elif "429" in err:
                return "⚠️ Chatbot đang bận (quá nhiều yêu cầu). Vui lòng đợi 1-2 phút rồi thử lại."
            else:
                return f"Lỗi Gemini: {err}"
