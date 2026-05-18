import logging
from typing import List, Dict, Any
from neo4j import GraphDatabase
from .schema import VALID_RELATION_TYPES

logger = logging.getLogger(__name__)


class Neo4jImporter:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self._init_indexes()

    def _init_indexes(self):
        with self.driver.session(database=self.database) as session:
            for label in ["Recipe", "Ingredient", "Category", "CookingStep"]:
                session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.nodeId)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Recipe) ON (n.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Ingredient) ON (n.name)")

    def clear_all(self):
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def create_category_nodes(self, categories: List[Dict[str, str]]):
        with self.driver.session(database=self.database) as session:
            for cat in categories:
                session.run("""
                    MERGE (c:Category {nodeId: $node_id})
                    SET c.name = $name
                """, node_id=cat["node_id"], name=cat["name"])

    def import_recipe(self, data: Dict[str, Any]):
        with self.driver.session(database=self.database) as session:
            def _do_import(tx):
                r = data["recipe"]
                tx.run("""
                    MERGE (rec:Recipe {nodeId: $node_id})
                    SET rec.name = $name,
                        rec.description = $description,
                        rec.cuisineType = $cuisine_type,
                        rec.difficulty = $difficulty,
                        rec.prepTime = $prep_time,
                        rec.cookTime = $cook_time,
                        rec.servings = $servings,
                        rec.category = $category,
                        rec.tags = $tags
                """,
                    node_id=r["node_id"],
                    name=r["name"],
                    description=r.get("description", ""),
                    cuisine_type=r.get("cuisine_type", ""),
                    difficulty=r.get("difficulty", 0),
                    prep_time=r.get("prep_time", ""),
                    cook_time=r.get("cook_time", ""),
                    servings=r.get("servings", ""),
                    category=r.get("category", ""),
                    tags=r.get("tags", [])
                )

                for ing in data.get("ingredients", []):
                    tx.run("""
                        MERGE (i:Ingredient {nodeId: $node_id})
                        SET i.name = $name, i.category = $category
                    """,
                        node_id=ing["node_id"],
                        name=ing["name"],
                        category=ing.get("category", "")
                    )

                for step in data.get("steps", []):
                    tx.run("""
                        MERGE (s:CookingStep {nodeId: $node_id})
                        SET s.name = $name,
                            s.description = $description,
                            s.stepNumber = $step_number
                    """,
                        node_id=step["node_id"],
                        name=step["name"],
                        description=step.get("description", ""),
                        step_number=step.get("step_number", 0)
                    )

                for rel in data.get("relations", []):
                    rel_type = rel["type"]
                    if rel_type not in VALID_RELATION_TYPES:
                        raise ValueError(f"Invalid relation type: {rel_type}")
                    props = rel.get("properties", {})
                    if props:
                        set_clauses = ", ".join(f"r.{k} = ${k}" for k in props)
                        tx.run(f"""
                            MATCH (a {{nodeId: $start_id}})
                            MATCH (b {{nodeId: $end_id}})
                            MERGE (a)-[r:{rel_type}]->(b)
                            SET {set_clauses}
                        """,
                            start_id=rel["start"],
                            end_id=rel["end"],
                            **props
                        )
                    else:
                        tx.run(f"""
                            MATCH (a {{nodeId: $start_id}})
                            MATCH (b {{nodeId: $end_id}})
                            MERGE (a)-[r:{rel_type}]->(b)
                        """,
                            start_id=rel["start"],
                            end_id=rel["end"]
                        )

            session.execute_write(_do_import)

    def count_nodes(self) -> Dict[str, int]:
        counts = {}
        with self.driver.session(database=self.database) as session:
            for label in ["Recipe", "Ingredient", "Category", "CookingStep"]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as cnt")
                counts[label] = result.single()["cnt"]
        return counts

    def get_statistics(self) -> Dict[str, Any]:
        with self.driver.session(database=self.database) as session:
            node_counts = self.count_nodes()
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as cnt")
            rel_count = rel_result.single()["cnt"]
            return {"nodes": node_counts, "relationships": rel_count}

    def close(self):
        if self.driver:
            self.driver.close()
