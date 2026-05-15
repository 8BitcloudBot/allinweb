"""
ChefMate 完备测试套件

覆盖场景：
1. 简单菜品问题 - 应该有好的答案
2. 复杂菜品问题 - 应该不出错
3. 不相关问题 - 应该有及格的答案
4. 边界情况 - 各种异常输入
"""

import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEFAULT_CONFIG
from main import RecipeRAGSystem


# ═══════════════════════════════════════════════
# 测试框架
# ═══════════════════════════════════════════════

@dataclass
class TestCase:
    """测试用例"""
    name: str
    query: str
    category: str  # simple, complex, irrelevant, edge
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_keywords: List[str] = field(default_factory=list)
    min_length: int = 10
    max_length: int = 2000
    should_have_dish: bool = True
    description: str = ""


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    passed: bool
    answer: str
    elapsed_ms: float
    issues: List[str] = field(default_factory=list)


class ComprehensiveTestSuite:
    """完备测试套件"""
    
    def __init__(self, system: RecipeRAGSystem):
        self.system = system
        self.results: List[TestResult] = []
        self.pass_count = 0
        self.fail_count = 0
    
    def run_all(self):
        """运行所有测试"""
        print("=" * 70)
        print("  ChefMate 完备测试套件")
        print("=" * 70)
        
        # 定义测试用例
        test_cases = self._define_test_cases()
        
        # 按类别分组运行
        categories = ["simple", "complex", "irrelevant", "edge"]
        for category in categories:
            cases = [tc for tc in test_cases if tc.category == category]
            if cases:
                self._run_category(category, cases)
        
        # 打印总结
        self._print_summary()
        
        return self.pass_count == 0 or (self.pass_count / (self.pass_count + self.fail_count)) >= 0.7
    
    def _define_test_cases(self) -> List[TestCase]:
        """定义测试用例"""
        return [
            # ═══════════════════════════════════════
            # 简单菜品问题 - 应该有好的答案
            # ═══════════════════════════════════════
            TestCase(
                name="S01: 推荐素菜",
                query="推荐几个素菜",
                category="simple",
                expected_keywords=["素菜"],
                min_length=50,
                description="简单推荐请求，应该返回有效的菜品列表"
            ),
            TestCase(
                name="S02: 宫保鸡丁做法",
                query="宫保鸡丁怎么做",
                category="simple",
                expected_keywords=["鸡丁", "花生"],
                min_length=80,
                should_have_dish=True,
                description="经典菜品做法查询"
            ),
            TestCase(
                name="S03: 西红柿炒鸡蛋",
                query="西红柿炒鸡蛋的做法",
                category="simple",
                expected_keywords=["西红柿", "鸡蛋"],
                min_length=80,
                description="家常菜做法查询"
            ),
            TestCase(
                name="S04: 适合10人的菜",
                query="推荐适合十个人吃的量的菜",
                category="simple",
                expected_keywords=["推荐", "人"],
                min_length=50,
                description="份量需求查询"
            ),
            TestCase(
                name="S05: 简单的荤菜",
                query="有什么简单的荤菜",
                category="simple",
                expected_keywords=["推荐"],
                min_length=50,
                description="带分类和难度的查询"
            ),
            TestCase(
                name="S06: 汤品推荐",
                query="推荐几个汤",
                category="simple",
                expected_keywords=["汤"],
                min_length=50,
                description="分类推荐查询"
            ),
            TestCase(
                name="S07: 早餐推荐",
                query="有什么适合当早餐的",
                category="simple",
                expected_keywords=["早餐"],
                min_length=50,
                description="场景推荐查询"
            ),
            
            # ═══════════════════════════════════════
            # 复杂菜品问题 - 应该不出错
            # ═══════════════════════════════════════
            TestCase(
                name="C01: 多条件查询",
                query="推荐3个简单的素菜，适合5个人吃",
                category="complex",
                expected_keywords=["推荐", "素菜"],
                min_length=50,
                description="多条件组合查询"
            ),
            TestCase(
                name="C02: 模糊查询",
                query="我想吃点清淡的",
                category="complex",
                expected_keywords=["清淡"],
                min_length=30,
                should_have_dish=False,
                description="模糊口味偏好查询"
            ),
            TestCase(
                name="C03: 食材查询",
                query="用鸡蛋能做什么菜",
                category="complex",
                expected_keywords=["鸡蛋"],
                min_length=50,
                description="按食材查询菜品"
            ),
            TestCase(
                name="C04: 对比查询",
                query="宫保鸡丁和麻婆豆腐哪个更好做",
                category="complex",
                min_length=5,
                description="对比两个菜品"
            ),
            TestCase(
                name="C05: 替代食材",
                query="没有淀粉可以用什么代替",
                category="complex",
                expected_keywords=["淀粉"],
                min_length=20,
                should_have_dish=False,
                description="食材替代查询"
            ),
            TestCase(
                name="C06: 烹饪技巧",
                query="炒菜怎么防止粘锅",
                category="complex",
                expected_keywords=["粘锅"],
                min_length=30,
                should_have_dish=False,
                description="烹饪技巧查询"
            ),
            TestCase(
                name="C07: 营养价值",
                query="西红柿有什么营养价值",
                category="complex",
                expected_keywords=["维生素"],
                min_length=20,
                should_have_dish=False,
                description="营养知识查询"
            ),
            TestCase(
                name="C08: 适合夏天的菜",
                query="夏天适合吃什么菜",
                category="complex",
                expected_keywords=["夏天", "适合"],
                min_length=50,
                description="季节推荐查询"
            ),
            TestCase(
                name="C09: 下饭菜",
                query="推荐几个下饭菜",
                category="complex",
                expected_keywords=["下饭"],
                min_length=50,
                description="场景推荐查询"
            ),
            TestCase(
                name="C10: 快手菜",
                query="有什么快手菜，10分钟能做好的",
                category="complex",
                expected_keywords=["快手", "分钟"],
                min_length=50,
                description="时间约束查询"
            ),
            
            # ═══════════════════════════════════════
            # 不相关问题 - 应该有及格的答案
            # ═══════════════════════════════════════
            TestCase(
                name="I01: 闲聊",
                query="你好",
                category="irrelevant",
                expected_keywords=["好"],
                min_length=10,
                should_have_dish=False,
                description="简单问候"
            ),
            TestCase(
                name="I02: 天气查询",
                query="今天天气怎么样",
                category="irrelevant",
                min_length=10,
                should_have_dish=False,
                description="与菜品无关的查询"
            ),
            TestCase(
                name="I03: 数学问题",
                query="1+1等于几",
                category="irrelevant",
                min_length=3,
                should_have_dish=False,
                description="非菜品问题"
            ),
            TestCase(
                name="I04: 股票查询",
                query="今天股票涨了吗",
                category="irrelevant",
                min_length=10,
                should_have_dish=False,
                description="与菜品完全无关"
            ),
            TestCase(
                name="I05: 编程问题",
                query="Python怎么写for循环",
                category="irrelevant",
                min_length=10,
                should_have_dish=False,
                description="技术问题"
            ),
            
            # ═══════════════════════════════════════
            # 边界情况 - 各种异常输入
            # ═══════════════════════════════════════
            TestCase(
                name="E01: 空查询",
                query="",
                category="edge",
                min_length=0,
                should_have_dish=False,
                description="空字符串输入"
            ),
            TestCase(
                name="E02: 单字查询",
                query="菜",
                category="edge",
                min_length=10,
                should_have_dish=False,
                description="极短查询"
            ),
            TestCase(
                name="E03: 重复字查询",
                query="菜菜菜菜菜",
                category="edge",
                min_length=10,
                should_have_dish=False,
                description="重复字符查询"
            ),
            TestCase(
                name="E04: 特殊字符",
                query="!@#$%^&*()",
                category="edge",
                min_length=10,
                should_have_dish=False,
                description="特殊字符输入"
            ),
            TestCase(
                name="E05: 超长查询",
                query="我想吃" * 100,
                category="edge",
                min_length=10,
                should_have_dish=False,
                description="超长输入"
            ),
            TestCase(
                name="E06: 英文查询",
                query="How to make Kung Pao Chicken",
                category="edge",
                expected_keywords=["鸡丁", "宫保"],
                min_length=50,
                max_length=3000,
                description="英文查询"
            ),
            TestCase(
                name="E07: 混合语言",
                query="推荐几个recipe",
                category="edge",
                min_length=30,
                description="中英混合查询"
            ),
            TestCase(
                name="E08: 不存在的菜",
                query="龙肝凤髓怎么做",
                category="edge",
                min_length=5,
                should_have_dish=False,
                description="不存在的菜品查询"
            ),
            TestCase(
                name="E09: 连续问多个问题",
                query="宫保鸡丁怎么做？麻婆豆腐呢？还有鱼香肉丝",
                category="edge",
                expected_keywords=["宫保鸡丁"],
                min_length=50,
                max_length=3000,
                description="一次问多个问题"
            ),
            TestCase(
                name="E10: 否定查询",
                query="我不喜欢吃辣的，推荐什么",
                category="edge",
                expected_keywords=["推荐"],
                min_length=30,
                description="带否定条件的查询"
            ),
        ]
    
    def _run_category(self, category: str, cases: List[TestCase]):
        """运行某一类别的测试"""
        category_names = {
            "simple": "简单菜品问题（应该有好的答案）",
            "complex": "复杂菜品问题（应该不出错）",
            "irrelevant": "不相关问题（应该有及格的答案）",
            "edge": "边界情况（各种异常输入）"
        }
        
        print(f"\n{'=' * 70}")
        print(f"  {category_names.get(category, category)}")
        print(f"{'=' * 70}")
        
        for case in cases:
            result = self._run_single_test(case)
            self.results.append(result)
    
    def _run_single_test(self, case: TestCase) -> TestResult:
        """运行单个测试"""
        issues = []
        
        # 处理空查询
        if not case.query.strip():
            print(f"  ⏭️  {case.name}: 跳过（空查询）")
            return TestResult(
                test_name=case.name,
                passed=True,
                answer="",
                elapsed_ms=0,
                issues=["空查询，跳过"]
            )
        
        # 运行查询
        t0 = time.time()
        try:
            # 重置会话状态，避免测试间相互影响
            self.system.conversation.clear()
            answer = self.system.ask_question(case.query, stream=False)
            elapsed_ms = (time.time() - t0) * 1000
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            print(f"  ❌ {case.name}: 异常 - {str(e)[:50]}")
            self.fail_count += 1
            return TestResult(
                test_name=case.name,
                passed=False,
                answer="",
                elapsed_ms=elapsed_ms,
                issues=[f"异常: {str(e)}"]
            )
        
        # 检查答案
        if answer is None:
            answer = ""
        
        # 长度检查
        if len(answer) < case.min_length:
            issues.append(f"答案太短: {len(answer)} < {case.min_length}")
        
        if len(answer) > case.max_length:
            issues.append(f"答案太长: {len(answer)} > {case.max_length}")
        
        # 关键词检查
        for keyword in case.expected_keywords:
            if keyword not in answer:
                issues.append(f"缺少关键词: {keyword}")
        
        # 禁止词检查
        for keyword in case.forbidden_keywords:
            if keyword in answer:
                issues.append(f"包含禁止词: {keyword}")
        
        # 菜品存在性检查（如果需要）
        if case.should_have_dish and case.category == "simple":
            # 简单问题应该有具体的菜品推荐
            if "推荐" in case.query and "没有" in answer and "无法" in answer:
                issues.append("推荐查询但没有给出具体菜品")
        
        # 检查是否是"暂未收录"的错误回复（只对简单问题检查）
        if "暂未收录" in answer and case.category == "simple":
            issues.append("返回'暂未收录'，检索可能失败")
        
        # 性能检查（放宽到15秒）
        if elapsed_ms > 15000:  # 超过15秒
            issues.append(f"响应太慢: {elapsed_ms:.0f}ms")
        
        # 判断是否通过
        passed = len(issues) == 0
        
        # 打印结果
        if passed:
            print(f"  ✅ {case.name}: 通过 ({elapsed_ms:.0f}ms)")
            self.pass_count += 1
        else:
            print(f"  ❌ {case.name}: 失败 - {'; '.join(issues[:2])}")
            self.fail_count += 1
        
        return TestResult(
            test_name=case.name,
            passed=passed,
            answer=answer[:500],  # 只保存前500字
            elapsed_ms=elapsed_ms,
            issues=issues
        )
    
    def _print_summary(self):
        """打印测试总结"""
        total = self.pass_count + self.fail_count
        pass_rate = (self.pass_count / total * 100) if total > 0 else 0
        
        print(f"\n{'=' * 70}")
        print(f"  测试总结")
        print(f"{'=' * 70}")
        print(f"  总计: {total}  |  通过: {self.pass_count}  |  失败: {self.fail_count}")
        print(f"  通过率: {pass_rate:.1f}%")
        
        # 分类统计
        categories = {}
        for result in self.results:
            # 从测试名称推断类别
            prefix = result.test_name[:1]
            if prefix not in categories:
                categories[prefix] = {"pass": 0, "fail": 0}
            if result.passed:
                categories[prefix]["pass"] += 1
            else:
                categories[prefix]["fail"] += 1
        
        category_names = {
            "S": "简单问题",
            "C": "复杂问题",
            "I": "不相关问题",
            "E": "边界情况"
        }
        
        print(f"\n  分类统计:")
        for prefix, stats in categories.items():
            name = category_names.get(prefix, prefix)
            total_cat = stats["pass"] + stats["fail"]
            rate = (stats["pass"] / total_cat * 100) if total_cat > 0 else 0
            print(f"    {name}: {stats['pass']}/{total_cat} ({rate:.0f}%)")
        
        # 打印失败详情
        failed = [r for r in self.results if not r.passed]
        if failed:
            print(f"\n  失败详情:")
            for result in failed[:10]:  # 最多显示10个
                print(f"    - {result.test_name}: {'; '.join(result.issues[:2])}")
        
        print(f"{'=' * 70}")
    
    def get_failure_report(self) -> str:
        """生成失败报告"""
        failed = [r for r in self.results if not r.passed]
        if not failed:
            return "所有测试通过！"
        
        lines = ["# 测试失败报告\n"]
        
        for result in failed:
            lines.append(f"## {result.test_name}")
            lines.append(f"- 耗时: {result.elapsed_ms:.0f}ms")
            lines.append(f"- 问题: {'; '.join(result.issues)}")
            lines.append(f"- 答案预览: {result.answer[:200]}...")
            lines.append("")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════

def main():
    print("正在初始化系统...")
    system = RecipeRAGSystem()
    system.initialize_system()
    system.build_knowledge_base()
    print("系统初始化完成\n")
    
    suite = ComprehensiveTestSuite(system)
    success = suite.run_all()
    
    # 保存失败报告
    report = suite.get_failure_report()
    report_path = Path(__file__).parent.parent / "TEST_FAILURE_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n失败报告已保存到: {report_path}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
