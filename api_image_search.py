"""
Flask API: Tìm kiếm sản phẩm bằng hình ảnh (CLIP) và Chatbot AI (Gemini)
"""
import os
import re
import json
import traceback

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
import secrets
import random

from image_search_clip import ImageSearchCLIP
from gemini_service import search_products, ask_gemini

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
CLIP_EMBEDDINGS_FILE = "clip_embeddings.pkl"
PRODUCTS_FILE = "final_merged_all_fixed.json"
PAGE_SIZE_DEFAULT = 24

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)   # Cần cho Flask session
CORS(app, supports_credentials=True)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Init CLIP ─────────────────────────────────────────────────────────────────
print("\n🟢 Đang khởi tạo hệ thống...")

# Load product catalog vào memory một lần duy nhất
print("   - Loading product catalog...")
_all_products: list = []
if os.path.exists(PRODUCTS_FILE):
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    _all_products = [
        {**p, "price": int(str(p.get("price", 0)).replace(",", "").replace(".", "") or 0)}
        for p in raw
        if p.get("price", 0)
    ]
    random.shuffle(_all_products)
    print(f"   ✓ Loaded {len(_all_products)} products.")
else:
    print(f"   ⚠️  {PRODUCTS_FILE} not found.")

print("   - Loading CLIP Model...")
searcher_clip = ImageSearchCLIP()

if os.path.exists(CLIP_EMBEDDINGS_FILE):
    searcher_clip.load_embeddings(CLIP_EMBEDDINGS_FILE)
    print("   ✓ CLIP Embeddings loaded.")
else:
    print("   ⚠️  CLIP Embeddings not found (image search won't work).")

print("🟢 Hệ thống sẵn sàng!\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _filter_and_sort(products: list, search: str, brand: str, storage: str, source: str, sort: str,
                     price_min: int = 0, price_max: int = 0) -> list:
    """Lọc và sắp xếp danh sách sản phẩm theo các tiêu chí."""
    result = products

    if search:
        kw = search.lower()
        result = [p for p in result if kw in (p.get("name", "") or "").lower()]
    if brand and brand != "all":
        result = [p for p in result if brand.lower() in (p.get("name", "") or "").lower()]
    if storage and storage != "all":
        result = [p for p in result if storage in (p.get("name", "") or "")]
    if source and source != "all":
        result = [p for p in result if p.get("source") == source]
    if price_min > 0 or price_max > 0:
        result = [p for p in result if price_min <= p.get("price", 0) <= price_max]

    reverse = sort in ("price-desc", "sold-desc", "rating-desc")
    key_map = {
        "price-asc": lambda p: p.get("price", 0),
        "price-desc": lambda p: p.get("price", 0),
        "sold-desc": lambda p: float(p.get("sold", 0) or 0),
        "rating-desc": lambda p: float(p.get("star", 0) or 0),
    }
    if sort in key_map:
        result = sorted(result, key=key_map[sort], reverse=reverse)

    return result


def get_chat_history() -> list:
    """Lấy lịch sử chat từ server-side session."""
    return session.get("chat_history", [])


def save_chat_history(history: list) -> None:
    """Lưu lịch sử chat vào server-side session."""
    session["chat_history"] = history


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/search-by-image", methods=["POST"])
def search_by_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400

        file = request.files["image"]
        if not file.filename or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file"}), 400

        image = Image.open(file.stream).convert("RGB")
        top_k = int(request.form.get("top_k", 5))

        results = searcher_clip.search_by_image_memory(image, top_k=top_k)
        return jsonify({"success": True, "results": results})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    print("--- Nhận request chat ---")
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"answer": "Lỗi format dữ liệu (JSON Invalid)"}), 400

        query = data.get("query", "").strip()
        if not query:
            return jsonify({"answer": "Vui lòng nhập câu hỏi."})

        # Tìm kiếm sản phẩm liên quan
        print(f"🔎 Tìm kiếm: {query}")
        search_results = search_products(query)
        print(f"   => Tìm thấy {len(search_results)} sản phẩm")

        # Lấy lịch sử hội thoại và gọi Gemini
        history = get_chat_history()
        print(f"💬 Lịch sử: {len(history) // 2} lượt trước")

        print("🤖 Vui lòng đợi giây lát...")
        answer = ask_gemini(query, search_results, history=history)
        print("✅ Gemini đã trả lời.")

        # Cập nhật lịch sử hội thoại (định dạng Gemini Chat)
        history.append({"role": "user", "parts": [query]})
        history.append({"role": "model", "parts": [answer]})
        save_chat_history(history)

        return jsonify({
            "answer": answer,
            "related_products": [r["metadata"] for r in search_results[:3]],
        })

    except Exception as e:
        print(f"❌ Exception in /api/chat: {e}")
        traceback.print_exc()
        return jsonify({"answer": f"Đã có lỗi xảy ra: {e}"})


@app.route("/api/chat/reset", methods=["POST"])
def reset_chat():
    """Xóa lịch sử hội thoại của session hiện tại."""
    session.pop("chat_history", None)
    return jsonify({"status": "ok", "message": "Đã xóa lịch sử hội thoại."})


@app.route("/api/products", methods=["GET"])
def get_products():
    """Phân trang sản phẩm server-side — tránh load 1.8MB JSON về browser."""
    page = max(1, int(request.args.get("page", 1)))
    page_size = int(request.args.get("page_size", PAGE_SIZE_DEFAULT))
    search = request.args.get("search", "").strip()
    brand = request.args.get("brand", "all")
    storage = request.args.get("storage", "all")
    source = request.args.get("source", "all")
    sort = request.args.get("sort", "random")
    price_min = int(request.args.get("price_min", 0))
    price_max = int(request.args.get("price_max", 0))

    filtered = _filter_and_sort(_all_products, search, brand, storage, source, sort, price_min, price_max)

    total = len(filtered)
    start = (page - 1) * page_size
    items = filtered[start: start + page_size]

    return jsonify({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size),  # ceiling division
    })


@app.route("/api/products/meta", methods=["GET"])
def get_products_meta():
    """Trả về metadata để populate dropdown filter (brands, storages, sources)."""
    brands = ["iPhone", "Samsung", "Xiaomi", "OPPO", "Vivo", "Realme", "Nokia", "Motorola", "Google Pixel", "OnePlus"]
    found_brands = [b for b in brands if any(b.lower() in (p.get("name", "") or "").lower() for p in _all_products)]

    all_storages = ["128GB", "256GB", "512GB", "1TB", "2TB"]
    found_storages = [s for s in all_storages if any(s in (p.get("name", "") or "") for p in _all_products)]

    sources = sorted(set(p["source"] for p in _all_products if p.get("source")))

    prices = [p["price"] for p in _all_products if p.get("price", 0) > 0]

    return jsonify({
        "total_products": len(_all_products),
        "brands": found_brands,
        "storages": found_storages,
        "sources": sources,
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 100000000,
    })


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "clip_ready": searcher_clip.embeddings is not None,
        "chatbot_ready": True,
        "total_products": len(_all_products),
    })


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 Server đang chạy tại: http://localhost:5001")
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5001, debug=debug_mode)
