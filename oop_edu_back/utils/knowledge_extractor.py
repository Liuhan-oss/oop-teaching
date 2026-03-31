"""
知识点提取工具模块
用于从PPT文档、作业内容等文本中提取OOP相关知识点
"""
import re
import jieba
import jieba.analyse
from collections import Counter
from typing import List, Dict, Set, Tuple, Optional
import os

class KnowledgeExtractor:
    """OOP知识点提取器 - 基于七章PPT"""
    
    # ==================== 七章PPT完整知识点 ====================
    
    # 第一章：C++语言编程入门
    CHAPTER1_KNOWLEDGE = [
        "C++语言产生", "C++与C语言关系", "开发步骤", "程序组成",
        "词法记号", "关键字", "标识符", "运算符", "分隔符", "常量", "注释符",
        "数据类型", "char", "int", "float", "double", "void",
        "变量", "变量声明", "变量命名规则",
        "常量", "整型常量", "字符常量", "字符串常量", "符号常量",
        "数组", "一维数组", "二维数组", "多维数组", "字符数组",
        "运算符", "算术运算符", "关系运算符", "逻辑运算符", "赋值运算符", "sizeof", "条件运算符",
        "表达式", "算术表达式", "赋值表达式", "逗号表达式",
        "类型转换", "隐含转换", "强制转换",
        "控制语句", "if语句", "switch语句", "while循环", "do-while循环", "for循环", "break", "continue"
    ]
    
    # 第二章：函数
    CHAPTER2_KNOWLEDGE = [
        "函数定义", "函数声明", "函数原型", "函数调用",
        "参数传递", "传值调用", "传址调用", "形式参数", "实际参数",
        "返回值", "return语句",
        "内联函数", "inline",
        "默认形参值", "默认参数",
        "作用域", "全局变量", "局部变量", "块作用域", "函数作用域",
        "递归调用", "递归函数",
        "函数重载", "重载函数",
        "系统函数", "库函数"
    ]
    
    # 第三章：类与对象
    CHAPTER3_KNOWLEDGE = [
        "类的声明", "class", "public", "protected", "private",
        "对象的声明", "实例化",
        "构造函数", "构造函数重载", "默认构造函数", "拷贝构造函数",
        "析构函数", "~类名",
        "类的组合", "对象成员",
        "静态成员", "静态数据成员", "静态成员函数", "static",
        "友元", "友元函数", "友元类", "friend",
        "常对象", "const对象",
        "常数据成员", "const成员",
        "类作用域",
        "对象生存期", "静态生存期", "动态生存期",
        "对象指针", "->运算符"
    ]
    
    # 第四章：指针与引用
    CHAPTER4_KNOWLEDGE = [
        "指针声明", "指针变量",
        "指针运算", "指针递增", "指针递减", "指针减法",
        "const指针", "指向常量的指针", "指针常量",
        "void指针",
        "动态内存分配", "new运算符", "delete运算符",
        "数组指针", "指向数组的指针",
        "指针数组",
        "指针作函数参数",
        "返回指针的函数",
        "字符串", "字符数组", "字符串常量",
        "引用", "引用变量", "别名",
        "引用作函数参数",
        "返回引用的函数",
        "链表", "Node", "List", "插入", "删除", "排序"
    ]
    
    # 第五章：继承
    CHAPTER5_KNOWLEDGE = [
        "继承", "派生",
        "单继承",
        "多继承",
        "公有派生", "public继承",
        "私有派生", "private继承",
        "保护派生", "protected继承",
        "派生类构造函数", "构造函数调用顺序",
        "派生类析构函数", "析构函数调用顺序",
        "二义性问题", "同名成员",
        "虚基类", "virtual继承", "菱形继承",
        "赋值兼容原则"
    ]
    
    # 第六章：运算符重载
    CHAPTER6_KNOWLEDGE = [
        "运算符重载", "operator关键字",
        "重载规则",
        "一元运算符重载", "++重载", "--重载", "负号重载", "逻辑非重载",
        "二元运算符重载", "+重载", "-重载", "*重载", "/重载",
        "赋值运算符重载", "=重载",
        "++重载", "前缀++", "后缀++",
        "--重载", "前缀--", "后缀--",
        "new重载", "delete重载",
        "成员函数重载", "友元函数重载"
    ]
    
    # 第七章：多态与虚函数
    CHAPTER7_KNOWLEDGE = [
        "多态性", "编译时多态", "运行时多态",
        "静态联编", "早期联编",
        "动态联编", "晚期联编",
        "虚函数", "virtual",
        "纯虚函数", "virtual =0",
        "抽象类",
        "包含多态",
        "重载多态",
        "强制转换多态"
    ]
    
    # 合并所有知识点
    ALL_KNOWLEDGE = []
    for i in range(1, 8):
        ALL_KNOWLEDGE.extend(eval(f"CHAPTER{i}_KNOWLEDGE"))
    
    # 知识点-章节映射
    CHAPTER_MAPPING = {
        1: "第一章 C++语言编程入门",
        2: "第二章 函数",
        3: "第三章 类与对象",
        4: "第四章 指针与引用",
        5: "第五章 继承",
        6: "第六章 运算符重载",
        7: "第七章 多态与虚函数"
    }
    
    # 知识点难度等级 (1-5)
    DIFFICULTY_MAPPING = {
        # 第一章 - 基础
        "C++语言产生": 1, "C++与C语言关系": 1, "开发步骤": 1, "程序组成": 1,
        "数据类型": 2, "变量": 1, "常量": 1, "数组": 2, "运算符": 2,
        "表达式": 2, "类型转换": 2, "控制语句": 2,
        
        # 第二章 - 基础到中级
        "函数定义": 2, "函数声明": 2, "函数调用": 2, "参数传递": 2,
        "返回值": 1, "内联函数": 2, "默认形参值": 2, "作用域": 2,
        "递归调用": 3, "函数重载": 3, "系统函数": 1,
        
        # 第三章 - 中级
        "类的声明": 3, "对象的声明": 3, "构造函数": 3, "析构函数": 3,
        "类的组合": 3, "静态成员": 3, "友元": 3, "常对象": 3,
        "常数据成员": 3, "类作用域": 2, "对象生存期": 2, "对象指针": 3,
        
        # 第四章 - 中级
        "指针声明": 3, "指针运算": 3, "const指针": 3, "void指针": 3,
        "动态内存分配": 3, "数组指针": 3, "指针数组": 3,
        "指针作函数参数": 3, "返回指针的函数": 3, "字符串": 2,
        "引用": 3, "引用作函数参数": 3, "返回引用的函数": 3, "链表": 4,
        
        # 第五章 - 中高级
        "继承": 4, "单继承": 3, "多继承": 4, "公有派生": 3,
        "私有派生": 3, "保护派生": 3, "派生类构造函数": 4,
        "派生类析构函数": 4, "二义性问题": 4, "虚基类": 5,
        "赋值兼容原则": 3,
        
        # 第六章 - 中高级
        "运算符重载": 4, "重载规则": 4, "一元运算符重载": 4,
        "二元运算符重载": 4, "赋值运算符重载": 4, "++重载": 4,
        "--重载": 4, "new重载": 5, "delete重载": 5,
        "成员函数重载": 4, "友元函数重载": 4,
        
        # 第七章 - 高级
        "多态性": 5, "静态联编": 4, "动态联编": 5, "虚函数": 5,
        "纯虚函数": 5, "抽象类": 5, "包含多态": 5,
        "重载多态": 4, "强制转换多态": 4
    }
    
    def __init__(self):
        """初始化知识点提取器"""
        # 构建知识点索引
        self.knowledge_index = self._build_knowledge_index()
        
        # 加载自定义词典
        self._load_custom_dict()
        
        print(f"✅ 知识点提取器初始化完成，共 {len(self.ALL_KNOWLEDGE)} 个知识点")
    
    def _load_custom_dict(self):
        """加载自定义词典到jieba"""
        try:
            for knowledge in self.ALL_KNOWLEDGE:
                jieba.add_word(knowledge, freq=2000, tag='nz')
                
                # 添加不带空格的版本（如果有空格）
                if ' ' in knowledge:
                    jieba.add_word(knowledge.replace(' ', ''), freq=1500, tag='nz')
            
            # 添加英文关键词
            jieba.add_word('C++', freq=5000, tag='eng')
            jieba.add_word('class', freq=3000, tag='eng')
            jieba.add_word('public', freq=3000, tag='eng')
            jieba.add_word('private', freq=3000, tag='eng')
            jieba.add_word('protected', freq=3000, tag='eng')
            jieba.add_word('virtual', freq=3000, tag='eng')
            jieba.add_word('static', freq=3000, tag='eng')
            jieba.add_word('const', freq=3000, tag='eng')
            jieba.add_word('friend', freq=3000, tag='eng')
            jieba.add_word('operator', freq=3000, tag='eng')
            jieba.add_word('new', freq=3000, tag='eng')
            jieba.add_word('delete', freq=3000, tag='eng')
            jieba.add_word('inline', freq=3000, tag='eng')
            
        except Exception as e:
            print(f"⚠️ 加载自定义词典失败: {e}")
    
    def _build_knowledge_index(self) -> Dict[str, Dict]:
        """构建知识点索引"""
        index = {}
        
        for knowledge in self.ALL_KNOWLEDGE:
            # 检测所属章节
            chapter = self._detect_chapter(knowledge)
            
            # 获取难度
            difficulty = self.DIFFICULTY_MAPPING.get(knowledge, 3)
            
            # 获取相关知识点
            related = self._get_related_knowledge(knowledge)
            
            index[knowledge] = {
                "name": knowledge,
                "chapter": chapter,
                "chapter_name": self.CHAPTER_MAPPING.get(chapter, "未知章节"),
                "difficulty": difficulty,
                "related": related[:5],  # 取前5个相关知识点
                "keywords": self._extract_keywords(knowledge)
            }
        
        return index
    
    def _detect_chapter(self, knowledge: str) -> int:
        """检测知识点所属章节"""
        for chapter in range(1, 8):
            chapter_list = eval(f"self.CHAPTER{chapter}_KNOWLEDGE")
            if knowledge in chapter_list:
                return chapter
        return 1  # 默认第一章
    
    def _extract_keywords(self, knowledge: str) -> List[str]:
        """从知识点名称中提取关键词"""
        # 简单的分词
        words = []
        for word in knowledge:
            if len(word) > 1 and not word.isspace():
                words.append(word)
        
        # 添加英文关键词
        if 'C++' in knowledge:
            words.append('C++')
        if 'class' in knowledge.lower():
            words.append('class')
        
        return list(set(words))
    
    def _get_related_knowledge(self, knowledge: str) -> List[str]:
        """获取相关知识点（基于章节关联）"""
        related = []
        chapter = self._detect_chapter(knowledge)
        
        # 同章节的其他知识点
        chapter_list = eval(f"self.CHAPTER{chapter}_KNOWLEDGE")
        for other in chapter_list[:10]:  # 取前10个
            if other != knowledge and other not in related:
                related.append(other)
        
        # 前后章节关联
        if chapter > 1:
            prev_list = eval(f"self.CHAPTER{chapter-1}_KNOWLEDGE")
            related.extend(prev_list[:3])
        
        if chapter < 7:
            next_list = eval(f"self.CHAPTER{chapter+1}_KNOWLEDGE")
            related.extend(next_list[:3])
        
        return list(set(related))
    
    def extract_from_text(self, text: str, top_k: int = 10) -> List[Dict]:
        """
        从文本中提取知识点
        
        参数:
            text: 输入文本
            top_k: 返回前k个知识点
            
        返回:
            知识点列表，每个知识点包含名称、权重、章节等信息
        """
        if not text or len(text.strip()) == 0:
            return []
        
        results = []
        
        # 方法1：精确匹配
        for knowledge in self.ALL_KNOWLEDGE:
            count = text.count(knowledge)
            if count > 0:
                # 检查是否完整词匹配（避免部分匹配）
                pattern = r'\b' + re.escape(knowledge) + r'\b'
                exact_count = len(re.findall(pattern, text))
                
                if exact_count > 0:
                    results.append({
                        "name": knowledge,
                        "count": exact_count,
                        "chapter": self._detect_chapter(knowledge),
                        "chapter_name": self.CHAPTER_MAPPING.get(self._detect_chapter(knowledge), "未知"),
                        "difficulty": self.DIFFICULTY_MAPPING.get(knowledge, 3),
                        "method": "exact_match",
                        "weight": exact_count * 10
                    })
        
        # 方法2：基于TF-IDF
        try:
            # 使用jieba提取关键词
            tags = jieba.analyse.extract_tags(
                text, topK=top_k * 3, 
                allowPOS=('n', 'vn', 'nz', 'eng', 'nrt')
            )
            
            # 计算词频
            words = jieba.lcut(text)
            word_freq = Counter(words)
            
            for tag in tags:
                # 检查是否匹配知识点
                for knowledge in self.ALL_KNOWLEDGE:
                    # 如果标签包含知识点或知识点包含标签
                    if tag in knowledge or knowledge in tag:
                        if not any(r["name"] == knowledge for r in results):
                            freq = word_freq.get(tag, 1)
                            results.append({
                                "name": knowledge,
                                "count": freq,
                                "chapter": self._detect_chapter(knowledge),
                                "chapter_name": self.CHAPTER_MAPPING.get(self._detect_chapter(knowledge), "未知"),
                                "difficulty": self.DIFFICULTY_MAPPING.get(knowledge, 3),
                                "method": "tfidf",
                                "weight": freq * 5
                            })
                        break
        except Exception as e:
            print(f"TF-IDF提取失败: {e}")
        
        # 方法3：基于关键词匹配
        # 常见英文关键词映射到知识点
        keyword_map = {
            "class": ["类的声明", "class"],
            "object": ["对象的声明", "对象"],
            "继承": ["继承", "派生"],
            "多态": ["多态性", "虚函数"],
            "指针": ["指针声明", "指针运算"],
            "引用": ["引用"],
            "函数": ["函数定义", "函数调用"],
            "重载": ["函数重载", "运算符重载"],
            "构造": ["构造函数"],
            "析构": ["析构函数"],
            "虚函数": ["虚函数"],
            "抽象类": ["抽象类"],
            "接口": ["抽象类"],
            "封装": ["类的声明", "private"],
            "new": ["new运算符", "动态内存分配"],
            "delete": ["delete运算符", "动态内存分配"],
            "const": ["const指针", "常对象"],
            "static": ["静态成员"],
            "friend": ["友元"],
            "operator": ["运算符重载"],
            "virtual": ["虚函数", "纯虚函数"],
            "public": ["公有派生"],
            "private": ["私有派生"],
            "protected": ["保护派生"]
        }
        
        lower_text = text.lower()
        for eng_keyword, knowledge_list in keyword_map.items():
            if eng_keyword in lower_text:
                for knowledge in knowledge_list:
                    if knowledge in self.ALL_KNOWLEDGE:
                        if not any(r["name"] == knowledge for r in results):
                            results.append({
                                "name": knowledge,
                                "count": lower_text.count(eng_keyword),
                                "chapter": self._detect_chapter(knowledge),
                                "chapter_name": self.CHAPTER_MAPPING.get(self._detect_chapter(knowledge), "未知"),
                                "difficulty": self.DIFFICULTY_MAPPING.get(knowledge, 3),
                                "method": "keyword_match",
                                "weight": lower_text.count(eng_keyword) * 3
                            })
        
        # 去重并排序
        seen = set()
        unique_results = []
        
        # 按权重排序
        for r in sorted(results, key=lambda x: -x.get("weight", x.get("count", 1))):
            if r["name"] not in seen:
                seen.add(r["name"])
                # 计算最终权重
                final_weight = r.get("weight", r.get("count", 1))
                r["final_weight"] = final_weight
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    def extract_from_ppt(self, ppt_text: str) -> Dict[int, List[str]]:
        """
        从PPT文本中按章节提取知识点
        
        参数:
            ppt_text: PPT文本内容
            
        返回:
            按章节分组的知识点字典
        """
        result = {i: [] for i in range(1, 8)}
        
        # 按章节提取
        for chapter in range(1, 8):
            chapter_list = eval(f"self.CHAPTER{chapter}_KNOWLEDGE")
            found = []
            
            for knowledge in chapter_list:
                if knowledge in ppt_text:
                    found.append(knowledge)
            
            result[chapter] = found
        
        return result
    
    def get_knowledge_by_chapter(self, chapter: int) -> List[str]:
        """
        获取指定章节的所有知识点
        
        参数:
            chapter: 章节号 (1-7)
            
        返回:
            知识点列表
        """
        if 1 <= chapter <= 7:
            return eval(f"self.CHAPTER{chapter}_KNOWLEDGE")
        return []
    
    def get_knowledge_detail(self, knowledge_name: str) -> Optional[Dict]:
        """
        获取知识点详细信息
        
        参数:
            knowledge_name: 知识点名称
            
        返回:
            知识点详细信息，包括章节、难度、相关知识点等
        """
        if knowledge_name in self.knowledge_index:
            return self.knowledge_index[knowledge_name]
        return None
    
    def calculate_mastery(self, student_errors: Dict[str, int]) -> Dict[str, int]:
        """
        根据错误次数计算知识点掌握度
        
        参数:
            student_errors: 知识点错误次数字典 {知识点名称: 错误次数}
            
        返回:
            掌握度字典 {知识点名称: 掌握度(0-100)}
        """
        mastery = {}
        
        for knowledge in self.ALL_KNOWLEDGE:
            error_count = student_errors.get(knowledge, 0)
            # 掌握度 = max(30, 100 - 错误次数 * 8)
            level = max(30, 100 - error_count * 8)
            mastery[knowledge] = level
        
        return mastery
    
    def recommend_next_knowledge(self, mastered: List[str]) -> List[str]:
        """
        根据已掌握知识点推荐下一个要学习的知识点
        
        参数:
            mastered: 已掌握的知识点列表
            
        返回:
            推荐的知识点列表
        """
        # 简单的推荐逻辑：推荐未掌握且难度适中的知识点
        not_mastered = [k for k in self.ALL_KNOWLEDGE if k not in mastered]
        
        # 按难度排序
        not_mastered.sort(key=lambda x: self.DIFFICULTY_MAPPING.get(x, 3))
        
        return not_mastered[:5]
    
    def search_knowledge(self, keyword: str) -> List[Dict]:
        """
        搜索知识点
        
        参数:
            keyword: 搜索关键词
            
        返回:
            匹配的知识点列表
        """
        results = []
        keyword_lower = keyword.lower()
        
        for knowledge in self.ALL_KNOWLEDGE:
            if keyword_lower in knowledge.lower():
                results.append({
                    "name": knowledge,
                    "chapter": self._detect_chapter(knowledge),
                    "chapter_name": self.CHAPTER_MAPPING.get(self._detect_chapter(knowledge), "未知"),
                    "difficulty": self.DIFFICULTY_MAPPING.get(knowledge, 3)
                })
        
        return results
    
    def get_statistics(self) -> Dict:
        """
        获取知识点统计信息
        
        返回:
            统计信息字典
        """
        stats = {
            "total": len(self.ALL_KNOWLEDGE),
            "by_chapter": {},
            "by_difficulty": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        }
        
        for chapter in range(1, 8):
            chapter_list = eval(f"self.CHAPTER{chapter}_KNOWLEDGE")
            stats["by_chapter"][chapter] = len(chapter_list)
        
        for knowledge in self.ALL_KNOWLEDGE:
            difficulty = self.DIFFICULTY_MAPPING.get(knowledge, 3)
            stats["by_difficulty"][difficulty] = stats["by_difficulty"].get(difficulty, 0) + 1
        
        return stats


