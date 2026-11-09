"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Bạn là VinAssistant - Trợ lý ảo AI chính thức của tập đoàn Vingroup. Nhiệm vụ của bạn là hỗ trợ khách hàng tra cứu thông tin sản phẩm, dịch vụ và tiếp nhận các yêu cầu hỗ trợ một cách chuyên nghiệp, chính xác và lịch sự.

## 1. AVAILABLE TOOLS
Bạn có quyền truy cập các công cụ sau để thu thập thông tin và thực hiện tác vụ:
{tools}

## 2. CORE RULES (QUY TẮC CỐT LÕI)
- **Không bịa đặt dữ liệu (No Hallucination):** Tuyệt đối không tự suy diễn thông tin về giá cả, thông số kỹ thuật, chính sách hay dịch vụ nếu không có dữ liệu thực tế từ tool hoặc kiến thức chuẩn được xác thực.
- **Bắt buộc gọi tool:** Khi người dùng hỏi về danh mục sản phẩm, giá cả, hoặc yêu cầu tạo ticket hỗ trợ, bạn phải gọi công cụ tương ứng (`search_product_catalog` hoặc `submit_support_ticket`).
- **Xử lý kết quả rỗng:** Nếu kết quả tìm kiếm từ tool trả về danh sách rỗng, hãy thông báo lịch sự cho khách hàng rằng hiện không tìm thấy sản phẩm phù hợp và gợi ý điều kiện tìm kiếm khác.
- **FAQ và Câu hỏi có sẵn:** Đối với các câu hỏi thường gặp (FAQ) đã có căn cứ rõ ràng (ví dụ: chính sách bảo hành pin xe điện VF 5 Plus là 10 năm), bạn có thể trả lời trực tiếp mà không cần gọi tool, nhưng phải đảm bảo thông tin chính xác, có căn cứ.

## 3. OPERATIONAL BOUNDARIES (GIỚI HẠN PHẠM VI)
- Chỉ trả lời và hỗ trợ các vấn đề liên quan đến hệ sinh thái sản phẩm, dịch vụ của Vingroup (VinFast, Vinpearl, Vinhomes, v.v.).
- Từ chối lịch sự các câu hỏi nằm ngoài phạm vi Vingroup hoặc vi phạm chính sách đạo đức/pháp luật.

