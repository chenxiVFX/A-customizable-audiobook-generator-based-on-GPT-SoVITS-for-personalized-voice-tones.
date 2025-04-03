import os
from typing import List, Dict, Tuple
from pydub import AudioSegment
from dotenv import load_dotenv
import json
import requests
import re
import time

class NovelToAudio:
    def __init__(self):
        load_dotenv()
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.api_key = "sk-xxx"
        self.model_name = "gpt-3.5-turbo"
        self.chat_api_url = "https://api.openai.com/v1/chat/completions"  # 对话模型API地址
        self.chat_api_key = "sk-xxx"  # 对话模型API密钥
        self.chat_model_name = "gpt-3.5-turbo"  # 对话模型名称
        self.voice_data = {}
        self.narration_enabled = True
        self.temp_dir = "分段合成临时文件"  # 临时文件夹名称
        self.chat_history = []  # 添加对话历史记录
        
        # 创建临时文件夹
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        
        self.load_config()
        
        # 初始化headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def load_config(self):
        """加载配置"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.api_url = config.get('api_url', self.api_url)
                self.api_key = config.get('api_key', self.api_key)
                self.model_name = config.get('model_name', self.model_name)
                self.chat_api_url = config.get('chat_api_url', self.chat_api_url)
                self.chat_api_key = config.get('chat_api_key', self.chat_api_key)
                self.chat_model_name = config.get('chat_model_name', self.chat_model_name)
                
                # 更新headers
                self.headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
    
    def update_config(self, api_url, api_key, model_name, chat_api_url, chat_api_key, chat_model_name):
        """更新配置"""
        try:
            config = {
                'api_url': api_url,
                'api_key': api_key,
                'model_name': model_name,
                'chat_api_url': chat_api_url,
                'chat_api_key': chat_api_key,
                'chat_model_name': chat_model_name
            }
            
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            self.api_url = api_url
            self.api_key = api_key
            self.model_name = model_name
            self.chat_api_url = chat_api_url
            self.chat_api_key = chat_api_key
            self.chat_model_name = chat_model_name
            
            # 更新headers
            self.headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            return True
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
            return False
    
    def set_narration(self, enable: bool):
        """设置是否启用旁白"""
        self.narration_enabled = enable
    
    def split_dialogue(self, text, callback=None):
        """分割对话，并实时显示AI的回复"""
        # 根据是否启用旁白选择不同的系统提示词
        if self.narration_enabled:
            system_prompt = """你是一个专业的小说对话分割助手。请将输入的小说文本分割成对话和旁白片段。
要求：
1. 对话部分：
   - 只包含实际的对话内容（引号内的内容）
   - 去掉所有引号
   - 不包含说话前的动作描述
   - 不包含说话后的动作描述
   - 不包含省略号等非对话内容
2. 旁白部分：
   - 包含所有非对话内容
   - 每个动作描述或场景描写应该作为独立的旁白片段
   - 包括说话前的动作描述（如"张三突然开口问道"）
   - 包括说话后的动作描述（如"李四放下手中的书"）
   - 包括场景描写、心理描写等
3. 输出格式：JSON数组，每个元素包含：
   - role: 说话角色（对话部分）或"旁白"（非对话部分）
   - text: 具体内容"""
        else:
            system_prompt = """你是一个专业的小说对话分割助手。请将输入的小说文本分割成对话片段。
要求：
1. 只提取对话内容：
   - 只包含实际的对话内容（引号内的内容）
   - 去掉所有引号
   - 不包含说话前的动作描述
   - 不包含说话后的动作描述
   - 不包含省略号等非对话内容
   - 不包含任何旁白内容
2. 输出格式：JSON数组，每个元素包含：
   - role: 说话角色
   - text: 对话内容
