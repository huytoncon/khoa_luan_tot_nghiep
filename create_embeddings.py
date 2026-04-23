import json
import pandas as pd
from sentence_transformers import SentenceTransformer
import pickle
import numpy as np
import os

# 1. Load dữ liệu từ file JSON
def load_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Đã load {len(data)} sản phẩm.")
    return data

# 2. Tạo text representation cho mỗi sản phẩm
# Biến mỗi object JSON thành một đoạn văn bản có ý nghĩa để model hiểu được
def create_text_chunks(data):
    chunks = []
    metadata = []
    
    for item in data:
        p = item.get('price', 0)
        # Xử lý giá tiền cho dễ đọc và dễ tìm kiếm
        price_commas = "{:,}".format(p)
        
        # Thêm cách gọi giá kiểu Việt Nam để AI dễ hiểu
        if p >= 1000000:
            price_vietnamese = f"{p/1000000:g} triệu"
        elif p >= 1000:
            price_vietnamese = f"{p/1000:g}k"
        else:
            price_vietnamese = f"{p} đồng"
            
        # Tạo câu mô tả đầy đủ thông tin
        text = (
            f"Sản phẩm: {item.get('name', 'N/A')}. "
            f"Giá: {price_commas} VNĐ ({price_vietnamese}). "
            f"Thương hiệu: {item.get('brand', 'N/A')}. "
            f"Nguồn: {item.get('source', 'N/A')}. "
            f"Đánh giá: {item.get('star', 0)} sao. "
            f"Đã bán: {item.get('sold', 0)}. "
            f"Khu vực: {item.get('locate', 'Không xác định')}. "
            f"Thông tin thêm: {item.get('category', '')}"
        )
        
        chunks.append(text)
        metadata.append(item)
        
    return chunks, metadata

# 3. Tạo embeddings
def generate_embeddings(chunks):
    print("Đang tải model embedding (lần đầu sẽ mất chút thời gian download)...")
    # Sử dụng model vietnamese-sbert để hiểu tiếng Việt tốt hơn
    model = SentenceTransformer('keepitreal/vietnamese-sbert') 
    
    print("Đang tạo embeddings...")
    embeddings = model.encode(chunks, show_progress_bar=True)
    
    return model, embeddings

def main():
    json_file = 'final_merged_all.json'
    if not os.path.exists(json_file):
        print(f"Lỗi: Không tìm thấy file {json_file}")
        return

    # Bước 1: Load data
    data = load_data(json_file)
    
    # Bước 2: Chuẩn bị text
    chunks, metadata = create_text_chunks(data)
    print(f"Mẫu text đầu tiên: {chunks[0]}")
    
    # Bước 3: Embed
    model, embeddings = generate_embeddings(chunks)
    
    # Bước 4: Lưu lại kết quả để dùng cho Chatbot
    output_file = 'vector_store.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump({
            'texts': chunks,
            'metadata': metadata,
            'embeddings': embeddings
        }, f)
        
    print(f"Hoàn tất! Dữ liệu đã được lưu vào {output_file}")
    print("Bạn có thể dùng file này để tìm kiếm và trả lời câu hỏi.")

if __name__ == "__main__":
    main()