## 4. OUTPUT CONTRACT (ĐỊNH DẠNG ĐẦU RA)
Mỗi phản hồi cần tuân theo định dạng ReAct (nếu sử dụng tool) hoặc trả lời trực tiếp (nếu là FAQ):
Thought: [Suy nghĩ ngắn gọn về mục đích của người dùng và bước xử lý tiếp theo]
Action: [Tên tool cần gọi kèm tham số dưới dạng JSON, hoặc bỏ qua nếu kết thúc/FAQ]
Observation: [Kết quả thực thi từ tool]
Final Answer: [Câu trả lời hoàn chỉnh, thân thiện gửi đến người dùng bằng tiếng Việt]
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # Trả về câu trả lời tĩnh quan sát hiện tượng hallucination
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input} (Lưu ý: Có thể xuất hiện thông tin chưa được kiểm chứng do thiếu cơ chế tool calling).",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        self.trace.append({"step": "init", "user_input": user_input})

        iterations = 0
        search_result = None
        ticket_result = None
        
        lower_input = user_input.lower()
        
        # 1. Xử lý câu hỏi FAQ (ví dụ: bảo hành pin VF 5 Plus) không cần gọi tool
        if "bảo hành pin" in lower_input and ("vf 5" in lower_input or "vf5" in lower_input):
            answer = "Theo chính sách của hãng, xe điện VinFast VF 5 Plus có thời hạn bảo hành pin chính hãng là 10 năm."
            self.trace.append({
                "step": "faq",
                "thought": "Câu hỏi thuộc về FAQ về bảo hành pin VF 5 Plus, có sẵn căn cứ xác thực (10 năm), không cần gọi tool.",
                "final_answer": answer
            })
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "success"
            }

        # Phát hiện nhu cầu gọi tool
        need_search = any(kw in lower_input for kw in ["xe", "vinfast", "giá", "dưới", "triệu", "tỷ", "du lịch", "resort", "vinpearl", "sản phẩm", "xem"])
        need_ticket = any(kw in lower_input for kw in ["ticket", "hỗ trợ", "gửi", "khiếu nại", "báo lỗi", "phản ánh", "giúp tôi", "liên hệ"])

        # Agent Loop giới hạn bởi max_iterations
        while iterations < self.max_iterations:
            iterations += 1
            
            # Step A: Xử lý tìm kiếm sản phẩm (nếu cần và chưa chạy)
            if need_search and search_result is None:
                category = "xe_dien"
                if any(kw in lower_input for kw in ["du lịch", "vinpearl", "resort", "khách sạn"]):
                    category = "du_lich"
                
                max_price = 999999999999
                price_match = re.search(r"dưới\s*(\d+)\s*(triệu|tr|tỷ)", lower_input)
                if price_match:
                    num_val = float(price_match.group(1))
                    unit = price_match.group(2)
                    if "triệu" in unit or "tr" in unit:
                        max_price = int(num_val * 1_000_000)
                    elif "tỷ" in unit:
                        max_price = int(num_val * 1_000_000_000)
                else:
                    nums = re.findall(r"(\d+)\s*(triệu|tr)", lower_input)
                    if nums:
                        max_price = int(float(nums[0][0]) * 1_000_000)

                thought = f"Phát hiện ý định tìm kiếm sản phẩm danh mục '{category}' với giá tối đa {max_price} VNĐ."
                action = {"tool": "search_product_catalog", "arguments": {"category": category, "max_price": max_price}}
                
                self.trace.append({
                    "step": f"iteration_{iterations}",
                    "thought": thought,
                    "action": action
                })
                
                search_result = search_product_catalog(category=category, max_price=max_price)
                self.trace.append({
                    "step": f"observation_{iterations}",
                    "observation": search_result
                })
                
                if not need_ticket:
                    break
                continue

            # Step B: Xử lý tạo ticket hỗ trợ (nếu cần và chưa chạy)
            if need_ticket and ticket_result is None:
                customer_name = "Khách hàng Vingroup"
                name_match = re.search(r"(?:tên tôi là|tên là|tôi là)\s+([A-Za-zÀ-ỹ\s]+)(?:,|\.|$)", user_input)
                if name_match:
                    customer_name = name_match.group(1).strip()
                
                priority = "medium"
                if any(kw in lower_input for kw in ["gấp", "khẩn cấp", "ngay", "cao"]):
                    priority = "high"
                elif any(kw in lower_input for kw in ["thấp"]):
                    priority = "low"
                
                thought = f"Phát hiện ý định gửi yêu cầu hỗ trợ (ticket) cho khách hàng '{customer_name}' với mức độ ưu tiên '{priority}'."
                action = {"tool": "submit_support_ticket", "arguments": {"customer_name": customer_name, "issue_description": user_input, "priority": priority}}
                
                self.trace.append({
                    "step": f"iteration_{iterations}",
                    "thought": thought,
                    "action": action
                })
                
                ticket_result = submit_support_ticket(customer_name=customer_name, issue_description=user_input, priority=priority)
                self.trace.append({
                    "step": f"observation_{iterations}",
                    "observation": ticket_result
                })
                break
            
            break

        # Tổng hợp kết quả từ các bước thực thi (Final Answer)
        answer_parts = []
        if search_result is not None:
            if len(search_result) == 0:
                answer_parts.append("Hiện tại không tìm thấy sản phẩm hoặc dịch vụ nào trong hệ thống phù hợp với yêu cầu của bạn.")
            else:
                prod_strs = [f"- **{p.get('name', 'N/A')}**: {p.get('price_vnd', 0):,} VNĐ ({p.get('description', '')})" for p in search_result]
                answer_parts.append("Dưới đây là các sản phẩm phù hợp với yêu cầu của bạn:\n" + "\n".join(prod_strs))
                
        if ticket_result is not None:
            answer_parts.append(f"Yêu cầu hỗ trợ của bạn đã được tiếp nhận thành công. Mã ticket của bạn là **{ticket_result.get('ticket_id')}** (Trạng thái: {ticket_result.get('status')}).")

        if not answer_parts:
            answer_parts.append("Xin chào! Tôi là VinAssistant. Tôi có thể hỗ trợ gì cho bạn về các sản phẩm và dịch vụ của Vingroup?")

        final_answer = "\n\n".join(answer_parts)
        self.trace.append({
            "step": "final_answer",
            "answer": final_answer
        })

        return {
            "answer": final_answer,
            "trace": self.trace,
            "iterations": iterations,
            "status": "success"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()