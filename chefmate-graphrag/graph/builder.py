import re
import hashlib
from typing import List, Dict, Any
from .extractor import IngredientExtractor, _guess_category


CATEGORY_MAP = {
    "meat_dish": "荤菜",
    "vegetable_dish": "素菜",
    "aquatic": "水产",
    "breakfast": "早餐",
    "condiment": "蘸料",
    "dessert": "甜品",
    "drink": "饮品",
    "soup": "汤羹",
    "staple": "主食",
    "semi-finished": "半成品",
}

CUISINE_MAP = {
    "川": "川菜", "粤": "粤菜", "鲁": "鲁菜", "苏": "苏菜",
    "闽": "闽菜", "浙": "浙菜", "湘": "湘菜", "徽": "徽菜",
}


class RecipeGraphBuilder:
    def __init__(self):
        self.extractor = IngredientExtractor()

    def build(self, dish_name: str, category_dir: str, content: str) -> Dict[str, Any]:
        recipe_id = self._gen_recipe_id(dish_name)
        category_label = CATEGORY_MAP.get(category_dir, category_dir)
        cuisine = self._guess_cuisine(dish_name, category_label)

        description = self._extract_description(content)
        difficulty = self._parse_difficulty(content)
        servings = self._parse_servings(content)

        recipe = {
            "node_id": recipe_id,
            "name": dish_name,
            "description": description,
            "cuisine_type": cuisine,
            "difficulty": difficulty,
            "servings": servings,
            "category": category_label,
            "tags": self._extract_tags(dish_name, category_label),
        }

        ingredients = self._extract_ingredients(recipe_id, content)
        steps = self._extract_steps(recipe_id, content)
        relations = self._build_relations(recipe_id, category_label, ingredients, steps)

        return {
            "recipe": recipe,
            "ingredients": ingredients,
            "steps": steps,
            "relations": relations,
        }

    def _extract_description(self, content: str) -> str:
        match = re.search(r"^# .+\n+!\[.*?\]\(.*?\)\n\n([^\n#!].+)", content, re.MULTILINE)
        if match:
            desc = match.group(1).strip()
            if "预估烹饪难度" not in desc:
                return desc[:200]
        return ""

    def _parse_difficulty(self, content: str) -> int:
        match = re.search(r"预估烹饪难度[：:]\s*(★+)", content)
        if match:
            return len(match.group(1))
        return 0

    def _parse_servings(self, content: str) -> str:
        patterns = [
            r"([\d\-~–]+)\s*[-~–]\s*([\d]+)\s*人",
            r"([\d]+)\s*人\s*食",
            r"够\s*([\d\-~–]+)\s*人",
            r"([\d]+)\s*人份",
        ]
        for p in patterns:
            m = re.search(p, content)
            if m:
                if m.lastindex and m.lastindex >= 2:
                    return f"{m.group(1)}-{m.group(2)}人"
                return f"{m.group(1)}人"
        return ""

    def _extract_tags(self, dish_name: str, category: str) -> List[str]:
        tags = [category]
        if category in ["荤菜", "水产"]:
            tags.append("肉类")
        if category in ["素菜"]:
            tags.append("素食")
        return tags

    def _guess_cuisine(self, dish_name: str, category: str) -> str:
        for key, value in CUISINE_MAP.items():
            if key in dish_name or key in category:
                return value
        return "家常菜"

    def _extract_ingredients(self, recipe_id: str, content: str) -> List[Dict[str, Any]]:
        raw = self.extractor.extract(content)
        for ing in raw:
            ing["recipe_id"] = recipe_id
        return raw

    def _extract_steps(self, recipe_id: str, content: str) -> List[Dict[str, Any]]:
        steps = []
        pos = content.find("## 操作")
        if pos == -1:
            return steps

        section = content[pos:]
        end_pos = section.find("## 附加内容")
        if end_pos == -1:
            end_pos = len(section)
        section = section[:end_pos]

        current_subsection = ""
        step_number = 0

        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("### "):
                current_subsection = line[4:].strip()
                continue
            if re.match(r"^\d+\.\s", line):
                step_number += 1
                text = re.sub(r"^\d+\.\s*", "", line).strip()
                steps.append({
                    "node_id": self._gen_step_id(recipe_id, step_number),
                    "recipe_id": recipe_id,
                    "name": text[:50] if len(text) > 50 else text,
                    "description": text,
                    "step_number": step_number,
                    "subsection": current_subsection,
                })

        return steps

    def _build_relations(self, recipe_id: str, category_label: str,
                         ingredients: List[Dict], steps: List[Dict]) -> List[Dict]:
        relations = []
        category_id = self._gen_category_id(category_label)

        relations.append({
            "start": recipe_id,
            "end": category_id,
            "type": "BELONGS_TO_CATEGORY",
            "properties": {}
        })

        for ing in ingredients:
            relations.append({
                "start": recipe_id,
                "end": ing["node_id"],
                "type": "REQUIRES",
                "properties": {
                    "amount": ing.get("amount", ""),
                    "unit": ing.get("unit", ""),
                }
            })
            ing_cat = _guess_category(ing["name"])
            if ing_cat != "其他":
                relations.append({
                    "start": ing["node_id"],
                    "end": self._gen_category_id(ing_cat),
                    "type": "BELONGS_TO_CATEGORY",
                    "properties": {}
                })

        for step in steps:
            relations.append({
                "start": recipe_id,
                "end": step["node_id"],
                "type": "CONTAINS_STEP",
                "properties": {"stepOrder": step["step_number"]}
            })

        return relations

    def _gen_recipe_id(self, name: str) -> str:
        digest = hashlib.md5(f"recipe:{name}".encode()).hexdigest()[:12]
        return f"rec_{digest}"

    def _gen_category_id(self, name: str) -> str:
        digest = hashlib.md5(f"category:{name}".encode()).hexdigest()[:12]
        return f"cat_{digest}"

    def _gen_step_id(self, recipe_id: str, step_num: int) -> str:
        digest = hashlib.md5(f"step:{recipe_id}:{step_num}".encode()).hexdigest()[:12]
        return f"stp_{digest}"
