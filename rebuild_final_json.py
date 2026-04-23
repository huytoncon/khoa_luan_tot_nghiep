import pandas as pd
import os
import glob
import re
import json

def clean_price(price):
    if pd.isna(price) or price == "": return 0.0
    
    # Nếu bản chất nó là số (float/int), trả về luôn
    if isinstance(price, (int, float)):
        val = float(price)
        if val < 1000 and val > 0: return 0.0
        return val

    price_str = str(price).strip()
    
    # Xử lý các đuôi thập phân vô nghĩa của tiền (như .0, .00, ,00) trước
    price_str = re.sub(r'[.,]0+$', '', price_str)
    
    # Xóa "đ", "₫", "vnd", dấu cách
    price_str = re.sub(r'[^\d.,]', '', price_str)
    
    # Xử lý dấu phẩy/chấm phân cách hàng nghìn
    price_str = price_str.replace(',', '').replace('.', '')
    
    try:
        val = float(price_str) if price_str else 0.0
        # Nếu đang ở đơn vị float bị nhân 10 kiểu cũ (hiếm khi xảy ra vì đã cover ở if type số)
        if val < 1000 and val > 0: return 0.0
        return val
    except:
        return 0.0

def clean_sold(sold):
    if pd.isna(sold) or sold == "": return 0
    sold_str = str(sold).lower()
    match = re.search(r'(\d+[\d\.]*)', sold_str)
    if not match: return 0
    val_str = match.group(1).replace('.', '')
    try:
        val = float(val_str)
        if 'k' in sold_str: val *= 1000
        return int(val)
    except:
        return 0

def clean_name(name):
    if pd.isna(name): return ""
    name = str(name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name

def is_phone(name, price, category=""):
    name_lower = name.lower()
    cat_lower = str(category).lower()
    
    # Non-phone items keywords
    exclude_keywords = [
        'ốp ', 'case', 'cường lực', 'sạc', 'cáp', 'tai nghe', 'buds', 'watch', 
        'dây ', 'túi ', 'bao da', 'charm', 'nơ ', 'kính ', 'giá đỡ', 'quạt ', 'bút ',
        'box', 'hộp ', 'tablet', 'máy tính bảng', 'ipad', 'tab ', 'đế ', 'loa ', 
        'mouse', 'chuột', 'keyboard', 'bàn phím', 'tay cầm', 'gamepad', 'remote',
        'sim', 'thẻ nhớ', 'usb', 'pin dự phòng', 'hộp đựng', 'miếng dán', 'balo',
        'flypods', 'airpods', 'freebuds', 'galaxy buds', 'gear', 'fit ', 'band',
        'sách', 'vỏ ', 'lân ', 'đồ chơi', 'mô hình', 'pump', 'vắt sữa', 'bình ',
        'nồi ', 'chảo ', 'máy hút', 'máy lọc', 'vòng đeo', 'đồng hồ', 'adapter',
        'hub', 'đầu chuyển', 'giắc', 'jack', 'cổng', 'chuông', 'camera giám sát',
        'thẻ cào', 'thẻ game', 'vòng thông minh', 'máy ảnh', 'ống kính', 'phụ kiện',
        'linh kiện', 'màn hình thay', 'pin thay', 'nắp lưng', 'vỏ máy', 'coming soon',
        'coming-soon', 'chờ cập nhật', 'placeholder', 'test product', 'new product is coming',
        'thay màn hình', 'thay pin', 'ép kính', 'sửa chữa', 'bảo hành', 'lì xì', 'voucher'
    ]
    
    for kw in exclude_keywords:
        if kw in name_lower or kw in cat_lower:
            return False
            
    # Heuristic for price: real phones > 500k and < 100M
    if price < 500000 or price > 80000000:
        return False
        
    return True

def detect_brand(name, folder_brand):
    name_lower = name.lower()
    brands = {
        'apple': ['iphone', 'apple'],
        'samsung': ['samsung', 'galaxy'],
        'xiaomi': ['xiaomi', 'redmi', 'poco'],
        'oppo': ['oppo', 'reno'],
        'vivo': ['vivo', 'iqoo'],
        'realme': ['realme'],
        'nubia': ['nubia', 'redmagic'],
        'honor': ['honor'],
        'asus': ['rog phone', 'zenfone'],
        'sony': ['xperia'],
        'nokia': ['nokia'],
        'google': ['pixel'],
        'tecno': ['tecno'],
        'infinix': ['infinix'],
        'huawei': ['huawei'],
    }
    
    for brand, keywords in brands.items():
        if any(kw in name_lower for kw in keywords):
            return brand
            
    return folder_brand.lower()

def rebuild():
    base_path = r'd:\LUAN_AN\newdata'
    all_data = []
    seen_urls = set()
    
    csv_files = glob.glob(os.path.join(base_path, '**', '*.csv'), recursive=True)
    print(f"Found {len(csv_files)} CSV files")
    
    for file_path in csv_files:
        rel_path = os.path.relpath(file_path, base_path)
        parts = rel_path.split(os.sep)
        
        platform = parts[0] if len(parts) > 0 else "unknown"
        folder_brand = parts[1] if len(parts) > 1 else "unknown"
        
        try:
            # Try different encodings
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except:
                df = pd.read_csv(file_path, encoding='latin1')
            
            df.columns = [c.strip() for c in df.columns]
            
            col_map = {
                'title': 'name',
                'image_url': 'image',
                'url': 'Url', 'URL': 'Url', 'link': 'Url',
                'location': 'locate',
                'price_numeric': 'price',
                'sold_numeric': 'sold',
                'star_rating': 'star', 'rating': 'star'
            }
            df = df.rename(columns=col_map)
            
            items_added = 0
            for _, row in df.iterrows():
                name = clean_name(row.get('name', row.get('title', '')))
                if not name: continue
                
                price = clean_price(row.get('price', 0))
                category = row.get('category', '')
                
                if not is_phone(name, price, category):
                    continue
                
                url = row.get('Url', row.get('url', ''))
                if url and url in seen_urls: continue
                if url: seen_urls.add(url)
                
                item = {
                    'name': name,
                    'price': price,
                    'image': row.get('image', row.get('image_url', '')),
                    'Url': url,
                    'category': category if pd.notna(category) else "",
                    'source': platform,
                    'sold': clean_sold(row.get('sold', 0)),
                    'star': float(row.get('star', 0.0)) if pd.notna(row.get('star')) else 0.0,
                    'locate': row.get('locate', row.get('location', '')) if pd.notna(row.get('locate')) else None,
                    'platform': platform.lower(),
                    'brand': detect_brand(name, folder_brand)
                }
                all_data.append(item)
                items_added += 1
            
            if items_added > 0:
                print(f"  + {items_added} items from {os.path.basename(file_path)}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print(f"Total items collected: {len(all_data)}")
    
    output_path = r'd:\LUAN_AN\final_merged_all.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"Successfully rebuilt {output_path}")

if __name__ == "__main__":
    rebuild()