3. 请确保JSON格式正确，不要将字段分割成多行。
4. 请保留所有对话内容，不要遗漏任何部分。
5. 直接输出JSON数组，不要添加任何Markdown标记。
6. 对话内容中的引号应该去掉，不要使用转义引号。
7. 请严格按照引号来区分对话，引号内的内容为对话。
8. 对话内容中不要包含任何引号，包括转义引号。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        data = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        dialogues = []
        accumulated_content = ""
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=data,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"API调用失败: {response.status_code} - {response.text}"
                print(error_msg)
                if callback:
                    callback(error_msg)
                return []
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        line = line[6:]  # 移除 'data: ' 前缀
                        if line == '[DONE]':
                            break
                        
                        try:
                            chunk = json.loads(line)
                            if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                content = chunk['choices'][0]['delta']['content']
                                # 实时显示AI的回复
                                if callback:
                                    callback(content)
                                
                                # 累积内容
                                accumulated_content += content
                        except json.JSONDecodeError:
                            continue
            
            # 处理累积的内容
            if accumulated_content.strip():
                try:
                    # 清理JSON字符串
                    cleaned_content = accumulated_content.strip()
                    # 移除Markdown代码块标记
                    cleaned_content = re.sub(r'```json\s*', '', cleaned_content)
                    cleaned_content = re.sub(r'\s*```', '', cleaned_content)
                    # 移除多余的换行和空格
                    cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
                    # 修复可能的格式问题
                    cleaned_content = cleaned_content.replace('}\n{', '},{')
                    cleaned_content = cleaned_content.replace(']\n[', '],[')
                    
                    # 尝试解析JSON
                    dialogues = json.loads(cleaned_content)
                    
                    # 显示解析后的对话内容
                    if callback:
                        callback("\n解析后的对话内容：")
                        for dialogue in dialogues:
                            callback(f"{dialogue['role']}: {dialogue['text']}")
                except json.JSONDecodeError as e:
                    error_msg = f"JSON解析错误: {str(e)}\n原始内容: {accumulated_content}"
                    print(error_msg)
                    if callback:
                        callback(error_msg)
                    return []
            
            return dialogues
            
        except Exception as e:
            error_msg = f"Error in split_dialogue: {str(e)}"
            print(error_msg)
            if callback:
                callback(error_msg)
            return []
    
    def text_to_speech(self, text: str, role: str) -> str:
        """
        使用GPTSoVits将文本转换为语音
        返回音频文件路径
        """
        try:
            import requests
            
            # 获取角色的音色设置
            voice_settings = self.voice_data.get(role, {})
            if not voice_settings:
                raise ValueError(f"未找到角色 {role} 的音色设置")
            
            # 设置GPT模型
            response = requests.get(
                "http://127.0.0.1:9880/set_gpt_weights",
                params={"weights_path": voice_settings['gpt_path']}
            )
            if response.status_code != 200:
                raise Exception(f"设置GPT模型失败: {response.text}")
            
            # 设置Sovits模型
            response = requests.get(
                "http://127.0.0.1:9880/set_sovits_weights",
                params={"weights_path": voice_settings['sovits_path']}
            )
            if response.status_code != 200:
                raise Exception(f"设置Sovits模型失败: {response.text}")
            
            # 准备请求参数
            request_data = {
                "text": text,
                "text_lang": "zh",
                "ref_audio_path": voice_settings['ref_audio_path'],
                "prompt_text": voice_settings['ref_text'],
                "prompt_lang": "zh",
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": False,
                # 添加高级参数
                "speed_factor": voice_settings.get('speed_factor', 1.0),
                "top_k": voice_settings.get('top_k', 5),
                "top_p": voice_settings.get('top_p', 1.0),
                "temperature": voice_settings.get('temperature', 1.0),
                "repetition_penalty": voice_settings.get('repetition_penalty', 1.35)
            }
            
            # 发送合成请求
            response = requests.post(
                "http://127.0.0.1:9880/tts",
                json=request_data
            )
            
            if response.status_code != 200:
                raise Exception(f"合成失败: {response.text}")
            
            # 保存音频文件到临时文件夹
            output_path = os.path.join(self.temp_dir, f"temp_{role}_{int(time.time())}.wav")
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return output_path
            
        except Exception as e:
            print(f"语音合成错误: {str(e)}")
            # 返回一个空的音频文件
            output_path = os.path.join(self.temp_dir, f"temp_{role}_{int(time.time())}.wav")
            with open(output_path, "wb") as f:
                f.write(b"")  # 写入空数据
            return output_path
    
    def merge_audio(self, audio_files: List[str], output_path: str):
        """
        合并多个音频文件
        """
        if not audio_files:
            return
            
        combined = AudioSegment.empty()
        for audio_file in audio_files:
            if os.path.exists(audio_file):
                audio = AudioSegment.from_wav(audio_file)
                combined += audio
                # 添加短暂停顿
                combined += AudioSegment.silent(duration=500)
                
        combined.export(output_path, format="wav")
        
        # 清理临时文件夹中的所有文件
        try:
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except Exception as e:
            print(f"清理临时文件失败: {str(e)}")
    
    def process_novel(self, novel_path: str, output_path: str, callback=None):
        """
        处理完整的小说文件
        """
        try:
            # 读取小说文本
            with open(novel_path, 'r', encoding='utf-8') as f:
                novel_text = f.read()
            
            # 分割对话
            dialogues = self.split_dialogue(novel_text, callback)
            if not dialogues:
                raise Exception("对话分割失败")
            
            # 保存分割结果供检查
            with open('dialogue_split.json', 'w', encoding='utf-8') as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            
            # 生成音频文件
            audio_files = []
            total_dialogues = len(dialogues)
            
            for i, dialogue in enumerate(dialogues, 1):
                if callback:
                    callback(f"正在生成第 {i}/{total_dialogues} 段音频 ({dialogue['role']})...")
                
                audio_path = self.text_to_speech(dialogue['text'], dialogue['role'])
                if audio_path:
                    audio_files.append(audio_path)
                
                # 更新进度
                if callback:
                    progress = int((i / total_dialogues) * 100)
                    callback(f"进度: {progress}%")
            
            if not audio_files:
                raise Exception("没有成功生成任何音频文件")
            
            # 合并音频
            if callback:
                callback("正在合并音频文件...")
            self.merge_audio(audio_files, output_path)
            
            if callback:
                callback("音频生成完成！")
            
            return True, "音频生成成功"
            
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            if callback:
                callback(error_msg)
            return False, error_msg

    def chat_with_ai(self, message, token_callback=None):
        """与AI进行对话"""
        try:
            # 添加用户消息到历史记录
            self.chat_history.append({"role": "user", "content": message})
            
            # 构建请求数据
            data = {
                "model": self.chat_model_name,
                "messages": self.chat_history,  # 使用完整的对话历史
                "stream": True
            }
            
            # 发送请求
            response = requests.post(
                self.chat_api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.chat_api_key}"
                },
                json=data,
                stream=True
            )
            
            if response.status_code != 200:
                raise Exception(f"API请求失败: {response.text}")
            
            # 处理流式响应
            buffer = ""
            last_send_time = time.time()
            
            for line in response.iter_lines():
                if line:
                    try:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            line = line[6:]
                            if line == '[DONE]':
                                break
                            try:
                                chunk = json.loads(line)
                                if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                                    token = chunk['choices'][0]['delta']['content']
                                    buffer += token
                                    
                                    # 在以下情况下发送缓冲区内容：
                                    # 1. 缓冲区达到一定大小
                                    # 2. 遇到标点符号
                                    # 3. 遇到换行符
                                    # 4. 距离上次发送超过一定时间
                                    current_time = time.time()
                                    if (len(buffer) >= 50 or  # 缓冲区大小限制
                                        token in '。！？.!?。' or  # 标点符号
                                        token == '\n' or  # 换行符
                                        current_time - last_send_time >= 0.2):  # 时间间隔
                                        if token_callback:
                                            token_callback(buffer)
                                        buffer = ""
                                        last_send_time = current_time
                            except json.JSONDecodeError:
                                continue
                    except UnicodeDecodeError:
                        continue
            
            # 发送剩余的缓冲区内容
            if buffer and token_callback:
                token_callback(buffer)
            
            # 获取完整响应
            response_text = "".join(chunk['choices'][0]['delta'].get('content', '') 
                                  for chunk in response.iter_lines() 
                                  if chunk and chunk.decode('utf-8').startswith('data: ') 
                                  and chunk.decode('utf-8')[6:] != '[DONE]')
            
            # 添加AI回复到历史记录
            self.chat_history.append({"role": "assistant", "content": response_text})
            
            return response_text
            
        except Exception as e:
            print(f"AI对话出错: {str(e)}")
            raise
    
    def clear_chat_history(self):
        """清空对话历史"""
        self.chat_history = []

if __name__ == "__main__":
    processor = NovelToAudio()
    processor.process_novel("test_novel.txt", "output_audio.wav") 