from yuxi.agents.buildin.chatbot.prompt import SystemPromptBuilder


def test_chatbot_prompt_contains_html_preview_guidance_exactly_once():
    """Fork này nhúng hướng dẫn html:preview trực tiếp trong system prompt (không phụ thuộc skill),
    nên khối hướng dẫn chỉ được xuất hiện đúng một lần để tránh trùng lặp chỉ thị."""
    prompt = SystemPromptBuilder().build("/virtual", "/outputs", "/uploads", "/workspace")
    # 3 lần: tiêu đề thành phần trực quan hóa + cú pháp fence + cảnh báo dùng khối thường
    assert prompt.count("html:preview") == 3
