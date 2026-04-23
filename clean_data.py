import json
import os
import pickle
import numpy as np

def clean_data():
    file_path = "final_merged_all_fixed.json"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Initial count: {len(data)}")

    # Giá trần hợp lý cho điện thoại (100 triệu)
    MAX_PRICE = 100_000_000

    # Danh sách tên/từ khóa sản phẩm rác cần loại bỏ hoàn toàn
    unwanted_keywords = [
        "New Product Is Coming", "Sony Ericsson Z710i", "Tecumseh Engine Repair Kit",
        "Terminal Block Studs", "ACTTO | Samsung Galaxy S", "Kesoto Octopu Kite",
        "Nubia 65W GaN Charger", "Nokia E72 Purple", "màn hình zte nubia neo 3",
        "Chính Hãng Galaxy S24 Siêu Dọc Gương Xem Ví", "Samsung Diva folder S5150",
        "Dr.Martens Lofers", "Transfer Bed Sheet", "Nubia 66W PD Quick charge",
        "6.7'' 100% Original LCD With Defect", "Pin Energizer iPhone",
        "Student-Friendly Phone 16+1Tb",
        "Điện Thoại Xiaomi Redmi 9A 2GB/32GB - Màn hình 6.53in",
        "Samsung Z Flip Hư màn hình", "Pin iPhone 13 Pro Volwatt",
        "Samsung Galaxy A02", "REDMI NOTE 8 4G/64gb chính hãng giá rẻ",
        "Super AMOLED Zflip5 LCD", "S24 Ultra điên thoại Chính Hãng đt giá rẻ",
        "camera sau xiaomi mi 13t", "Điện thoại di động S24 Ultra giá rẽ",
        "Pin iPhone 13 Pro Max Volwatt", "ĐIỆN THOẠI SAMSUNG A20 MÁY TÂN TRANG",
        "Nubia Redmagic 45W 10000Mah 2C Power Bank", "Nubia Redmagic Cooler 6 Pro",
        "ĐIỆN THOẠI SAMSUNG GALAXY A750 A7 2018",
        "Poco M3 Ram 6G/128gb điện thoại chính hãng", "Redmi 9T Ram 6G/128gb",
        "Redmi 9C pin 5000mAh điện thoại chính hãng", "Samsung Galaxy A50 RAM 4G/64G Tân Trang",
        "16 + 512GB memory cheap smart phone", "ANTA | Moisture Wicking Women's T-Shirt",
        "Flipsuit Galaxy Z Flip6", "Pin Energizer iPhone 13 PRO",
    ]

    def is_unwanted(product):
        name = product.get("name", "")
        for kw in unwanted_keywords:
            if kw.lower() in name.lower():
                return True
        return False

    # Giá trần hợp lý: 50 triệu VNĐ (đủ cho cả foldable cao cấp nhất)
    # Giá sàn: 3 triệu VNĐ (loại bỏ hàng rác, hàng dỏm)
    MAX_PRICE = 50_000_000
    MIN_PRICE = 3_000_000

    def is_price_sane(product):
        """Loại bỏ listing giá ảo vượt ngưỡng hợp lý hoặc quá rẻ."""
        try:
            price = float(product.get("price", 0) or 0)
            return MIN_PRICE <= price <= MAX_PRICE
        except (ValueError, TypeError):
            return False

    before = len(data)
    cleaned_data = [p for p in data if not is_unwanted(p) and is_price_sane(p)]

    print(f"Final count: {len(cleaned_data)}")
    print(f"Removed from JSON: {before - len(cleaned_data)} items "
          f"(keyword: {sum(1 for p in data if is_unwanted(p))}, "
          f"invalid_price (<{MIN_PRICE//1_000_000}tr or >{MAX_PRICE//1_000_000}tr): {sum(1 for p in data if not is_unwanted(p) and not is_price_sane(p))})")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    # Cập nhật cả file gốc nếu cần
    orig_path = "final_merged_all.json"
    if os.path.exists(orig_path):
         with open(orig_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
         print(f"Updated {orig_path}")
    
    # Làm sạch file CLIP Pickle
    clip_file = "clip_embeddings.pkl"
    if os.path.exists(clip_file):
        with open(clip_file, "rb") as f:
            clip_data = pickle.load(f)
        
        prods = clip_data['products']
        embs = clip_data['embeddings']
        paths = clip_data['image_paths']

        print(f"CLIP items initial: {len(prods)}")
        
        indices_to_keep = [i for i, p in enumerate(prods) if not is_unwanted(p)]
        
        new_prods = [prods[i] for i in indices_to_keep]
        new_paths = [paths[i] for i in indices_to_keep]
        new_embs = embs[indices_to_keep]

        clip_data['products'] = new_prods
        clip_data['image_paths'] = new_paths
        clip_data['embeddings'] = new_embs

        with open(clip_file, "wb") as f:
            pickle.dump(clip_data, f)
        
        print(f"CLIP items final: {len(new_prods)}")
        print(f"Removed from CLIP: {len(prods) - len(new_prods)} items.")

if __name__ == "__main__":
    clean_data()
