import pickle
import time
import numpy as np
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Cấu hình Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY or "YOUR_GEMINI_API_KEY" in GEMINI_API_KEY:
    print("⚠️ CẢNH BÁO: Chưa cấu hình GEMINI_API_KEY trong file .env")
    print("Vui lòng dán API Key của bạn vào file .env để chatbot hoạt động.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Load dữ liệu đã embed
def load_vector_store(file_path='vector_store.pkl'):
    if not os.path.exists(file_path):
        print(f"❌ Lỗi: Không tìm thấy file {file_path}. Hãy chạy create_embeddings.py trước.")
        return None
    with open(file_path, 'rb') as f:
        store = pickle.load(f)
    print("✅ Đã load dữ liệu vector store.")
    return store

# Hàm tìm kiếm
def search(query, model, store, top_k=5):
    # 1. Embed câu hỏi của người dùng
    query_embedding = model.encode([query])
    
    # 2. Tính độ tương đồng cosine với tất cả sản phẩm
    similarities = cosine_similarity(query_embedding, store['embeddings'])[0]
    
    # 3. Lấy top K kết quả cao nhất
    top_indices = similarities.argsort()[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        results.append({
            'score': similarities[idx],
            'text': store['texts'][idx],
            'metadata': store['metadata'][idx]
        })
        
    return results

# Hàm gọi Gemini để trả lời
def generate_gemini_answer(query, results):
    if not GEMINI_API_KEY:
        return "Lỗi: Chưa cấu hình Gemini API Key."

    # Chuẩn bị context từ kết quả tìm kiếm
    context = ""
    for i, res in enumerate(results):
        context += f"--- Sản phẩm {i+1} ---\n{res['text']}\n\n"
    
    prompt = f"""
    Bạn là một chuyên gia tư vấn công nghệ smartphone cao cấp. Bạn có kiến thức sâu rộng về phần cứng (Chipset, RAM, Màn hình, Camera) và luôn cập nhật giá thị trường.

    Dựa vào dữ liệu sản phẩm dưới đây, hãy trả lời khách hàng như một chuyên gia thực thụ:

    HƯỚNG DẪN TRẢ LỜI:
    1. ĐÁNH GIÁ KỸ THUẬT: Đưa ra nhận xét về cấu hình của máy so với mức giá (P/P - Price/Performance).
    2. PHÂN LOẠI NHU CẦU: Phân tích xem máy này phù hợp nhất cho ai (Game thủ, Người làm văn phòng, Học sinh sinh viên, hay Người thích chụp ảnh).
    3. SO SÁNH GIÁ CẢ: Nếu một máy có nhiều nguồn bán, hãy chỉ ra nguồn có giá rẻ nhất và lưu ý về uy tín nguồn đó.
    4. KHUYẾN NGHỊ: Luôn chốt lại một "Lựa chọn đáng tiền nhất" cho khách hàng.
    5. CẤU TRÚC: Dùng Markdown rõ ràng (Bullet points, In đậm các con số quan trọng).

    Dữ liệu sản phẩm từ kho lưu trữ:
    {context}
    
    Câu hỏi của khách: {query}
    
    Trả lời (Tiếng Việt - Phong cách am hiểu, tin cậy):
    """
    
    # Sử dụng model gemini-2.0-flash
    model = genai.GenerativeModel('gemini-2.0-flash')
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            err_str = str(e)
            if '429' in err_str and attempt < max_retries - 1:
                wait_time = 10 * (attempt + 1)
                print(f"⚠️  Gemini 429 - Đợi {wait_time}s rồi thử lại (lần {attempt+1}/{max_retries-1})...")
                time.sleep(wait_time)
            elif '429' in err_str:
                return "⚠️ Chatbot đang bận (quá nhiều yêu cầu). Vui lòng đợi 1-2 phút rồi thử lại."
            else:
                return f"❌ Lỗi khi gọi Gemini: {err_str}"

def main():
    # Load model embedding (local)
    print(" đang tải model embedding...")
    model_embed = SentenceTransformer('all-MiniLM-L6-v2') 
    
    store = load_vector_store()
    if store is None:
        return
    
    print("\n🤖 CHATBOT TÌM KIẾM SẢN PHẨM (GEMINI 2.0 FLASH) ĐÃ SẴN SÀNG!")
    print("--------------------------------------------------")
    
    while True:
        query = input("\n👤 Bạn: ")
        if query.lower() in ['exit', 'quit', 'thoát']:
            break
            
        if not query.strip():
            continue

        # 1. Tìm kiếm context
        results = search(query, model_embed, store)
        
        # 2. Sinh câu trả lời bằng Gemini
        print("🤖 Chatbot đang suy nghĩ...")
        answer = generate_gemini_answer(query, results)
        
        print(f"\n🤖 Chatbot:\n{answer}")
        print("-" * 50)

if __name__ == "__main__":
    main()
