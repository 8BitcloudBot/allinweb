import logging
from typing import List, Dict, Any
from neo4j import GraphDatabase
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

logger = logging.getLogger(__name__)


class GraphDataPreparationModule:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None
        self.recipes: List[Dict] = []
        self.ingredients: List[Dict] = []
        self.steps: List[Dict] = []
        self.documents: List[Document] = []
        self.chunks: List[Document] = []
        self._connect()

    def _connect(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        logger.info(f"Connected to Neo4j: {self.uri}")

    def load_graph_data(self):
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (r:Recipe)
                OPTIONAL MATCH (r)-[:BELONGS_TO_CATEGORY]->(c:Category)
                RETURN r.nodeId as nodeId, r.name as name,
                       properties(r) as props,
                       collect(DISTINCT c.name) as categories
                ORDER BY r.nodeId
            """)
            self.recipes = []
            for record in result:
                props = dict(record["props"])
                categories = record["categories"]
                props["category"] = categories[0] if categories else props.get("category", "")
                props["all_categories"] = categories
                self.recipes.append({
                    "node_id": record["nodeId"],
                    "name": record["name"],
                    "properties": props,
                })
            logger.info(f"Loaded {len(self.recipes)} recipes")

            result = session.run("MATCH (i:Ingredient) RETURN i.nodeId as nodeId, i.name as name, properties(i) as props")
            self.ingredients = [{"node_id": r["nodeId"], "name": r["name"], "properties": dict(r["props"])} for r in result]
            logger.info(f"Loaded {len(self.ingredients)} ingredients")

            result = session.run("MATCH (s:CookingStep) RETURN s.nodeId as nodeId, s.name as name, properties(s) as props")
            self.steps = [{"node_id": r["nodeId"], "name": r["name"], "properties": dict(r["props"])} for r in result]
            logger.info(f"Loaded {len(self.steps)} cooking steps")

    def build_recipe_documents(self) -> List[Document]:
        logger.info("Building recipe documents from graph data...")
        documents = []

        with self.driver.session(database=self.database) as session:
            for recipe in self.recipes:
                try:
                    rid = recipe["node_id"]
                    rname = recipe["name"]
                    props = recipe["properties"]

                    result = session.run("""
                        MATCH (r:Recipe {nodeId: $rid})-[req:REQUIRES]->(i:Ingredient)
                        RETURN i.name as name, i.category as category,
                               req.amount as amount, req.unit as unit
                        ORDER BY i.name
                    """, rid=rid)
                    ingredients_info = []
                    for row in result:
                        text = row["name"]
                        amt = row.get("amount")
                        unt = row.get("unit")
                        if amt and unt:
                            text += f"({amt}{unt})"
                        ingredients_info.append(text)

                    result = session.run("""
                        MATCH (r:Recipe {nodeId: $rid})-[c:CONTAINS_STEP]->(s:CookingStep)
                        RETURN s.name as name, s.description as description,
                               s.stepNumber as stepNumber,
                               c.stepOrder as stepOrder
                        ORDER BY COALESCE(c.stepOrder, s.stepNumber, 999)
                    """, rid=rid)
                    steps_info = []
                    for row in result:
                        step_text = f"步骤: {row['name']}"
                        desc = row.get("description")
                        if desc:
                            step_text += f"\n描述: {desc}"
                        steps_info.append(step_text)

                    content_parts = [f"# {rname}"]
                    desc = props.get("description")
                    if desc:
                        content_parts.append(f"\n## 菜品描述\n{desc}")
                    cuisine = props.get("cuisineType")
                    if cuisine:
                        content_parts.append(f"\n菜系: {cuisine}")
                    difficulty = props.get("difficulty")
                    if difficulty:
                        content_parts.append(f"难度: {'★' * difficulty}")
                    servings = props.get("servings")
                    if servings:
                        content_parts.append(f"份量: {servings}")

                    if ingredients_info:
                        content_parts.append("\n## 所需食材")
                        for i, ing in enumerate(ingredients_info, 1):
                            content_parts.append(f"{i}. {ing}")

                    if steps_info:
                        content_parts.append("\n## 制作步骤")
                        for i, step in enumerate(steps_info, 1):
                            content_parts.append(f"\n### 第{i}步\n{step}")

                    full_content = "\n".join(content_parts)

                    doc = Document(
                        page_content=full_content,
                        metadata={
                            "node_id": rid,
                            "recipe_name": rname,
                            "node_type": "Recipe",
                            "category": props.get("category", ""),
                            "cuisine_type": cuisine or "",
                            "difficulty": difficulty or 0,
                            "servings": servings or "",
                            "ingredients_count": len(ingredients_info),
                            "steps_count": len(steps_info),
                            "doc_type": "recipe",
                            "content_length": len(full_content),
                        }
                    )
                    documents.append(doc)

                except Exception as e:
                    logger.warning(f"Failed to build doc for {rname}: {e}")

        self.documents = documents
        logger.info(f"Built {len(documents)} recipe documents")
        return documents

    def chunk_documents(self, chunk_size: int = 500, chunk_overlap: int = 50) -> List[Document]:
        logger.info(f"Chunking with size={chunk_size}, overlap={chunk_overlap}")

        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
        )

        chunks = []
        chunk_id = 0
        for doc in self.documents:
            sub_chunks = splitter.split_text(doc.page_content)
            for i, sc in enumerate(sub_chunks):
                chunks.append(Document(
                    page_content=sc.page_content,
                    metadata={
                        **doc.metadata,
                        "chunk_id": f"{doc.metadata['node_id']}_chunk_{chunk_id}",
                        "parent_id": doc.metadata["node_id"],
                        "chunk_index": i,
                        "total_chunks": len(sub_chunks),
                        "chunk_size": len(sc.page_content),
                        "doc_type": "chunk",
                    }
                ))
                chunk_id += 1

        self.chunks = chunks
        logger.info(f"Produced {len(chunks)} chunks from {len(self.documents)} docs")
        return chunks

    def get_valid_dish_names(self) -> List[str]:
        return [r["name"] for r in self.recipes]

    def get_statistics(self) -> Dict[str, Any]:
        stats = {
            "total_recipes": len(self.recipes),
            "total_ingredients": len(self.ingredients),
            "total_cooking_steps": len(self.steps),
            "total_documents": len(self.documents),
            "total_chunks": len(self.chunks),
        }
        if self.documents:
            categories = {}
            for doc in self.documents:
                cat = doc.metadata.get("category", "未知")
                categories[cat] = categories.get(cat, 0) + 1
            stats["categories"] = categories
        return stats

    def close(self):
        if self.driver:
            self.driver.close()
