import requests
import json

def test_deepseek_api():
    api_key = "Bearer sk-wsbrvlxdkmcwiddmisdabinvqtfvwlgzhptojzbjusarltls"
    api_url = "https://api.siliconflow.cn/v1/chat/completions"
    model_name = "Pro/deepseek-ai/DeepSeek-R1"
    
    # 测试文本
    test_text = """这是一个测试文本。
    张三说："你好，李四！"
    李四回答："你好啊，张三！"
    旁白：两人相视一笑。
    """
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一个专业的小说对话分割助手，请将小说文本分割成对话和旁白。"},
            {"role": "user", "content": f"请将以下小说文本分割成对话和旁白。对于每个部分，请标明说话者（旁白或具体角色）。\n\n小说文本：\n{test_text}"}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        print("API响应：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"API调用出错: {str(e)}")

if __name__ == "__main__":
    test_deepseek_api() 