# utils/multimodal_ai.py
"""
多模态AI工具 - 简化版
只使用智谱GLM-4.7-Flash免费模型，已移除拍照功能
"""

import os
import json
import re
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MultimodalAI:
    """多模态AI批改器 - 简化版，只使用GLM-4.7-Flash免费模型"""
    
    # 智谱API配置
    ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    def __init__(self, api_key: str = None):
        """
        初始化多模态AI
        
        参数:
            api_key: 智谱AI API密钥，如果不提供则使用默认的
        """
        # 如果提供了api_key则使用，否则使用app.py中的默认密钥
        self.api_key = api_key or "2e0af7231fec40f5a667adfd536537a7.L4F0x6GD0QYRT4zS"
        
        # 使用免费的GLM-4.7-Flash模型
        self.model = "glm-4.7-flash"
        
        print(f"✅ 多模态AI初始化完成，使用免费模型 {self.model}")
    
    def _call_zhipu_api(self, messages, temperature=0.3, max_tokens=2000):
        """
        调用智谱GLM-4.7-Flash API的通用函数
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9
        }
        
        try:
            response = requests.post(self.ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'content': result['choices'][0]['message']['content'],
                    'model': result.get('model', self.model)
                }
            else:
                error_msg = f"API错误: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                logger.error(f"智谱API调用失败: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except requests.exceptions.Timeout:
            logger.error("智谱API请求超时")
            return {'success': False, 'error': '请求超时'}
        except Exception as e:
            logger.error(f"智谱API异常: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def grade_code_by_text(self, code: str, question: str = None, knowledge_point: str = None) -> Dict[str, Any]:
        """
        通过文本批改代码
        
        参数:
            code: 代码文本
            question: 题目描述（可选）
            knowledge_point: 知识点标签（可选）
            
        返回:
            批改结果字典
        """
        if not code:
            return self._fallback_grade("代码不能为空")
        
        try:
            # 构建提示词
            text_content = ""
            if question:
                text_content += f"【题目】\n{question}\n\n"
            
            if knowledge_point:
                text_content += f"【知识点】\n{knowledge_point}\n\n"
            
            text_content += f"【学生代码】\n```cpp\n{code}\n```\n\n"
            
            text_content += """请从以下维度进行批改：

1. 语法正确性（30分）：代码是否有语法错误
2. 逻辑完整性（30分）：代码逻辑是否完整正确
3. 代码规范（20分）：命名规范、代码格式、注释等
4. 知识点掌握（20分）：是否正确运用了要求的OOP知识点

请以JSON格式返回批改结果：
{
    "total_score": 总分,
    "dimensions": {
        "syntax": 语法分数,
        "logic": 逻辑分数,
        "standard": 规范分数,
        "knowledge": 知识点分数
    },
    "recognized_code": "识别出的代码文本（可直接复制原代码）",
    "feedback": "总体评语（50字以内）",
    "suggestions": ["建议1", "建议2", "建议3"]
}

注意：总分和维度分都应该是0-100之间的整数。"""
            
            # 调用API
            messages = [
                {"role": "system", "content": "你是一个专业的C++代码批改助手，擅长给出客观、详细的评分和建议。"},
                {"role": "user", "content": text_content}
            ]
            
            response = self._call_zhipu_api(messages, temperature=0.3, max_tokens=2048)
            
            if not response['success']:
                return self._fallback_grade(response.get('error', 'API调用失败'))
            
            content = response['content']
            
            # 尝试解析JSON
            try:
                # 提取JSON部分（防止有额外文本）
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    
                    # 确保有所有必要字段
                    result.setdefault('total_score', 70)
                    result.setdefault('dimensions', {
                        'syntax': 20,
                        'logic': 20,
                        'standard': 15,
                        'knowledge': 15
                    })
                    result.setdefault('recognized_code', code)
                    result.setdefault('feedback', '批改完成')
                    result.setdefault('suggestions', ['请仔细检查代码'])
                    
                    return result
                else:
                    return self._parse_text_response(content, code)
            except json.JSONDecodeError:
                return self._parse_text_response(content, code)
                
        except Exception as e:
            logger.error(f"代码批改失败: {str(e)}")
            return self._fallback_grade(str(e))
    
    def _parse_text_response(self, text: str, original_code: str) -> Dict[str, Any]:
        """解析非JSON格式的响应"""
        # 尝试提取分数
        score_match = re.search(r'(\d{1,3})分', text)
        total_score = int(score_match.group(1)) if score_match else 70
        
        # 尝试提取建议
        suggestions = []
        suggestion_lines = re.findall(r'[1-9][.、]\s*([^\n]+)', text)
        if suggestion_lines:
            suggestions = suggestion_lines[:3]
        else:
            suggestions = ["建议根据反馈修改代码"]
        
        return {
            "total_score": total_score,
            "dimensions": {
                "syntax": total_score // 3,
                "logic": total_score // 3,
                "standard": total_score // 4,
                "knowledge": total_score // 4
            },
            "recognized_code": original_code,
            "feedback": text[:100] if len(text) > 100 else text,
            "suggestions": suggestions
        }
    
    def _fallback_grade(self, reason: str) -> Dict[str, Any]:
        """降级评分"""
        return {
            "total_score": 60,
            "dimensions": {
                "syntax": 15,
                "logic": 15,
                "standard": 15,
                "knowledge": 15
            },
            "recognized_code": "",
            "feedback": f"AI批改服务暂时不可用（{reason}），使用基础评分",
            "suggestions": ["请稍后重试"]
        }
    
    def extract_code_from_text(self, text: str) -> str:
        """
        从文本中提取代码块
        
        参数:
            text: 包含代码的文本
            
        返回:
            提取出的代码文本
        """
        # 提取 markdown 代码块
        code_match = re.search(r'```(?:\w*)\n(.*?)```', text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # 如果没有代码块，返回原文本
        return text.strip()


# 创建全局实例，使用app.py中的默认API密钥
multimodal_ai = MultimodalAI()