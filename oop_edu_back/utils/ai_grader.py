# utils/ai_grader.py
import json
import re
import time
import requests
import logging
from typing import Dict, List, Any, Optional
from functools import lru_cache

# 配置日志
logger = logging.getLogger(__name__)

# 尝试导入zhipuai，如果失败则使用requests
try:
    from zhipuai import ZhipuAI
    ZHIPUAI_AVAILABLE = True
except ImportError:
    ZHIPUAI_AVAILABLE = False
    print("⚠️ zhipuai库未安装，将使用requests方式调用API")
    ZhipuAI = None

class AIGrader:
    """AI作业评分器 - 使用智谱免费大模型（GLM-4.7-Flash）"""
    
    # 智谱API配置
    ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    def __init__(self, api_key: str = None):
        """初始化智谱AI客户端
        
        Args:
            api_key: 智谱AI API密钥，如果不提供则使用默认的
        """
        self.api_key = api_key or "2e0af7231fec40f5a667adfd536537a7.L4F0x6GD0QYRT4zS"
        self.client = None
        
        # 如果zhipuai库可用，初始化客户端
        if ZHIPUAI_AVAILABLE and self.api_key:
            try:
                self.client = ZhipuAI(api_key=self.api_key)
                print("✅ [ai_grader] 使用zhipuai官方库初始化成功")
            except Exception as e:
                print(f"⚠️ [ai_grader] zhipuai官方库初始化失败: {e}，将使用requests方式")
                self.client = None
        
        # 使用最新的免费模型 - GLM-4.7-Flash（永久免费）
        self.model = "glm-4.7-flash"
        
        # 评分维度权重配置
        self.dimension_weights = {
            'correctness': 0.35,  # 正确性
            'completeness': 0.25,  # 完整性
            'efficiency': 0.20,    # 效率
            'style': 0.10,         # 代码风格
            'innovation': 0.10      # 创新性
        }
        
        # 缓存配置，避免重复评分
        self.cache = {}
        self.cache_timeout = 3600  # 缓存1小时
        
    def _call_zhipu_api(self, messages, temperature=0.3, max_tokens=2000):
        """
        调用智谱GLM-4.7-Flash API的通用函数
        兼容两种方式：zhipuai官方库 和 requests直接调用
        """
        # 如果zhipuai客户端可用，优先使用
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=0.9
                )
                return {
                    'success': True,
                    'content': response.choices[0].message.content,
                    'model': self.model
                }
            except Exception as e:
                logger.error(f"zhipuai官方库调用失败: {e}，尝试使用requests")
                # 失败后继续尝试requests方式
        
        # 使用requests方式调用
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
    
    def grade_homework(self, question: str, answer: str, knowledge_point: str) -> Dict[str, Any]:
        """作业评分 - 主入口方法
        
        Args:
            question: 题目内容
            answer: 学生答案
            knowledge_point: 知识点
            
        Returns:
            评分结果字典
        """
        # 生成缓存键
        cache_key = f"{hash(question)}_{hash(answer)}_{hash(knowledge_point)}"
        
        # 检查缓存
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                return cached_result
        
        # 尝试AI评分
        try:
            result = self._ai_comprehensive_grade(question, answer, knowledge_point)
        except Exception as e:
            logger.error(f"AI综合评分失败: {e}，降级使用规则评分")
            result = self._rule_based_grade(answer)
        
        # 更新缓存
        self.cache[cache_key] = (result, time.time())
        
        return result
    
    def _ai_comprehensive_grade(self, question: str, answer: str, knowledge_point: str) -> Dict[str, Any]:
        """AI综合评分 - 使用GLM-4.7-Flash进行智能评分"""
        
        # 构建评分提示词
        prompt = f"""你是一个专业的C++编程作业评分助手。请对以下学生作业进行综合评分。

【题目】
{question}

【知识点】
{knowledge_point}

【学生答案】
{answer}

请从以下维度进行评分（每项0-100分）：
1. 正确性：代码逻辑是否正确，能否正确解决问题
2. 完整性：代码是否完整，是否考虑了边界情况
3. 效率：算法效率如何，时间复杂度是否合理
4. 代码风格：命名规范、代码格式、注释等
5. 创新性：是否有独特的解决思路或优化

请按以下JSON格式返回评分结果：
{{
    "total_score": 85,
    "dimensions": {{
        "correctness": 90,
        "completeness": 85,
        "efficiency": 80,
        "style": 75,
        "innovation": 70
    }},
    "feedback": "总体评价...",
    "suggestions": ["建议1", "建议2", "建议3"],
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"]
}}

注意：
- 总分和维度分都应该是0-100之间的整数
- 反馈要具体、有建设性
- 建议要针对性强，便于改进
"""

        messages = [
            {"role": "system", "content": "你是一个专业的C++编程作业评分助手，擅长给出客观、详细的评分和建议。"},
            {"role": "user", "content": prompt}
        ]
        
        # 调用智谱API
        response = self._call_zhipu_api(messages, temperature=0.3, max_tokens=1000)
        
        if not response['success']:
            raise Exception(response.get('error', 'API调用失败'))
        
        # 解析返回结果
        result_text = response['content']
        
        # 提取JSON部分
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            
            # 计算加权总分（如果AI没有返回总分）
            if 'total_score' not in result:
                weighted_score = 0
                for dim, weight in self.dimension_weights.items():
                    if dim in result.get('dimensions', {}):
                        weighted_score += result['dimensions'][dim] * weight
                result['total_score'] = round(weighted_score)
            
            # 确保有所有必要字段
            result.setdefault('dimensions', {})
            result.setdefault('feedback', '')
            result.setdefault('suggestions', [])
            result.setdefault('strengths', [])
            result.setdefault('weaknesses', [])
            
            return result
        else:
            raise ValueError("无法从AI响应中解析JSON")
    
    def analyze_code_nlp(self, code: str) -> Dict[str, Any]:
        """NLP代码分析 - 使用GLM-4.7-Flash进行代码语义分析
        
        Args:
            code: 代码文本
            
        Returns:
            代码分析结果
        """
        prompt = f"""请对以下C++代码进行NLP语义分析，包括：
1. 代码意图：这段代码想解决什么问题
2. 复杂度分析：代码的时间复杂度和空间复杂度
3. 潜在问题：可能存在的bug或性能问题
4. 改进建议：如何优化这段代码
5. 关键变量：提取关键的变量名及其作用

代码：
```cpp
{code}

请以JSON格式返回分析结果：
{{
    "intent": "代码意图描述",
    "complexity": {{
        "time": "O(n)",
        "space": "O(1)",
        "explanation": "复杂度分析说明"
    }},
    "potential_issues": ["问题1", "问题2"],
    "improvements": ["改进1", "改进2"],
    "key_variables": {{
        "变量名": "变量作用"
    }}
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个代码分析专家，擅长理解代码意图和发现潜在问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._basic_code_analysis(code)
                
        except Exception as e:
            print(f"NLP代码分析失败: {e}")
            return self._basic_code_analysis(code)
    
    def generate_feedback(self, question: str, answer: str, score: int) -> str:
        """生成个性化反馈 - 使用GLM-4-Flash生成针对性评语
        
        Args:
            question: 题目
            answer: 答案
            score: 得分
            
        Returns:
            个性化反馈文本
        """
        if not self._ensure_client():
            return f"得分：{score}分。请继续努力！"
        
        prompt = f"""请根据以下作业信息，生成一段鼓励性、建设性的个性化反馈。

