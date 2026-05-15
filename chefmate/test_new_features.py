"""
ChefMate 新功能测试
测试会话管理、答案验证、反馈收集等新功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEFAULT_CONFIG

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ PASS: {name}")
    else:
        FAIL += 1
        print(f"  ❌ FAIL: {name}  {detail}")


def print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ═══════════════════════════════════════════════
# 测试 1: 上下文预算管理器
# ═══════════════════════════════════════════════
print_header("模块 1: ContextBudgetManager")

from chefmate.context_budget import ContextBudgetManager

cbm = ContextBudgetManager(max_tokens=500)
test("初始化", cbm.max_tokens == 500)

# 测试 token 计数
count = cbm._count_tokens("这是一段中文测试文本")
test("token 计数 (中文)", count > 0, f"count={count}")

count_en = cbm._count_tokens("This is English text")
test("token 计数 (英文)", count_en > 0, f"count={count_en}")

# 测试截断
long_text = "测试文本" * 1000
truncated = cbm.truncate_to_budget(long_text)
test("文本截断", len(truncated) < len(long_text), f"原始 {len(long_text)}, 截断后 {len(truncated)}")

# 测试上下文压缩
from langchain_core.documents import Document
docs = [
    Document(page_content="# 测试菜\n## 食材\n- 鸡蛋\n## 步骤\n1. 打蛋", metadata={"chunk_id": "1"}),
    Document(page_content="另一个菜谱内容" * 100, metadata={"chunk_id": "2"}),
]
compressed = cbm.compress_context(docs, "测试查询")
test("上下文压缩", len(compressed) > 0, f"压缩后长度={len(compressed)}")


# ═══════════════════════════════════════════════
# 测试 2: 答案验证器
# ═══════════════════════════════════════════════
print_header("模块 2: AnswerValidator")

from chefmate.validator import AnswerValidator

av = AnswerValidator()

# 加载有效菜品
docs = [
    Document(page_content="test", metadata={"dish_name": "宫保鸡丁"}),
    Document(page_content="test", metadata={"dish_name": "西红柿炒鸡蛋"}),
    Document(page_content="test", metadata={"dish_name": "糖醋排骨"}),
]
av.load_valid_dishes(docs)
test("加载有效菜品", len(av.valid_dishes) == 3, f"加载了 {len(av.valid_dishes)} 个菜品")

# 验证有效答案（只包含已知菜品）
result = av.validate_answer("推荐宫保鸡丁和西红柿炒鸡蛋", docs, "list")
test("验证有效答案", result.is_valid, f"is_valid={result.is_valid}")

# 验证答案验证功能（测试置信度）
result2 = av.validate_answer("推荐宫保鸡丁", docs, "list")
test("验证置信度", result2.confidence == 0.9, f"confidence={result2.confidence}")

# 测试没有提到菜品的情况
result3 = av.validate_answer("这是一道美味的菜", docs, "list")
test("无菜品答案", result3.confidence == 0.5, f"confidence={result3.confidence}")

# 提取菜品名
dish = av.extract_dish_from_answer("我推荐宫保鸡丁，这是一道经典川菜")
test("提取菜品名", dish == "宫保鸡丁", f"extracted={dish}")


# ═══════════════════════════════════════════════
# 测试 3: 会话管理器
# ═══════════════════════════════════════════════
print_header("模块 3: ConversationManager")

from chefmate.conversation import ConversationManager

cm = ConversationManager(max_history=3)

# 添加对话轮次
cm.add_turn("user", "推荐一个素菜")
cm.add_turn("assistant", "推荐西红柿炒鸡蛋", {"dish_name": "西红柿炒鸡蛋"})
test("添加对话轮次", len(cm.history) == 2)

# 解析指代
resolved = cm.resolve_references("那个菜怎么做")
test("解析指代", resolved.references_resolved, f"resolved={resolved.resolved}")
test("指代正确", "西红柿炒鸡蛋" in resolved.resolved, f"resolved={resolved.resolved}")

# 上下文摘要
summary = cm.get_context_summary()
test("上下文摘要", len(summary) > 0, f"summary={summary[:50]}...")

# 历史文本
history = cm.get_history_text()
test("历史文本", len(history) > 0)

# 测试历史限制
for i in range(10):
    cm.add_turn("user", f"测试问题 {i}")
    cm.add_turn("assistant", f"测试回答 {i}", {"dish_name": f"菜品{i}"})
test("历史限制", len(cm.history) <= cm.max_history * 2, f"history_len={len(cm.history)}")


# ═══════════════════════════════════════════════
# 测试 4: 反馈收集器
# ═══════════════════════════════════════════════
print_header("模块 4: FeedbackCollector")

from chefmate.feedback import FeedbackCollector
import tempfile
import shutil

# 使用临时目录
temp_dir = tempfile.mkdtemp()
fc = FeedbackCollector(feedback_dir=temp_dir)

# 收集反馈
record = fc.collect_feedback(
    query="推荐一个素菜",
    answer="推荐西红柿炒鸡蛋",
    rating="positive",
    route_type="list"
)
test("收集正面反馈", record.rating == "positive")

record2 = fc.collect_feedback(
    query="怎么做宫保鸡丁",
    answer="宫保鸡丁做法...",
    rating="negative",
    feedback_text="步骤不够详细",
    route_type="detail"
)
test("收集负面反馈", record2.rating == "negative")

# 获取统计
stats = fc.get_feedback_stats()
test("反馈统计", stats["total"] == 2, f"total={stats['total']}")
test("满意度计算", stats["satisfaction_rate"] == 50.0, f"rate={stats['satisfaction_rate']}")

# 获取负面反馈
negative = fc.get_negative_feedback()
test("获取负面反馈", len(negative) == 1)

# 改进建议
suggestions = fc.get_improvement_suggestions()
test("改进建议", len(suggestions) > 0)

# 清理
shutil.rmtree(temp_dir)


# ═══════════════════════════════════════════════
# 测试 5: 集成测试
# ═══════════════════════════════════════════════
print_header("模块 5: 集成测试")

from main import RecipeRAGSystem

system = RecipeRAGSystem()
test("系统初始化", system.config is not None)
test("会话管理器", system.conversation is not None)
test("答案验证器", system.validator is not None)
test("反馈收集器", system.feedback_collector is not None)

# 初始化系统
system.initialize_system()
system.build_knowledge_base()
test("知识库构建", system.retrieval_module is not None)
test("加载有效菜品", len(system.validator.valid_dishes) > 0, 
     f"加载了 {len(system.validator.valid_dishes)} 个菜品")

# 测试问答（会触发会话记录）
answer = system.ask_question("推荐一个素菜", stream=False)
test("问答功能", len(answer) > 0, f"answer_len={len(answer)}")

# 测试指代解析
answer2 = system.ask_question("那个菜怎么做", stream=False)
test("指代解析问答", len(answer2) > 0, f"answer_len={len(answer2)}")


# ═══════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════
print_header("测试汇总")
total = PASS + FAIL
print(f"  总计: {total}  |  通过: {PASS}  |  失败: {FAIL}")
if total > 0:
    print(f"  通过率: {PASS / total * 100:.1f}%")
print(f"{'=' * 60}")

sys.exit(0 if FAIL == 0 else 1)
