import json
import os
import requests
from urllib.parse import urlparse
import time
import sys
from concurrent.futures import ThreadPoolExecutor
import threading

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Lock for terminal printing and shared counters
print_lock = threading.Lock()
success_count = 0
fail_count = 0
skip_count = 0

def download_single_image(idx, item, output_folder, total_count):
    """Tải một ảnh duy nhất"""
    global success_count, fail_count, skip_count
    
    image_url = item.get('image', '')
    product_name = item.get('name', f'product_{idx}')
    
    if not image_url:
        with print_lock:
            print(f"[{idx}/{total_count}] ✗ Không có URL ảnh cho: {product_name}")
            fail_count += 1
        return

    try:
        # Lấy extension từ URL
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        
        # Xử lý extension
        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]
            extension = ''.join(c for c in extension if c.isalnum())[:10]
            if not extension:
                extension = 'jpg'
        else:
            extension = 'jpg'
        
        # Tạo tên file an toàn
        safe_filename = f"product_{idx}.{extension}"
        file_path = os.path.join(output_folder, safe_filename)
        
        # Kiểm tra nếu ảnh đã tồn tại thì bỏ qua
        if os.path.exists(file_path):
            with print_lock:
                # print(f"[{idx}/{total_count}] → Đã tồn tại: {safe_filename}")
                skip_count += 1
            return

        # Tải ảnh
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Lưu file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        with print_lock:
            print(f"[{idx}/{total_count}] ✓ Đã tải: {safe_filename} ({len(response.content)} bytes)")
            success_count += 1
            
    except Exception as e:
        with print_lock:
            print(f"[{idx}/{total_count}] ✗ Lỗi khi tải {product_name[:30]}: {str(e)[:50]}...")
            fail_count += 1

def download_images_parallel(json_file, output_folder, max_workers=10):
    """
    Tải tất cả ảnh từ file JSON sử dụng đa luồng
    """
    global success_count, fail_count, skip_count
    
    # Tạo folder nếu chưa tồn tại
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Đã tạo folder: {output_folder}")
    
    # Đọc file JSON
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        total_items = len(data)
        print(f"Đã đọc {total_items} sản phẩm từ file JSON")
    except Exception as e:
        print(f"Lỗi khi đọc file JSON: {e}")
        return
    
    print(f"Bắt đầu tải với {max_workers} luồng (threads)...\n")
    
    # Sử dụng ThreadPoolExecutor để tải song song
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, item in enumerate(data, 1):
            executor.submit(download_single_image, idx, item, output_folder, total_items)
    
    # Thống kê
    print("\n" + "="*60)
    print(f"HOÀN THÀNH!")
    print(f"Tổng số sản phẩm: {total_items}")
    print(f"Tải mới thành công: {success_count}")
    print(f"Bỏ qua (đã có): {skip_count}")
    print(f"Thất bại: {fail_count}")
    print(f"Ảnh được lưu tại: {os.path.abspath(output_folder)}")
    print("="*60)

if __name__ == "__main__":
    # Cấu hình
    json_file = "final_merged_all.json"
    output_folder = "images"
    num_threads = 20  # Bạn có thể tăng số này để tải nhanh hơn (vd: 20, 30)
    
    print("="*60)
    print("CHƯƠNG TRÌNH TẢI ẢNH ĐA LUỒNG")
    print("="*60)
    print(f"File JSON: {json_file}")
    print(f"Folder lưu ảnh: {output_folder}")
    print(f"Số luồng: {num_threads}")
    print("="*60 + "\n")
    
    start_time = time.time()
    download_images_parallel(json_file, output_folder, max_workers=num_threads)
    duration = time.time() - start_time
    print(f"Tổng thời gian thực hiện: {duration:.2f} giây")
