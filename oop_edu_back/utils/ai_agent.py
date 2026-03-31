
"""
智能体模块 - 提供AI问答、代码纠正、问题解析等功能
支持学生端和教师端的不同角色智能体，使用智谱GLM-4.7-Flash免费模型
"""
import json
import re
import requests
import logging
import random
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

class AIAgent:
    """智能体基类 - 使用智谱免费大模型（GLM-4.7-Flash）"""
    
    # 智谱API配置
    ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    def __init__(self, role: str, name: str, api_key: str = None):
        """
        初始化智能体
        
        参数:
            role: 角色 ('student' 或 'teacher')
            name: 智能体名称
            api_key: 智谱API密钥，如果不提供则使用默认的
        """
        self.role = role
        self.name = name
        self.api_key = api_key or "2e0af7231fec40f5a667adfd536537a7.L4F0x6GD0QYRT4zS"
        self.model = "glm-4.7-flash"  # 使用最新的免费模型
        
        self.conversation_history = []
        self.max_history = 50
        self.user_profile = {}  # 用户画像
        self.knowledge_score = {}  # 知识点掌握度
        
    def _call_zhipu_api(self, messages, temperature=0.7, max_tokens=2000):
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
    
    def add_to_history(self, question: str, answer: str, category: str = 'general', metadata: Dict = None):
        """
        添加对话到历史记录
        
        参数:
            question: 用户问题
            answer: 智能体回答
            category: 对话类别
            metadata: 元数据（如代码、错误信息等）
        """
        self.conversation_history.append({
            'question': question,
            'answer': answer,
            'category': category,
            'time': self._get_current_time(),
            'metadata': metadata or {}
        })
        
        # 限制历史记录长度
        if len(self.conversation_history) > self.max_history:
            # 保留最近的对话和标记为重要的对话
            important = [h for h in self.conversation_history if h.get('metadata', {}).get('important', False)]
            recent = self.conversation_history[-30:]
            self.conversation_history = important + recent
            # 去重
            seen = set()
            unique_history = []
            for h in self.conversation_history:
                key = f"{h['time']}_{h['question'][:50]}"
                if key not in seen:
                    seen.add(key)
                    unique_history.append(h)
            self.conversation_history = unique_history
    
    def get_history(self, limit: int = 20, category: str = None) -> List[Dict]:
        """获取对话历史"""
        history = self.conversation_history
        if category:
            history = [h for h in history if h['category'] == category]
        return history[-limit:]
    
    def clear_history(self, keep_important: bool = True):
        """清空对话历史"""
        if keep_important:
            self.conversation_history = [h for h in self.conversation_history 
                                        if h.get('metadata', {}).get('important', False)]
        else:
            self.conversation_history = []
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def analyze_intent(self, question: str) -> Dict:
        """
        深度分析用户意图
        
        参数:
            question: 用户问题
            
        返回:
            {
                'type': 意图类型,
                'subtype': 子类型,
                'confidence': 置信度,
                'keywords': 关键词列表,
                'entities': 识别出的实体
            }
        """
        question_lower = question.lower()
        
        # 意图分类器
        intent_patterns = {
            'definition': {
                'keywords': ['什么是', '什么叫', '解释', '定义', 'meaning', 'what is', 'explain', 'describe', '概念'],
                'weight': 1.0
            },
            'code_generation': {
                'keywords': ['写代码', '实现', '怎么写', '如何写', '代码示例', 'example code', 'how to code', 'demo', '例子'],
                'weight': 1.2
            },
            'code_check': {
                'keywords': ['检查代码', '代码有问题', '帮我看看', 'check code', 'review', 'debug', '调试', '哪里错了'],
                'weight': 1.3
            },
            'error_explanation': {
                'keywords': ['错误', '报错', '异常', 'bug', 'error', 'exception', 'wrong', 'fail', '失败', '编译错误'],
                'weight': 1.2
            },
            'comparison': {
                'keywords': ['区别', '对比', 'vs', 'versus', 'difference', 'compared to', '异同', '比较'],
                'weight': 1.1
            },
            'why': {
                'keywords': ['为什么', '为何', 'why', 'reason', '原因'],
                'weight': 1.0
            },
            'how': {
                'keywords': ['如何', '怎么', '怎样', 'how', 'way to', '方法'],
                'weight': 1.0
            },
            'greeting': {
                'keywords': ['你好', '您好', '嗨', 'hi', 'hello', 'hey', '在吗', '有人吗'],
                'weight': 0.8
            },
            'thanks': {
                'keywords': ['谢谢', '感谢', 'thank', 'thanks', 'appreciate', '多谢'],
                'weight': 0.8
            },
            'farewell': {
                'keywords': ['再见', '拜拜', 'bye', 'goodbye', 'see you', '下次见'],
                'weight': 0.8
            }
        }
        
        # 计算每个意图的得分
        scores = {}
        entities = {}
        
        for intent, config in intent_patterns.items():
            score = 0
            matched_keywords = []
            for keyword in config['keywords']:
                if keyword in question_lower:
                    score += 1
                    matched_keywords.append(keyword)
            
            if score > 0:
                # 计算置信度
                confidence = min(0.5 + score * 0.1, 0.95)
                confidence *= config['weight']
                scores[intent] = {
                    'score': score,
                    'confidence': confidence,
                    'keywords': matched_keywords
                }
        
        # 选择最佳意图
        if not scores:
            return {
                'type': 'general',
                'subtype': 'unknown',
                'confidence': 0.3,
                'keywords': [],
                'entities': entities
            }
        
        best_intent = max(scores.items(), key=lambda x: x[1]['confidence'])
        
        return {
            'type': best_intent[0],
            'subtype': 'general',
            'confidence': best_intent[1]['confidence'],
            'keywords': best_intent[1]['keywords'],
            'entities': entities
        }
    
    def _extract_code_blocks(self, text: str) -> List[Dict]:
        """
        从文本中提取所有代码块
        
        返回:
            [{'language': 'cpp', 'code': '...', 'line_count': 10}, ...]
        """
        code_blocks = []
        
        # 匹配 markdown 代码块
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for lang, code in matches:
            code_blocks.append({
                'language': lang or 'text',
                'code': code.strip(),
                'line_count': len(code.strip().split('\n'))
            })
        
        # 匹配行内代码
        inline_pattern = r'`([^`]+)`'
        inline_matches = re.findall(inline_pattern, text)
        
        for code in inline_matches:
            if len(code.split('\n')) > 1:  # 多行行内代码转为代码块
                code_blocks.append({
                    'language': 'text',
                    'code': code.strip(),
                    'line_count': len(code.strip().split('\n')),
                    'inline': True
                })
        
        return code_blocks
    
    def update_user_profile(self, key: str, value: Any):
        """更新用户画像"""
        self.user_profile[key] = value
    
    def get_user_profile(self) -> Dict:
        """获取用户画像"""
        return self.user_profile
    
    def mark_important(self, question: str):
        """标记对话为重要"""
        for h in self.conversation_history:
            if h['question'] == question:
                h['metadata']['important'] = True
                break


