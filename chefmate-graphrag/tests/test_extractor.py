import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from graph.extractor import IngredientExtractor


def test_extract_ingredients_from_simple_recipe():
    content = """## 必备原料和工具

- 猪蹄
- 香叶
- 姜
- 老抽

## 计算

- 猪蹄：2~3 根
- 香叶 2 片
- 姜 5 片
"""
    extractor = IngredientExtractor()
    ingredients = extractor.extract(content)

    assert len(ingredients) >= 3
    names = [i["name"] for i in ingredients]
    assert "猪蹄" in names
    assert "香叶" in names
    assert "姜" in names


def test_extract_ingredients_with_measurements():
    content = """## 必备原料和工具

- 猪蹄
- 食用油
- 冰糖
- 料酒
- 盐

## 计算

- 猪蹄：2~3 根
- 食用油：30ml
- 冰糖 7-8 粒
- 料酒 30 ml
- 盐 8 克
"""
    extractor = IngredientExtractor()
    ingredients = extractor.extract(content)

    pork = next((i for i in ingredients if i["name"] == "猪蹄"), None)
    assert pork is not None
    assert pork.get("amount") == "2~3"
    assert pork.get("unit") == "根"


def test_extract_ingredients_skips_tools():
    content = """## 必备原料和工具

- 炒锅（自带锅盖）
- 老抽
"""
    extractor = IngredientExtractor()
    ingredients = extractor.extract(content)

    names = [i["name"] for i in ingredients]
    assert "老抽" in names
    assert "炒锅" not in names


def test_extract_comma_separated_ingredients():
    content = """## 必备原料和工具

- 花椒，香叶，香果，干线椒，大蒜，大葱
"""
    extractor = IngredientExtractor()
    ingredients = extractor.extract(content)

    names = [i["name"] for i in ingredients]
    assert "花椒" in names
    assert "香叶" in names
    assert "香果" in names
