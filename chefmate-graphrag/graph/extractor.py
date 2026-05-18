import re
import hashlib
from typing import List, Dict, Any


TOOL_KEYWORDS = [
    "锅", "铲", "刀", "砧板", "碗", "盘", "勺", "筷", "烤箱",
    "微波炉", "蒸锅", "高压锅", "料理机", "搅拌机", "打蛋器",
    "烤盘", "模具", "纱布", "滤网", "擀面杖", "油纸", "锡纸",
    "保鲜膜", "厨房纸", "温度计", "秤", "量杯", "炒锅"
]

INGREDIENT_BLACKLIST = {
    "水", "开水", "冷水", "热水", "清水", "温水", "沸水",
    "食用油", "盐", "糖", "白砂糖", "白糖", "冰糖",
    "油", "盐油", "适量", "少许",
}

CATEGORY_INGREDIENTS = {
    "肉类": ["猪蹄", "猪肉", "牛肉", "羊肉", "鸡肉", "鸭肉", "鸡腿", "鸡翅", "排骨", "五花肉", "里脊肉", "肉末", "肉馅"],
    "蔬菜": ["茄子", "土豆", "尖椒", "青椒", "菜椒", "番茄", "西红柿", "黄瓜", "白菜", "萝卜", "胡萝卜", "玉米", "豆角", "西兰花", "菜花", "冬瓜", "南瓜", "苦瓜", "丝瓜", "韭菜", "菠菜", "芹菜", "生菜", "小白菜", "油菜", "油麦菜", "大葱", "小葱", "葱", "洋葱", "姜", "蒜", "大蒜", "香菜"],
    "水产": ["鱼", "虾", "蟹", "贝", "蛤", "海带", "紫菜", "虾仁", "干贝", "鱿鱼", "鲍鱼", "带鱼", "三文鱼", "虾皮"],
    "豆制品": ["豆腐", "豆浆", "豆皮", "腐竹", "千张", "豆干", "豆腐乳"],
    "蛋奶": ["鸡蛋", "鸭蛋", "牛奶", "奶油", "黄油", "芝士", "奶酪", "蛋"],
    "主食": ["米饭", "面条", "面粉", "面包", "馒头", "饺子", "粉条", "粉丝", "淀粉", "米"],
    "调味料": ["老抽", "生抽", "料酒", "蚝油", "豆瓣酱", "醋", "味极鲜", "花椒", "八角", "桂皮", "香叶", "孜然", "胡椒", "辣椒", "干线椒", "香果", "豆豉", "郫县豆瓣酱", "甜面酱", "番茄酱", "番茄沙司", "芝麻", "香油", "芝麻油", "鸡精", "味精", "干辣椒", "花椒粉", "花椒油", "白胡椒粉", "黑胡椒粉"],
    "干货": ["木耳", "银耳", "香菇", "红枣", "枸杞", "莲子", "百合", "桂圆", "花生"],
}


def _guess_category(name: str) -> str:
    for cat, items in CATEGORY_INGREDIENTS.items():
        if name in items:
            return cat
    return "其他"


class IngredientExtractor:
    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

    def extract(self, content: str) -> List[Dict[str, Any]]:
        raw_names = self._extract_names(content)
        measurements = self._extract_measurements(content)
        ingredients = []

        for name in raw_names:
            if self._is_tool(name):
                continue
            if name in INGREDIENT_BLACKLIST:
                continue

            entry = measurements.get(name, {})
            ingredients.append({
                "name": name,
                "amount": entry.get("amount", ""),
                "unit": entry.get("unit", ""),
                "category": _guess_category(name),
                "node_id": self._gen_id(name),
            })

        return ingredients

    def _extract_names(self, content: str) -> List[str]:
        names = []
        start_marker = "## 必备原料和工具"
        end_markers = ["## 计算", "## 操作"]

        pos = content.find(start_marker)
        if pos == -1:
            return names

        section = content[pos:]
        end_pos = len(section)
        for m in end_markers:
            idx = section.find(m, len(start_marker))
            if idx != -1 and idx < end_pos:
                end_pos = idx
        section = section[:end_pos]

        for line in section.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ "):
                item = stripped[2:].strip()
                if "，" in item or "," in item:
                    parts = re.split(r"[，,]", item)
                else:
                    parts = [item]

                for part in parts:
                    part = part.strip()
                    part = re.sub(r'[（(].*?[）)]', '', part).strip()
                    part = re.sub(r'^[#*`]+|[#*`]+$', '', part).strip()
                    part = re.sub(r'^(必备[：:]|主料[：:]|辅料[：:]|可选[：:]|进阶[：:])', '', part).strip()
                    if part and part not in names and len(part) >= 1:
                        names.append(part)

        return names

    def _extract_measurements(self, content: str) -> Dict[str, Dict[str, str]]:
        measurements = {}

        pos = content.find("## 计算")
        if pos == -1:
            return measurements

        section = content[pos:]
        end_pos = section.find("## 操作")
        if end_pos != -1:
            section = section[:end_pos]

        for line in section.split("\n"):
            stripped = line.strip()
            if not (stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ ")):
                continue
            item = stripped[2:].strip()

            match = re.match(r"(.+?)[：:](.+)", item)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
            else:
                parts = item.rsplit(" ", 1)
                if len(parts) >= 2 and re.match(r"\d", parts[1]):
                    name = parts[0].strip()
                    value = parts[1].strip()
                else:
                    continue

            name = re.sub(r"[（(].*?[）)]", "", name).strip()
            amount_match = re.match(r"([\d~\-–.]+)", value)
            amount = amount_match.group(1) if amount_match else ""
            unit_match = re.search(r"[\d~\-–.]+\s*([a-zA-Z\u4e00-\u9fff]+)$", value)
            unit = unit_match.group(1) if unit_match else ""

            measurements[name] = {"amount": amount, "unit": unit}

        return measurements

    def _is_tool(self, name: str) -> bool:
        return any(tool in name for tool in TOOL_KEYWORDS)

    def _gen_id(self, name: str) -> str:
        digest = hashlib.md5(f"ingredient:{name}".encode()).hexdigest()[:12]
        return f"ing_{digest}"