class StudentAgent(AIAgent):
    """学生端智能体 - 学习助手小O"""
    
    def __init__(self, api_key: str = None):
        """初始化学生端智能体"""
        super().__init__('student', '学习助手小O', api_key)
        
        # 系统提示词
        self.system_prompt = """你是一个C++编程学习助手，名叫"小O"。你的主要任务是：
1. 帮助学生理解面向对象编程概念（类、对象、继承、多态、封装、虚函数等）
2. 解释C++代码错误并提供修复建议
3. 提供代码示例帮助学生理解
4. 回答要简洁易懂，可以给代码示例，语气亲切
5. 当学生问代码问题时，可以给出详细的代码示例
6. 如果是概念性问题，用通俗易懂的例子解释

请用中文回答，保持友好、耐心的态度。如果遇到不懂的问题，可以建议学生查阅资料或请教老师。"""
        
        print("✅ [ai_agent] 学生端智能体初始化完成")
    
    def ask(self, question: str, context: Optional[Dict] = None) -> Dict:
        """
        学生端智能体回答问题
        
        参数:
            question: 用户问题
            context: 上下文信息
            
        返回:
            {'answer': '', 'type': '', 'suggestions': [], 'code_blocks': []}
        """
        question = question.strip()
        
        result = {
            'answer': '',
            'type': 'general',
            'suggestions': [],
            'code_blocks': [],
            'model': self.model
        }
        
        # 分析意图
        intent = self.analyze_intent(question)
        
        # 构建提示词
        if intent['type'] == 'code_check':
            prompt = f"请检查这段C++代码，找出问题并给出改进建议：\n{question}"
        elif intent['type'] == 'code_generation':
            prompt = f"请提供C++代码示例：{question}\n请给出完整的代码示例，并附上解释。"
        elif intent['type'] == 'error_explanation':
            prompt = f"请解释这个C++错误并提供解决方案：{question}"
        else:
            prompt = question
        
        # 构建消息
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # 添加历史上下文（最近3条）
        history = self.get_history(3)
        for h in history:
            messages.insert(1, {"role": "assistant", "content": h['answer']})
            messages.insert(1, {"role": "user", "content": h['question']})
        
        # 调用API
        response = self._call_zhipu_api(messages, temperature=0.7, max_tokens=2000)
        
        if response['success']:
            answer = response['content']
            result['answer'] = answer
            result['model'] = response['model']
            
            # 提取代码块
            result['code_blocks'] = self._extract_code_blocks(answer)
            
            # 生成建议问题
            result['suggestions'] = self._generate_suggestions(question)
            
            # 判断回答类型
            if '```' in answer:
                result['type'] = 'code'
            elif '错误' in question or 'error' in question.lower():
                result['type'] = 'error'
            else:
                result['type'] = 'concept'
        else:
            result['answer'] = f"抱歉，我现在无法回答这个问题。错误原因：{response.get('error', '未知错误')}\n建议您稍后再试，或者查阅教材和资料。"
        
        # 添加到历史
        self.add_to_history(question, result['answer'], result['type'])
        
        return result
    
    def _generate_suggestions(self, question: str) -> List[str]:
        """生成建议问题"""
        suggestions = []
        question_lower = question.lower()
        
        if '多态' in question or 'polymorphism' in question_lower:
            suggestions = ['虚函数原理', '重载与重写区别', '抽象类示例']
        elif '继承' in question or 'inheritance' in question_lower:
            suggestions = ['public继承', '多继承', '虚基类']
        elif '指针' in question or 'pointer' in question_lower:
            suggestions = ['智能指针', '引用', '动态内存']
        elif '构造' in question or '析构' in question_lower:
            suggestions = ['拷贝构造', '移动语义', 'RAII原则']
        elif '虚函数' in question or 'virtual' in question_lower:
            suggestions = ['纯虚函数', '抽象类', '动态联编']
        elif '类' in question or 'class' in question_lower:
            suggestions = ['构造函数', '析构函数', '静态成员', '友元']
        elif '错误' in question or 'error' in question_lower:
            suggestions = ['编译错误', '链接错误', '运行时错误']
        else:
            suggestions = ['什么是多态？', '解释虚函数', '重载和重写区别', '智能指针']
        
        return suggestions