# ==================== 便捷函数 ====================

def extract_knowledge_from_file(file_path: str, top_k: int = 10) -> List[Dict]:
    """
    从文件中提取知识点
    
    参数:
        file_path: 文件路径
        top_k: 返回前k个知识点
        
    返回:
        知识点列表
    """
    extractor = KnowledgeExtractor()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return extractor.extract_from_text(text, top_k)
    except Exception as e:
        print(f"读取文件失败: {e}")
        return []


def get_chapter_summary(chapter: int) -> str:
    """
    获取章节概要
    
    参数:
        chapter: 章节号 (1-7)
        
    返回:
        章节概要文本
    """
    summaries = {
        1: "第一章：C++语言编程入门 - 包括C++产生、开发步骤、数据类型、变量、常量、数组、运算符、表达式、控制语句等基础内容",
        2: "第二章：函数 - 包括函数定义、声明、调用、参数传递、返回值、内联函数、默认参数、作用域、递归、重载等",
        3: "第三章：类与对象 - 包括类的声明、对象的声明、构造函数、析构函数、静态成员、友元、常对象等",
        4: "第四章：指针与引用 - 包括指针声明、运算、const指针、动态内存分配、数组指针、引用、链表等",
        5: "第五章：继承 - 包括单继承、多继承、派生类型、构造函数/析构函数调用顺序、二义性、虚基类等",
        6: "第六章：运算符重载 - 包括一元/二元运算符重载、赋值运算符重载、++/--重载、new/delete重载等",
        7: "第七章：多态与虚函数 - 包括静态联编、动态联编、虚函数、纯虚函数、抽象类、多态类型等"
    }
    
    return summaries.get(chapter, "未知章节")


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 测试知识点提取器
    extractor = KnowledgeExtractor()
    
    # 打印统计信息
    stats = extractor.get_statistics()
    print("\n📊 知识点统计:")
    print(f"总知识点数: {stats['total']}")
    print("各章节数量:")
    for ch, count in stats['by_chapter'].items():
        print(f"  第{ch}章: {count}个")
    print("各难度等级:")
    for diff, count in stats['by_difficulty'].items():
        print(f"  难度{diff}: {count}个")
    
    # 测试文本提取
    test_text = """
    面向对象编程中，类是非常重要的概念。类可以包含数据成员和成员函数。
    通过类可以创建对象，对象是类的实例。构造函数在对象创建时被调用，
    析构函数在对象销毁时被调用。继承是OOP的重要特性，通过继承可以创建
    派生类。多态性允许使用基类指针调用派生类的虚函数。
    """
    
    print("\n📝 测试文本提取:")
    results = extractor.extract_from_text(test_text, top_k=5)
    for r in results:
        print(f"  - {r['name']} (第{r['chapter']}章, 权重:{r.get('final_weight', r['count'])})")
    
    # 测试搜索
    print("\n🔍 搜索 '指针':")
    search_results = extractor.search_knowledge("指针")
    for r in search_results[:5]:
        print(f"  - {r['name']}")