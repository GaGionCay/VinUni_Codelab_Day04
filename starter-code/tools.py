import json
import os
from typing import List, Dict, Any
from datetime import datetime

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")

# ---------------------------------------------------------------------------
# Tool #1: search_product_catalog
# Đã hoàn thiện: Đọc file product_catalog.json, lọc theo category và max_price.
# ---------------------------------------------------------------------------

def search_product_catalog(category: str, max_price: int = 999999999999) -> List[Dict[str, Any]]:
    """
    Tra cứu sản phẩm/dịch vụ Vingroup theo danh mục và giá tối đa.
    
    Args:
        category: Loại sản phẩm ('xe_dien' hoặc 'du_lich').
        max_price: Giá tối đa (VNĐ). Mặc định không giới hạn.
    
    Returns:
        Danh sách sản phẩm phù hợp điều kiện.
    """
    catalog_file = os.path.join(RAW_DATA_DIR, "product_catalog.json")
    if not os.path.exists(catalog_file):
        return []
    
    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    except Exception:
        return []
    
    results = []
    for p in catalog:
        if p.get("category") == category and p.get("price_vnd", 0) <= max_price:
            results.append(p)
            
    return results


# ---------------------------------------------------------------------------
# Tool #2: submit_support_ticket
# Đã hoàn thiện: Tạo ticket mới, tăng mã thứ tự, lưu vào support_tickets.json và trả về kết quả.
# ---------------------------------------------------------------------------

def submit_support_ticket(
    customer_name: str,
    issue_description: str,
    priority: str = "medium"
) -> Dict[str, Any]:
    """
    Ghi nhận yêu cầu hỗ trợ của khách hàng vào hệ thống ticket.
    
    Args:
        customer_name: Tên khách hàng.
        issue_description: Mô tả vấn đề cần hỗ trợ.
        priority: Mức độ ưu tiên ('low', 'medium', 'high'). Mặc định 'medium'.
    
    Returns:
        Thông tin ticket vừa tạo bao gồm ticket_id, status.
    """
    tickets_file = os.path.join(RAW_DATA_DIR, "support_tickets.json")
    
    tickets = []
    if os.path.exists(tickets_file):
        try:
            with open(tickets_file, "r", encoding="utf-8") as f:
                tickets = json.load(f)
        except Exception:
            tickets = []
            
    today = datetime.now().strftime("%Y%m%d")
    today_prefix = f"TK-{today}-"
    seq = 1
    
    for t in tickets:
        tid = t.get("ticket_id", "")
        if tid.startswith(today_prefix):
            try:
                part = int(tid.split("-")[-1])
                if part >= seq:
                    seq = part + 1
            except ValueError:
                pass
                
    ticket_id = f"TK-{today}-{seq:03d}"
    
    new_ticket = {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now().isoformat()
    }
    
    tickets.append(new_ticket)
    
    os.makedirs(os.path.dirname(tickets_file), exist_ok=True)
    try:
        with open(tickets_file, "w", encoding="utf-8") as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
        
    return new_ticket


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS — JSON Schemas mô tả cho LLM
# Đã hoàn thiện: Khai báo JSON Schema đầy đủ (type, description, enum, required).
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_product_catalog",
        "description": "Tra cứu danh mục sản phẩm hoặc dịch vụ của Vingroup dựa theo loại danh mục và mức giá tối đa.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Loại danh mục sản phẩm/dịch vụ cần tra cứu.",
                    "enum": ["xe_dien", "du_lich"]
                },
                "max_price": {
                    "type": "integer",
                    "description": "Mức giá tối đa (tính bằng VNĐ) cho phép."
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "submit_support_ticket",
        "description": "Tạo và ghi nhận một yêu cầu hỗ trợ mới từ khách hàng vào hệ thống ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Họ và tên của khách hàng gửi yêu cầu hỗ trợ."
                },
                "issue_description": {
                    "type": "string",
                    "description": "Mô tả chi tiết vấn đề hoặc yêu cầu cần được hỗ trợ."
                },
                "priority": {
                    "type": "string",
                    "description": "Mức độ ưu tiên của ticket hỗ trợ.",
                    "enum": ["low", "medium", "high"],
                    "default": "medium"
                }
            },
            "required": ["customer_name", "issue_description"]
        }
    }
]


# ---------------------------------------------------------------------------
# TOOL_MAP — Ánh xạ tên tool → hàm thực thi
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "search_product_catalog": search_product_catalog,
    "submit_support_ticket": submit_support_ticket
}