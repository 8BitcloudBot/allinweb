import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from graph.builder import RecipeGraphBuilder


def test_build_recipe_graph():
    content = """# 红烧猪蹄的做法
预估烹饪难度：★★★★

## 必备原料和工具

- 猪蹄
- 姜

## 计算

一份正好够 3-4 人吃。
- 猪蹄：2~3 根
- 姜 5 片

## 操作

1. 焯水去腥
2. 炒糖色
"""

    builder = RecipeGraphBuilder()
    result = builder.build("红烧猪蹄", "meat_dish", content)

    assert result["recipe"]["name"] == "红烧猪蹄"
    assert result["recipe"]["category"] == "荤菜"
    assert result["recipe"]["difficulty"] == 4
    assert result["recipe"]["servings"] == "3-4人"

    assert len(result["ingredients"]) >= 2
    ingredient_names = [i["name"] for i in result["ingredients"]]
    assert "猪蹄" in ingredient_names
    assert "姜" in ingredient_names

    assert len(result["steps"]) >= 1
    assert len(result["relations"]) >= 3


def test_parse_servings():
    builder = RecipeGraphBuilder()
    assert builder._parse_servings("一份正好够 3-4 人吃") == "3-4人"
    assert builder._parse_servings("2 人食用") == "2人"
    assert builder._parse_servings("无提及") == ""


def test_parse_difficulty():
    builder = RecipeGraphBuilder()
    assert builder._parse_difficulty("预估烹饪难度：★★★★") == 4
    assert builder._parse_difficulty("预估烹饪难度：★") == 1
    assert builder._parse_difficulty("无") == 0
