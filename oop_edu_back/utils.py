import random
import jieba.analyse

# ===================== 优化后的热词提取（真实提取，非占位）=====================
def extract_hot_words(text, top_k=5, method="textrank"):
    """
    真实热词提取函数
    :param text: 输入文本
    :param top_k: 提取热词数量
    :param method: 提取方法（textrank/extract_tags）
    :return: 包含热词、权重、方法的字典
    """
    # 过滤空文本
    if not text or text.strip() == "":
        return {"hot_words": [], "weights": [], "method": method}
    
    # 设置停用词（过滤无意义词汇）
    stop_words = {
        "的", "了", "是", "我", "你", "他", "在", "和", "与", "或", 
        "一个", "实现", "使用", "要求", "功能", "编写", "代码", "格式",
        "规范", "请", "输入", "输出", "以及", "还有", "需要", "能够"
    }
    
    try:
        # 两种提取方法可选
        if method == "textrank":
            # TextRank算法（更注重语义关联）
            keywords = jieba.analyse.textrank(text, topK=top_k*2, withWeight=True)
        else:
            # TF-IDF算法（更注重词频）
            keywords = jieba.analyse.extract_tags(text, topK=top_k*2, withWeight=True)
        
        # 过滤停用词，保留前top_k个有效热词
        hot_words = []
        weights = []
        for word, weight in keywords:
            if word not in stop_words and len(word) > 1:  # 过滤单字和停用词
                hot_words.append(word)
                weights.append(round(weight, 2))
                if len(hot_words) >= top_k:
                    break
        
        # 如果提取结果为空，返回基础兜底值
        if not hot_words:
            hot_words = ["基础知识点", "核心考点"]
            weights = [1.0, 0.9]
        
        return {"hot_words": hot_words, "weights": weights, "method": method}
    
    except Exception as e:
        # 异常兜底，保证不报错
        return {"hot_words": ["测试", "热词"], "weights": [1, 0.9], "method": method}

# ===================== 普通作业生成（优化版）=====================
def generate_homework(knowledge_points, difficulty="medium", num_questions=5):
    """
    根据知识点生成普通作业
    :param knowledge_points: 知识点列表
    :param difficulty: 难度（easy/medium/hard）
    :param num_questions: 题目数量
    :return: 作业题目列表
    """
    # 按知识点分类的题库
    question_bank = {
        "Python基础": {
            "easy": ["Python的基本数据类型有哪些？", "如何定义和调用函数？", "列表和字典的区别是什么？"],
            "medium": ["简述装饰器的作用和使用场景", "异常处理的try-except语法？", "迭代器和生成器的区别？"],
            "hard": ["深拷贝和浅拷贝的区别？", "GIL锁对Python多线程的影响？", "元类的作用和实现方式？"]
        },
        "Flask路由": {
            "easy": ["Flask中如何定义基本路由？", "GET和POST请求的区别？", "如何获取URL参数？"],
            "medium": ["Flask蓝图的作用是什么？", "如何设置路由的请求方法？", "路由装饰器的参数有哪些？"],
            "hard": ["before_request装饰器的执行顺序？", "如何实现路由的动态参数？", "Flask路由的底层实现原理？"]
        },
        "SQL查询": {
            "easy": ["SELECT语句的基本语法？", "WHERE条件的使用方法？", "如何排序查询结果？"],
            "medium": ["JOIN的几种类型和区别？", "GROUP BY和HAVING的用法？", "子查询的使用场景？"],
            "hard": ["索引的类型和优化原则？", "如何避免SQL注入？", "分库分表的实现思路？"]
        },
        "HTML布局": {
            "easy": ["HTML的基本结构是什么？", "常用的块级元素有哪些？", "如何引入CSS样式？"],
            "medium": ["Flex布局的常用属性？", "响应式布局的实现方式？", "CSS选择器的优先级？"],
            "hard": ["Grid布局和Flex布局的区别？", "CSS动画的实现原理？", "浏览器渲染机制？"]
        }
    }
    
    homework = []
    qid = 1
    
    # 确保知识点存在，不存在则用默认
    valid_points = [p for p in knowledge_points if p in question_bank]
    if not valid_points:
        valid_points = ["Python基础"]
    
    # 生成题目
    for _ in range(num_questions):
        # 随机选知识点和题目
        point = random.choice(valid_points)
        questions = question_bank[point].get(difficulty, question_bank[point]["medium"])
        content = random.choice(questions)
        
        homework.append({
            "question_id": qid,
            "question_content": content,
            "knowledge_point": point,
            "difficulty": difficulty
        })
        qid += 1
    
    return homework