class TeacherAgent(AIAgent):
    """教师端智能体 - 教学助手小T"""
    
    def __init__(self, api_key: str = None):
        """初始化教师端智能体"""
        super().__init__('teacher', '教学助手小T', api_key)
        
        # 系统提示词
        self.system_prompt = """你是一个C++教学助手，名叫"小T"。你的主要任务是：
1. 帮助教师解答教学问题
2. 提供教学建议和课堂活动想法
3. 生成练习题和代码示例
4. 分析学生常见错误
5. 推荐教学资源
6. 帮助设计课程大纲和教学计划

请用中文回答，提供专业、实用的教学建议。如果涉及代码，请提供清晰的示例。"""
        
        print("✅ [ai_agent] 教师端智能体初始化完成")
    
    def ask(self, question: str, context: Optional[Dict] = None) -> Dict:
        """
        教师端智能体回答问题
        
        参数:
            question: 用户问题
            context: 上下文信息（班级数据等）
            
        返回:
            {'answer': '', 'type': '', 'suggestions': [], 'resources': []}
        """
        question = question.strip()
        
        result = {
            'answer': '',
            'type': 'general',
            'suggestions': [],
            'resources': [],
            'model': self.model
        }
        
        # 构建提示词，包含上下文信息
        prompt = question
        if context:
            prompt += f"\n\n上下文信息：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        
        # 构建消息
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # 添加历史上下文（最近3条）
        history = self.get_history(3)
        for h in history:
            messages.insert(1, {"role": "assistant", "content": h['answer']})
            messages.insert(1, {"role": "user", "content": h['question']})
        
        # 调用API
        response = self._call_zhipu_api(messages, temperature=0.7, max_tokens=2000)
        
        if response['success']:
            answer = response['content']
            result['answer'] = answer
            result['model'] = response['model']
            
            # 判断回答类型
            if '教学建议' in question or '如何教' in question:
                result['type'] = 'teaching_advice'
            elif '题目' in question or '练习题' in question:
                result['type'] = 'quiz'
            elif '分析' in question and '班级' in question:
                result['type'] = 'analysis'
            else:
                result['type'] = 'general'
        else:
            result['answer'] = f"抱歉，我现在无法回答这个问题。错误原因：{response.get('error', '未知错误')}\n建议您稍后再试。"
        
        # 添加到历史
        self.add_to_history(question, result['answer'], result['type'])
        
        return result
    
    def analyze_class_data(self, class_data: Dict) -> Dict:
        """
        分析班级数据（使用AI增强）
        
        参数:
            class_data: 班级数据字典
            
        返回:
            分析结果
        """
        prompt = f"""请分析以下班级数据，提供教学建议：

班级数据：
{json.dumps(class_data, ensure_ascii=False, indent=2)}

请从以下方面分析：
1. 整体学习情况评估
2. 薄弱知识点识别
3. 需要重点关注的学生
4. 教学改进建议

请用中文返回分析结果，格式清晰。"""
        
        messages = [
            {"role": "system", "content": "你是一个教学数据分析专家，擅长从数据中发现教学问题并提供改进建议。"},
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_zhipu_api(messages, temperature=0.5, max_tokens=1500)
        
        if response['success']:
            return {
                'analysis': response['content'],
                'model': response['model']
            }
        else:
            return {
                'analysis': f"分析失败：{response.get('error', '未知错误')}",
                'model': self.model
            }
    
    def generate_quiz(self, topic: str, difficulty: str = 'medium', count: int = 3) -> List[Dict]:
        """
        生成测验题目（使用AI）
        
        参数:
            topic: 主题
            difficulty: 难度 easy/medium/hard
            count: 题目数量
            
        返回:
            题目列表
        """
        prompt = f"""请生成{difficulty}难度的{count}道关于"{topic}"的C++测验题目。

要求：
1. 题目类型可以包括选择题、填空题、简答题或编程题
2. 每道题都要包含题目、答案和简要解析
3. 题目要有区分度，适合考察学生对知识点的理解

请以JSON格式返回，格式如下：
[
    {{
        "type": "选择题",
        "question": "题目内容",
        "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
        "answer": "A",
        "explanation": "解析"
    }},
    ...
]"""
        
        messages = [
            {"role": "system", "content": "你是一个C++教学专家，擅长生成高质量的测验题目。"},
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_zhipu_api(messages, temperature=0.7, max_tokens=2000)
        
        if response['success']:
            try:
                # 尝试解析JSON
                json_match = re.search(r'\[[\s\S]*\]', response['content'])
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
            # 如果解析失败，返回原始文本
            return [{'question': response['content'], 'type': 'text', 'answer': '', 'explanation': ''}]
        else:
            return [{'question': '生成题目失败，请稍后重试', 'type': 'text', 'answer': '', 'explanation': ''}]


# 智能体工厂
class AgentFactory:
    """智能体工厂类 - 使用单例模式"""
    
    _instances = {}
    
    @classmethod
    def get_agent(cls, role: str, api_key: str = None) -> AIAgent:
        """获取智能体实例"""
        key = f"{role}_{api_key}" if api_key else role
        
        if key not in cls._instances:
            if role == 'student':
                cls._instances[key] = StudentAgent(api_key)
            elif role == 'teacher':
                cls._instances[key] = TeacherAgent(api_key)
            else:
                raise ValueError(f"未知角色: {role}")
        return cls._instances[key]
    
    @classmethod
    def clear_instances(cls):
        """清除所有实例"""
        cls._instances.clear()