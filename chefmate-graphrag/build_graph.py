"""一次性脚本：将 data/<category>/*.md 菜谱灌入 Neo4j 知识图谱。

用法（在 chefmate-graphrag 目录下）：
    python build_graph.py [--data-dir data] [--clear]

--clear 会先清空 Neo4j 再导入。
依赖 config.py 中的 NEO4J 配置（从 .env 或 docs/key.md 读取）。
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_graph")

from config import DEFAULT_CONFIG
from graph.builder import RecipeGraphBuilder
from graph.importer import Neo4jImporter


def iter_recipes(data_dir: Path):
    """遍历 data/<category>/<dish>.md 或 data/<category>/<dish>/<dish>.md"""
    for category_dir in sorted(data_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        cat = category_dir.name
        # 形式1: data/<cat>/<dish>.md
        for md in sorted(category_dir.glob("*.md")):
            yield cat, md.stem, md.read_text(encoding="utf-8")
        # 形式2: data/<cat>/<dish>/<dish>.md
        for dish_dir in sorted(category_dir.iterdir()):
            if dish_dir.is_dir():
                for md in sorted(dish_dir.glob("*.md")):
                    yield cat, dish_dir.name, md.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--clear", action="store_true", help="导入前清空 Neo4j")
    args = parser.parse_args()

    cfg = DEFAULT_CONFIG
    uri = cfg.neo4j_uri
    user = cfg.neo4j_user
    password = cfg.neo4j_password
    logger.info(f"Neo4j -> {uri} user={user}")

    builder = RecipeGraphBuilder()
    importer = Neo4jImporter(uri, user, password, database=cfg.neo4j_database)

    if args.clear:
        logger.info("清空已有图谱...")
        importer.clear_all()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"数据目录不存在: {data_dir}")
        sys.exit(1)

    total = 0
    for cat, dish, content in iter_recipes(data_dir):
        try:
            structured = builder.build(dish, cat, content)
            importer.import_recipe(structured)
            total += 1
            if total % 50 == 0:
                logger.info(f"已导入 {total} 道菜...")
        except Exception as e:
            logger.warning(f"导入失败 [{cat}/{dish}]: {e}")

    stats = importer.get_statistics()
    logger.info(f"导入完成，共 {total} 道菜。图谱统计: {stats}")
    importer.close()


if __name__ == "__main__":
    main()