题目：{question}
学生答案：{answer}
得分：{score}

要求：
1. 语言亲切、鼓励性强
2. 针对得分情况给出具体建议
3. 指出优点和进步空间
4. 控制在100字以内

请直接返回反馈文本，不要加额外说明。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个亲切的编程老师，擅长给学生鼓励性的反馈。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"生成反馈失败: {e}")
            return f"得分：{score}分。你的代码有可取之处，继续加油！"
    
    def _enhanced_rule_grade(self, answer: str) -> Dict[str, Any]:
        """增强的规则评分（AI降级备用）"""
        score = 60
        suggestions = []
        strengths = []
        
        # 检查类定义
        if re.search(r'class\s+\w+', answer):
            score += 10
            strengths.append("正确使用了类定义")
        else:
            suggestions.append("建议使用面向对象思想，定义类")
        
        # 检查方法定义
        if re.search(r'def\s+\w+\s*\(', answer):
            score += 10
            strengths.append("方法定义清晰")
        elif re.search(r'public\s+\w+\s+\w+\s*\(', answer):
            score += 10
            strengths.append("方法定义符合Java规范")
        else:
            suggestions.append("建议定义方法组织代码")
        
        # 检查代码块完整性
        if '{' in answer and '}' in answer:
            if answer.count('{') == answer.count('}'):
                score += 5
                strengths.append("代码块结构完整")
            else:
                suggestions.append("检查大括号是否配对")
        else:
            suggestions.append("代码块需要完整")
        
        # 检查返回值
        if re.search(r'return', answer):
            score += 5
            strengths.append("正确处理了返回值")
        
        # 检查注释
        if re.search(r'#.*|//.*|/\*.*?\*/', answer, re.DOTALL):
            score += 5
            strengths.append("代码有注释，很好")
        else:
            suggestions.append("建议添加注释说明代码逻辑")
        
        # 检查命名规范
        if re.search(r'[a-z_][a-z0-9_]*', answer):
            score += 3
        else:
            suggestions.append("注意使用规范的命名方式")
        
        score = min(100, score)
        
        # 计算维度分
        return {
            'total_score': score,
            'dimensions': {
                'correctness': min(90, score),
                'completeness': min(85, score - 5),
                'efficiency': min(80, score - 10),
                'style': min(75, score - 15),
                'innovation': min(70, score - 20)
            },
            'feedback': f'评分完成，得分{score}分。{self._get_score_level(score)}',
            'suggestions': suggestions[:3],
            'strengths': strengths[:2],
            'weaknesses': suggestions[:2]
        }
    
    def _basic_code_analysis(self, code: str) -> Dict[str, Any]:
        """基础代码分析（NLP降级备用）"""
        lines = code.split('\n')
        imports = re.findall(r'^(?:import|from)\s+\S+', code, re.MULTILINE)
        functions = re.findall(r'def\s+(\w+)\s*\(', code)
        classes = re.findall(r'class\s+(\w+)', code)
        
        complexity = "O(1)" if len(lines) < 20 else "O(n)" if len(lines) < 50 else "O(n²)"
        
        return {
            'intent': "代码意图分析（基础版）",
            'complexity': {
                'time': complexity,
                'space': "O(1)" if len(imports) < 5 else "O(n)",
                'explanation': f"基于代码长度和结构的初步分析"
            },
            'potential_issues': ["需要更详细的分析"],
            'improvements': ["建议使用AI进行详细分析"],
            'key_variables': {func: "定义的函数" for func in functions[:3]}
        }
    
    def _get_score_level(self, score: int) -> str:
        """根据得分返回等级描述"""
        if score >= 90:
            return "优秀！代码质量很高"
        elif score >= 80:
            return "良好，还有提升空间"
        elif score >= 70:
            return "中等，需要继续努力"
        elif score >= 60:
            return "及格，但要加油"
        else:
            return "需要加强练习"
    
    def set_api_key(self, api_key: str):
        """设置API密钥"""
        self.api_key = api_key
        self.client = ZhipuAI(api_key=self.api_key)
    
    def clear_cache(self):
        """清除评分缓存"""
        self.cache.clear()

# 创建全局实例，API密钥需要在使用前设置
ai_grader = AIGrader()