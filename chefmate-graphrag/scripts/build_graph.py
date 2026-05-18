#!/usr/bin/env python3
"""Build Neo4j knowledge graph from 362 .md recipe files."""

import os
import sys
import glob
import hashlib
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import DEFAULT_CONFIG
from graph.builder import RecipeGraphBuilder
from graph.importer import Neo4jImporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "meat_dish": "荤菜", "vegetable_dish": "素菜", "aquatic": "水产",
    "breakfast": "早餐", "condiment": "蘸料", "dessert": "甜品",
    "drink": "饮品", "soup": "汤羹", "staple": "主食",
    "semi-finished": "半成品",
}


def main():
    config = DEFAULT_CONFIG
    data_path = config.data_path
    if not os.path.isdir(data_path):
        data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    data_path = os.path.abspath(data_path)

    logger.info(f"Data path: {data_path}")
    logger.info(f"Neo4j: {config.neo4j_uri}")

    importer = Neo4jImporter(
        config.neo4j_uri, config.neo4j_user,
        config.neo4j_password, config.neo4j_database
    )

    response = input("Clear Neo4j and rebuild graph? (y/N): ").strip().lower()
    if response != "y":
        print("Cancelled")
        importer.close()
        return

    importer.clear_all()

    category_nodes = []
    for dir_name, label in CATEGORY_LABELS.items():
        digest = hashlib.md5(f"category:{label}".encode()).hexdigest()[:12]
        category_nodes.append({"node_id": f"cat_{digest}", "name": label})

    ingredient_cats = ["肉类", "蔬菜", "水产", "豆制品", "蛋奶", "主食", "调味料", "干货"]
    for cat in ingredient_cats:
        if not any(c["name"] == cat for c in category_nodes):
            digest = hashlib.md5(f"category:{cat}".encode()).hexdigest()[:12]
            category_nodes.append({"node_id": f"cat_{digest}", "name": cat})

    importer.create_category_nodes(category_nodes)
    logger.info(f"Created {len(category_nodes)} Category nodes")

    md_files = glob.glob(os.path.join(data_path, "**/*.md"), recursive=True)
    md_files = [f for f in md_files if not os.path.basename(f).startswith("._")]
    md_files = [f for f in md_files if "template" not in os.path.dirname(f)]
    logger.info(f"Found {len(md_files)} recipe files")

    builder = RecipeGraphBuilder()
    success_count = 0
    error_count = 0

    for filepath in md_files:
        try:
            rel_path = os.path.relpath(filepath, data_path)
            parts = Path(rel_path).parts
            category_dir = parts[0] if len(parts) > 1 else "unknown"

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            dish_name = Path(filepath).stem
            if dish_name.startswith("._"):
                continue

            graph_data = builder.build(dish_name, category_dir, content)
            importer.import_recipe(graph_data)
            success_count += 1

            if success_count % 50 == 0:
                logger.info(f"Progress: {success_count}/{len(md_files)}")

        except Exception as e:
            error_count += 1
            logger.warning(f"Failed {filepath}: {e}")

    logger.info(f"Import complete: {success_count} success, {error_count} failed")

    stats = importer.get_statistics()
    logger.info(f"Graph stats: {stats}")

    with importer.driver.session(database=config.neo4j_database) as session:
        result = session.run("MATCH (r:Recipe) RETURN count(r) as cnt")
        logger.info(f"Recipe nodes: {result.single()['cnt']}")

        result = session.run("""
            MATCH (r:Recipe {name: '宫保鸡丁'})-[rel:REQUIRES]->(i:Ingredient)
            RETURN i.name as ingredient, rel.amount as amount, rel.unit as unit
        """)
        ingredients = list(result)
        if ingredients:
            logger.info("Verification - 宫保鸡丁 ingredients:")
            for row in ingredients:
                logger.info(f"  {row['ingredient']}: {row.get('amount', '')} {row.get('unit', '')}")

    # Post-processing: build SIMILAR_TO relations (shared ingredients >= 3)
    logger.info("Building SIMILAR_TO relations...")
    with importer.driver.session(database=config.neo4j_database) as session:
        session.run("""
            MATCH (r1:Recipe)-[:REQUIRES]->(i:Ingredient)<-[:REQUIRES]-(r2:Recipe)
            WHERE r1.nodeId < r2.nodeId
            WITH r1, r2, count(i) as shared
            WHERE shared >= 3
            MERGE (r1)-[r:SIMILAR_TO]->(r2)
            SET r.shared_ingredients = shared
        """)
        result = session.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) as cnt")
        logger.info(f"Created {result.single()['cnt']} SIMILAR_TO relations")

    # Post-processing: build SUBSTITUTE_FOR relations
    logger.info("Building SUBSTITUTE_FOR relations...")
    SUBSTITUTE_MAP = {
        "马铃薯": ["山药", "芋头", "红薯"],
        "猪五花肉": ["牛腩", "鸡腿肉", "羊排"],
        "生抽": ["酱油", "味极鲜"],
        "白糖": ["冰糖", "蜂蜜"],
        "料酒": ["啤酒", "黄酒"],
        "淀粉": ["面粉", "生粉"],
        "小葱": ["大葱", "洋葱"],
        "鸡蛋": ["鸭蛋"],
    }
    sub_count = 0
    with importer.driver.session(database=config.neo4j_database) as session:
        for original, alts in SUBSTITUTE_MAP.items():
            for alt in alts:
                result = session.run("""
                    MATCH (i1:Ingredient) WHERE i1.name CONTAINS $orig
                    MATCH (i2:Ingredient) WHERE i2.name CONTAINS $alt
                    MERGE (i1)-[:SUBSTITUTE_FOR]->(i2)
                """, orig=original, alt=alt)
                sub_count += 1
    logger.info(f"Applied {sub_count} SUBSTITUTE_FOR rules")

    importer.close()
    logger.info("Graph build complete")


if __name__ == "__main__":
    main()
