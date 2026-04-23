"""
Hệ thống tìm kiếm sản phẩm bằng hình ảnh sử dụng CLIP
"""
import os
import json
import numpy as np
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
import pickle
import requests
from io import BytesIO
from pathlib import Path

class ImageSearchCLIP:
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        """
        Khởi tạo model CLIP
        """
        print("Đang tải CLIP model...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Sử dụng device: {self.device}")
        
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        
        self.embeddings = None
        self.image_paths = []
        self.products = []
        
        print("✓ CLIP model đã sẵn sàng!")
    
    def create_embeddings(self, images_folder, json_file, save_path="clip_embeddings.pkl"):
        """
        Tạo embeddings cho tất cả ảnh trong folder
        
        Args:
            images_folder: Folder chứa ảnh
            json_file: File JSON chứa thông tin sản phẩm
            save_path: Đường dẫn lưu embeddings
        """
        print(f"\n{'='*60}")
        print("BẮT ĐẦU TẠO EMBEDDINGS")
        print(f"{'='*60}")
        
        # Đọc thông tin sản phẩm
        with open(json_file, 'r', encoding='utf-8') as f:
            self.products = json.load(f)
        print(f"✓ Đã đọc {len(self.products)} sản phẩm từ JSON")
        
        # Lấy danh sách ảnh
        image_files = sorted([f for f in os.listdir(images_folder) 
                            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
        
        print(f"✓ Tìm thấy {len(image_files)} ảnh trong folder")
        
        embeddings_list = []
        
        for idx, img_file in enumerate(image_files, 1):
            img_path = os.path.join(images_folder, img_file)
            
            try:
                # Load và xử lý ảnh
                image = Image.open(img_path).convert('RGB')
                
                # Tạo embedding
                inputs = self.processor(images=image, return_tensors="pt").to(self.device)
                
                with torch.no_grad():
                    image_features = self.model.get_image_features(**inputs)
                    # Normalize
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                embeddings_list.append(image_features.cpu().numpy())
                self.image_paths.append(img_path)
                
                print(f"[{idx}/{len(image_files)}] ✓ {img_file}")
                
            except Exception as e:
                print(f"[{idx}/{len(image_files)}] ✗ Lỗi với {img_file}: {e}")
        
        # Chuyển thành numpy array
        self.embeddings = np.vstack(embeddings_list)
        
        # Lưu embeddings
        data = {
            'embeddings': self.embeddings,
            'image_paths': self.image_paths,
            'products': self.products[:len(self.image_paths)]  # Đảm bảo khớp số lượng
        }
        
        with open(save_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n{'='*60}")
        print(f"HOÀN THÀNH!")
        print(f"✓ Đã tạo {len(embeddings_list)} embeddings")
        print(f"✓ Đã lưu vào: {save_path}")
        print(f"{'='*60}\n")
        
        return self.embeddings
    
    def create_embeddings_from_json(self, json_file, save_path="clip_embeddings.pkl", max_items=None):
        """
        Tạo embeddings trực tiếp từ URL ảnh trong file JSON (không cần download về disk)
        
        Args:
            json_file: File JSON chứa thông tin sản phẩm (phải có trường 'image')
            save_path: Đường dẫn lưu embeddings
            max_items: Số lượng sản phẩm tối đa (None = tất cả)
        """
        print(f"\n{'='*60}")
        print("BẪT ĐẦU TẠO CLIP EMBEDDINGS TỪ URL ẢNH")
        print(f"{'='*60}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # Lọc chỉ sản phẩm có ảnh
        products_with_img = [p for p in products if p.get('image')]
        if max_items:
            products_with_img = products_with_img[:max_items]
        
        print(f"✓ Tổng: {len(products)} sản phẩm, có ảnh: {len(products_with_img)}")
        
        embeddings_list = []
        valid_products = []
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for idx, product in enumerate(products_with_img, 1):
            img_url = product.get('image', '')
            try:
                resp = requests.get(img_url, timeout=10, headers=headers)
                resp.raise_for_status()
                image = Image.open(BytesIO(resp.content)).convert('RGB')
                
                inputs = self.processor(images=image, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    image_features = self.model.get_image_features(**inputs)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                embeddings_list.append(image_features.cpu().numpy())
                valid_products.append(product)
                
                if idx % 50 == 0 or idx == len(products_with_img):
                    print(f"  [{idx}/{len(products_with_img)}] ✓ Đã xử lý {idx} ảnh...")
                    
            except Exception as e:
                if idx <= 10 or idx % 100 == 0:  # Chỉ log lỗi đầu và mỗi 100
                    print(f"  [{idx}] ✗ Bỏ qua: {img_url[:60]}... | Lỗi: {e}")
        
        if not embeddings_list:
            print("❌ Không tạo được embedding nào!")
            return None
        
        self.embeddings = np.vstack(embeddings_list)
        self.products = valid_products
        self.image_paths = [p.get('image', '') for p in valid_products]  # Lưu URL thay vì path
        
        data = {
            'embeddings': self.embeddings,
            'image_paths': self.image_paths,
            'products': self.products
        }
        with open(save_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n{'='*60}")
        print(f"✅ HOÀN THÀNH! Đã tạo {len(embeddings_list)} CLIP embeddings")
        print(f"✓ Đã lưu vào: {save_path}")
        print(f"{'='*60}\n")
        
        return self.embeddings
    
    def load_embeddings(self, embeddings_path="clip_embeddings.pkl"):
        """
        Load embeddings đã lưu
        """
        print(f"Đang load embeddings từ {embeddings_path}...")
        
        with open(embeddings_path, 'rb') as f:
            data = pickle.load(f)
        
        self.embeddings = data['embeddings']
        self.image_paths = data['image_paths']
        self.products = data['products']
        
        print(f"✓ Đã load {len(self.embeddings)} embeddings")
        return True
    
    def search_by_image(self, query_image_path, top_k=5):
        """
        Tìm kiếm sản phẩm tương tự bằng đường dẫn ảnh
        """
        query_image = Image.open(query_image_path).convert('RGB')
        return self.search_by_image_memory(query_image, top_k)

    def search_by_image_memory(self, query_image, top_k=5):
        """
        Tìm kiếm sản phẩm tương tự bằng đối tượng PIL Image (Trong bộ nhớ)
        
        Args:
            query_image: Đối tượng PIL Image
            top_k: Số kết quả trả về
        
        Returns:
            List các sản phẩm tương tự nhất
        """
        if self.embeddings is None:
            raise ValueError("Chưa có embeddings! Hãy tạo hoặc load embeddings trước.")
        
        # Tạo embedding cho ảnh query
        inputs = self.processor(images=query_image, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            query_features = self.model.get_image_features(**inputs)
            query_features = query_features / query_features.norm(dim=-1, keepdim=True)
        
        query_features = query_features.cpu().numpy()
        
        # Tính cosine similarity
        similarities = np.dot(self.embeddings, query_features.T).squeeze()
        
        # Lấy top_k kết quả
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            result = {
                'product': self.products[idx],
                'image_path': self.image_paths[idx],
                'similarity': float(similarities[idx])
            }
            results.append(result)
        
        return results


def main():
    """
    Hàm chính để tạo CLIP embeddings từ final_merged_all.json
    """
    import argparse
    parser = argparse.ArgumentParser(description='Tạo CLIP embeddings cho tìm kiếm ảnh')
    parser.add_argument('--json', default='final_merged_all.json', help='File JSON chứa dữ liệu sản phẩm')
    parser.add_argument('--output', default='clip_embeddings.pkl', help='File đầu ra embeddings')
    parser.add_argument('--max', type=int, default=None, help='Số sản phẩm tối đa (mặc định: tất cả)')
    parser.add_argument('--folder', default=None, help='Dùng folder ảnh có sẵn thay vì download từ URL')
    args = parser.parse_args()
    
    searcher = ImageSearchCLIP()
    
    if args.folder and os.path.isdir(args.folder):
        # Chế độ cũ: dùng folder ảnh local
        print(f"Ảnh từ folder: {args.folder}")
        searcher.create_embeddings(
            images_folder=args.folder,
            json_file=args.json,
            save_path=args.output
        )
    else:
        # Chế độ mới: download ảnh từ URL trong JSON
        print(f"Dữ liệu: {args.json} | Output: {args.output}")
        if args.max:
            print(f"Giới hạn: {args.max} sản phẩm")
        searcher.create_embeddings_from_json(
            json_file=args.json,
            save_path=args.output,
            max_items=args.max
        )
    
    print("\nBạn có thể chạy API server: python api_image_search.py")


if __name__ == "__main__":
    main()