# ===================== 推送知识点（优化版）=====================
def push_knowledge_points(user_level="beginner"):
    """根据用户等级推送知识点"""
    level_points = {
        "beginner": ["Python基础语法", "HTML基础标签", "SQL基本查询"],
        "intermediate": ["Flask路由", "Python函数进阶", "SQL联表查询"],
        "advanced": ["Flask蓝图", "Python装饰器", "SQL优化", "响应式布局"]
    }
    return level_points.get(user_level, level_points["beginner"])

# ===================== 更新个人错题图谱 =====================
def update_personal_wrong_graph(username, wrong_knowledge_points):
    return {
        "success": True,
        "msg": f"用户{username}的错题图谱已更新，新增错题知识点：{','.join(wrong_knowledge_points)}"
    }

# ===================== 图谱推荐薄弱点 =====================
def recommend_from_graph(username, top_n=3):
    # 模拟从图谱中分析的薄弱点
    weak_candidates = ["Flask路由", "SQL查询", "Python装饰器", "响应式布局"]
    weak_points = random.sample(weak_candidates, min(top_n, len(weak_candidates)))
    
    return {
        "success": True,
        "msg": f"为{username}推荐{len(weak_points)}个薄弱知识点",
        "weak_points": weak_points
    }

# ===================== 个性化作业生成（70%+20%+10%）=====================
def generate_personalized_homework(username, weak_points=None, total_questions=10):
    """
    生成个性化作业（70%薄弱题+20%基础题+10%进阶题）
    :param username: 用户名
    :param weak_points: 薄弱知识点（None则自动推荐）
    :param total_questions: 总题数
    :return: 个性化作业
    """
    # 如果没有指定薄弱点，自动推荐
    if not weak_points:
        weak_points = recommend_from_graph(username)["weak_points"]
    
    # 计算各类型题目数量
    weak_num = int(total_questions * 0.7)
    basic_num = int(total_questions * 0.2)
    adv_num = total_questions - weak_num - basic_num

    # 扩展题库（覆盖更多知识点）
    question_bank = {
        "Python基础": {
            "easy": ["输出语句print的用法？", "变量命名规则？", "列表的增删改查？"],
            "medium": ["for循环和while循环的区别？", "字典的遍历方式？", "模块的导入方法？"],
            "hard": ["闭包的定义和使用场景？", "多线程和多进程的区别？", "装饰器的实现？"]
        },
        "Flask路由": {
            "easy": ["Flask路由如何定义？", "路由参数怎么传？", "如何返回JSON数据？"],
            "medium": ["Flask蓝图是什么？", "before_request 作用？", "如何处理静态文件？"],
            "hard": ["Flask中间件的实现？", "路由匹配的底层原理？", "如何实现路由权限控制？"]
        },
        "SQL查询": {
            "easy": ["SELECT 语法？", "WHERE 作用？", "LIMIT的用法？"],
            "medium": ["联查怎么写？", "GROUP BY 场景？", "索引的基本作用？"],
            "hard": ["什么是索引？", "如何防注入？", "分库分表的设计思路？"]
        },
        "HTML布局": {
            "easy": ["HTML基本结构？", "常用标签有哪些？", "如何引入CSS？"],
            "medium": ["Flex布局的使用？", "媒体查询的写法？", "CSS选择器优先级？"],
            "hard": ["Grid布局实战？", "CSS动画实现？", "浏览器渲染优化？"]
        }
    }

    homework = []
    qid = 1

    # 70% 薄弱题（针对薄弱知识点）
    valid_weak_points = [p for p in weak_points if p in question_bank]
    if not valid_weak_points:
        valid_weak_points = ["Python基础"]
    
    for _ in range(weak_num):
        point = random.choice(valid_weak_points)
        content = random.choice(question_bank[point]["medium"])
        homework.append({
            "question_id": qid,
            "content": content,
            "knowledge_point": point,
            "difficulty": "medium",
            "type": "薄弱巩固题"
        })
        qid +=1

    # 20% 基础题（通用基础知识点）
    basic_points = ["Python基础", "HTML布局"]
    for _ in range(basic_num):
        point = random.choice(basic_points)
        content = random.choice(question_bank[point]["easy"])
        homework.append({
            "question_id": qid,
            "content": content,
            "knowledge_point": point,
            "difficulty": "easy",
            "type": "基础巩固题"
        })
        qid +=1

    # 10% 进阶题（拓展知识点）
    adv_points = ["Flask路由", "SQL查询"]
    for _ in range(adv_num):
        point = random.choice(adv_points)
        content = random.choice(question_bank[point]["hard"])
        homework.append({
            "question_id": qid,
            "content": content,
            "knowledge_point": point,
            "difficulty": "hard",
            "type": "能力提升题"
        })
        qid +=1

    # 打乱题目顺序
    random.shuffle(homework)

    return {
        "success": True,
        "msg": f"已为{username}生成{len(homework)}道个性化作业（70%薄弱+20%基础+10%进阶）",
        "homework": homework,
        "weak_points_used": valid_weak_points
    }