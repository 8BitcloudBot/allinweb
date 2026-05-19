import json
import logging
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    ENTITY_RELATION = "entity_relation"
    MULTI_HOP = "multi_hop"
    SUBGRAPH = "subgraph"
    PATH_FINDING = "path_finding"
    CLUSTERING = "clustering"


@dataclass
class GraphQuery:
    query_type: QueryType
    source_entities: List[str]
    target_entities: List[str] = None
    relation_types: List[str] = None
    max_depth: int = 2
    max_nodes: int = 50
    constraints: Dict[str, Any] = None

    def __post_init__(self):
        if self.target_entities is None:
            self.target_entities = []
        if self.relation_types is None:
            self.relation_types = []
        if self.constraints is None:
            self.constraints = {}


class GraphRAGRetrieval:
    def __init__(self, config, llm_client):
        self.config = config
        self.llm_client = llm_client
        self.driver = None
        self._connected = False
        self._failure_count = 0
        self._last_failure_time = 0.0

    def initialize(self):
        logger.info("Initializing GraphRAG retrieval...")
        self._try_connect()

    def _try_connect(self):
        try:
            self.driver = GraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password),
            )
            self.driver.verify_connectivity()
            self._connected = True
            self._failure_count = 0
            logger.info("Neo4j connection established")
        except Exception as e:
            self._connected = False
            logger.warning(f"Neo4j connection failed: {e}")

    def _ensure_connected(self):
        if not self._connected or not self.driver:
            self._try_connect()
            return
        try:
            self.driver.verify_connectivity()
        except Exception:
            logger.warning("Neo4j connection lost, reconnecting...")
            try:
                self.driver.close()
            except Exception:
                pass
            self._try_connect()

    def understand_graph_query(self, query: str) -> GraphQuery:
        # Extract conversation context if present
        ctx_match = re.search(r'\[对话上下文\]\s*(.*?)$', query, re.DOTALL)
        context_section = ""
        clean_query = query
        if ctx_match:
            context_section = ctx_match.group(1).strip()
            clean_query = query[:ctx_match.start()].strip()

        prompt = f"""分析这个中文烹饪查询，用于 Neo4j 图遍历。
重要：图中所有实体名称都是中文，必须返回中文实体名。

图结构:
- Recipe: name(菜名), cuisineType(菜系), category, difficulty, servings
- Ingredient: name(食材名), category (大类如"蔬菜""肉类""调料")
- Category: name(分类名)
- 关系: REQUIRES (菜→食材), BELONGS_TO_CATEGORY (菜→分类), CONTAINS_STEP (菜→步骤)

当前查询: {clean_query}
{f'对话上下文: {context_section}' if context_section else ''}

任务:
1. query_type: multi_hop/entity_relation/subgraph/path_finding/clustering
   - "X配什么Y"或"X搭配什么Y" → multi_hop
   - "什么菜用了X和Y"或"X和Y一起做的菜" → entity_relation (intersection)
   - "X能替代什么"或"代替X" → multi_hop
2. source_entities: 必须是中文完整词。不要截取、合并或翻译。
   - 追问（如"鸡肉和鱼肉呢？"）→ source_entities=["鸡肉","鱼肉"]
   - 多实体查询 → 分别列出，如 source_entities=["牛肉","土豆"]
3. target_entities: 查询中的大类词，用于过滤无关路径。
   - "配什么蔬菜" → ["蔬菜"]
   - "和什么肉类" → ["肉类"]
   - "什么汤" → ["汤羹"]
   - 无明确大类 → []
4. relation_types: 从 ["REQUIRES","BELONGS_TO_CATEGORY","CONTAINS_STEP"] 选择
5. max_depth: 搭配/反向查询=2, 复杂=3
6. constraints: 属性过滤，无则 {{}}

示例:
- "鸡肉配什么蔬菜" → {{"query_type":"multi_hop","source_entities":["鸡肉"],"target_entities":["蔬菜"],"relation_types":["REQUIRES"],"max_depth":2}}
- "什么菜用了牛肉和土豆" → {{"query_type":"entity_relation","source_entities":["牛肉","土豆"],"target_entities":[],"relation_types":["REQUIRES"],"max_depth":2}}
- "土豆能替代什么食材" → {{"query_type":"multi_hop","source_entities":["土豆"],"target_entities":["食材"],"relation_types":["REQUIRES"],"max_depth":2}}

返回纯JSON（无markdown）:
{{"query_type":"...","source_entities":["..."],"target_entities":[],"relation_types":["..."],"max_depth":2,"constraints":{{}}}}"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=800,
            )
            text = response.choices[0].message.content.strip()
            text = text[text.find("{"):text.rfind("}") + 1]
            result = json.loads(text)
            return GraphQuery(
                query_type=QueryType(result.get("query_type", "subgraph")),
                source_entities=result.get("source_entities", []),
                target_entities=result.get("target_entities", []),
                relation_types=result.get("relation_types", []),
                max_depth=result.get("max_depth", 2),
                max_nodes=50,
                constraints=result.get("constraints", {}),
            )
        except Exception as e:
            logger.error(f"Graph query understanding failed: {e}")
            return GraphQuery(
                query_type=QueryType.SUBGRAPH,
                source_entities=[query],
                max_depth=2,
            )

    def multi_hop_traversal(self, gq: GraphQuery) -> List[Dict]:
        paths = []
        if not self._connected:
            self._ensure_connected()
        if not self._connected:
            return paths

        try:
            with self.driver.session() as session:
                target_filter = ""
                params = {
                    "source_entities": gq.source_entities,
                    "relation_types": gq.relation_types,
                }
                if gq.target_entities:
                    target_filter = """
                    AND ANY(kw IN $target_keywords WHERE
                        target.name CONTAINS kw
                        OR kw CONTAINS target.name
                        OR (target:Category AND target.name CONTAINS kw)
                        OR (target:Ingredient AND target.category CONTAINS kw)
                        OR (target:Recipe AND (target.cuisineType CONTAINS kw OR target.category CONTAINS kw))
                    )"""
                    params["target_keywords"] = gq.target_entities

                # Prefer Recipe + Ingredient nodes. Expand search terms for common aliases
                search_terms = []
                ALIAS_MAP = {"调料": "调味料", "调味": "调味料", "香菜": "芫荽", "粉": "粉条"}
                for se in gq.source_entities:
                    search_terms.append(se.strip())
                    if se.strip() in ALIAS_MAP:
                        search_terms.append(ALIAS_MAP[se.strip()])

                params["search_terms"] = search_terms

                cypher = f"""
                UNWIND $search_terms as source_name
                MATCH (source)
                WHERE (source:Recipe OR source:Ingredient OR source:Category)
                  AND (source.name CONTAINS source_name OR source.nodeId = source_name)
                WITH source, source_name
                MATCH path = (source)-[*1..{gq.max_depth}]-(target)
                WHERE NOT source = target{target_filter}
                WITH DISTINCT path, source, target,
                     length(path) as plen,
                     nodes(path) as pnodes,
                     relationships(path) as rels
                WITH path, source, target, plen, pnodes, rels,
                     (1.0 / plen) +
                     (CASE WHEN ANY(r IN rels WHERE type(r) IN $relation_types) THEN 0.3 ELSE 0.0 END) as relevance
                ORDER BY relevance DESC
                LIMIT 30
                RETURN path, source, target, plen, pnodes, rels, relevance
                """
                result = session.run(cypher, params)
                for record in result:
                    path_nodes = []
                    for node in record["pnodes"]:
                        path_nodes.append({
                            "id": node.get("nodeId", ""),
                            "name": node.get("name", ""),
                            "labels": list(node.labels),
                        })
                    relationships = []
                    for rel in record["rels"]:
                        relationships.append({
                            "type": type(rel).__name__,
                        })
                    paths.append({
                        "nodes": path_nodes,
                        "relationships": relationships,
                        "path_length": record["plen"],
                        "relevance_score": record["relevance"],
                        "path_type": "multi_hop",
                    })
        except Exception as e:
            logger.error(f"Multi-hop traversal failed: {e}")
            self._failure_count += 1

        logger.info(f"Found {len(paths)} graph paths")
        return paths

    def _entity_intersection(self, gq: GraphQuery) -> List[Dict]:
        """Find recipes connected to ALL source entities (AND intersection)."""
        recipes_data = []
        if not self._connected:
            self._ensure_connected()
        if not self._connected or len(gq.source_entities) < 2:
            return recipes_data

        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (r:Recipe)
                WHERE ALL(term IN $source_entities WHERE EXISTS {
                    MATCH (r)-[:REQUIRES]->(i:Ingredient)
                    WHERE i.name CONTAINS term OR i.nodeId = term
                })
                WITH r
                OPTIONAL MATCH (r)-[:REQUIRES]->(i:Ingredient)
                OPTIONAL MATCH (r)-[:CONTAINS_STEP]->(s:CookingStep)
                OPTIONAL MATCH (r)-[:BELONGS_TO_CATEGORY]->(c:Category)
                RETURN r,
                       collect(DISTINCT i.name) AS ingredients,
                       count(DISTINCT s) AS step_count,
                       collect(DISTINCT c.name) AS categories
                LIMIT 20
                """
                result = session.run(cypher, {"source_entities": gq.source_entities})
                for record in result:
                    node = record["r"]
                    recipes_data.append({
                        "nodes": [{
                            "id": node.get("nodeId", ""),
                            "name": node.get("name", ""),
                            "labels": list(node.labels),
                            "category": node.get("category", ""),
                            "cuisine": node.get("cuisineType", ""),
                            "difficulty": node.get("difficulty", ""),
                        }],
                        "relationships": [],
                        "path_length": 1,
                        "relevance_score": 0.9,
                        "path_type": "intersection",
                        "ingredients": record.get("ingredients", []),
                        "step_count": record.get("step_count", 0),
                        "similar_dishes": record.get("similar_dishes", []),
                    })
        except Exception as e:
            logger.error(f"Entity intersection failed: {e}")

        logger.info(f"Intersection found {len(recipes_data)} recipes")
        return recipes_data

    def extract_knowledge_subgraph(self, gq: GraphQuery) -> Dict:
        if not self._connected:
            self._ensure_connected()
        if not self._connected:
            return {"central_nodes": [], "connected_nodes": [], "relationships": [], "graph_metrics": {}, "reasoning_chains": []}

        try:
            with self.driver.session() as session:
                cypher = f"""
                UNWIND $source_entities as entity_name
                MATCH (source)
                WHERE (source:Recipe OR source:Ingredient OR source:Category)
                  AND (source.name CONTAINS entity_name OR source.nodeId = entity_name)
                MATCH (source)-[r*1..{gq.max_depth}]-(neighbor)
                WITH source, collect(DISTINCT neighbor) as neighbors,
                     collect(DISTINCT r) as relationships
                RETURN source,
                       neighbors[0..$max_nodes] as nodes,
                       relationships[0..$max_nodes] as rels,
                       {{
                           node_count: size(neighbors),
                           relationship_count: size(relationships)
                       }} as metrics
                """
                result = session.run(cypher, {
                    "source_entities": gq.source_entities,
                    "max_nodes": gq.max_nodes,
                })
                record = result.single()
                if record:
                    central = [dict(record["source"])] if record["source"] else []
                    connected = [dict(n) for n in (record.get("nodes") or [])]
                    rels_list = [dict(r[0]) if isinstance(r, list) else dict(r) for r in (record.get("rels") or [])]
                    return {
                        "central_nodes": central,
                        "connected_nodes": connected,
                        "relationships": rels_list,
                        "graph_metrics": record.get("metrics", {}),
                        "reasoning_chains": [],
                    }
        except Exception as e:
            logger.error(f"Subgraph extraction failed: {e}")

        return {"central_nodes": [], "connected_nodes": [], "relationships": [], "graph_metrics": {}, "reasoning_chains": []}

    def graph_rag_search(self, query: str, top_k: int = 5) -> List[Document]:
        logger.info(f"GraphRAG search: {query}")
        if not self._connected:
            self._ensure_connected()
        if not self._connected:
            return []

        gq = self.understand_graph_query(query)
        logger.info(f"Graph query: type={gq.query_type.value}, sources={gq.source_entities}, targets={gq.target_entities}")

        results = []
        try:
            # Intersection path: when 2+ entities AND query asks "what uses X and Y"
            if len(gq.source_entities) >= 2 and gq.query_type in [QueryType.MULTI_HOP, QueryType.ENTITY_RELATION]:
                intersection_paths = self._entity_intersection(gq)
                if intersection_paths:
                    results = self._intersection_to_documents(intersection_paths, gq.source_entities)
                else:
                    paths = self.multi_hop_traversal(gq)
                    results = self._paths_to_documents(paths)
            elif gq.query_type in [QueryType.MULTI_HOP, QueryType.PATH_FINDING, QueryType.ENTITY_RELATION]:
                paths = self.multi_hop_traversal(gq)
                if not paths and gq.source_entities:
                    logger.info("No paths from primary entities, trying expanded search...")
                    expanded = [s.replace("鸡", "") if s.startswith("鸡") else s for s in gq.source_entities]
                    expanded = [s for s in expanded if s] or gq.source_entities
                    gq.source_entities = expanded
                    paths = self.multi_hop_traversal(gq)
                results = self._paths_to_documents(paths)

            elif gq.query_type in [QueryType.SUBGRAPH, QueryType.CLUSTERING]:
                subgraph = self.extract_knowledge_subgraph(gq)
                if not subgraph.get("central_nodes") and gq.source_entities:
                    logger.info("Empty subgraph, trying broader search...")
                    gq.max_depth = min(gq.max_depth + 1, 4)
                    subgraph = self.extract_knowledge_subgraph(gq)
                results = self._subgraph_to_documents(subgraph)

            results = sorted(results, key=lambda x: x.metadata.get("relevance_score", 0), reverse=True)
            
            # If all results are empty/placeholder, return empty so fallback kicks in
            non_empty = [r for r in results if r.metadata.get("search_type") not in ("subgraph_empty", "")]
            if not non_empty:
                logger.info("GraphRAG returned only empty results, returning [] for fallback")
                return []
            
            logger.info(f"GraphRAG returned {len(results[:top_k])} results")
            return results[:top_k]
        except Exception as e:
            logger.error(f"GraphRAG search failed: {e}")
            return []

    def _paths_to_documents(self, paths: List[Dict]) -> List[Document]:
        docs = []
        for path in paths:
            structured = {
                "path_type": "multi_hop",
                "nodes": path.get("nodes", []),
                "relationships": path.get("relationships", []),
            }
            readable = self._path_to_readable(path)
            docs.append(Document(
                page_content=readable,
                metadata={
                    "search_type": "graph_path",
                    "structured_data": json.dumps(structured, ensure_ascii=False),
                    "path_length": path.get("path_length", 0),
                    "relevance_score": path.get("relevance_score", 0),
                    "node_count": len(path.get("nodes", [])),
                    "recipe_name": path["nodes"][0].get("name", "") if path.get("nodes") else "",
                    "search_source": "graph_rag",
                }
            ))
        return docs

    def _intersection_to_documents(self, intersection_paths: List[Dict], source_entities: List[str]) -> List[Document]:
        docs = []
        source_str = "、".join(source_entities)
        for entry in intersection_paths:
            nodes = entry.get("nodes", [])
            if not nodes:
                continue
            recipe = nodes[0]
            name = recipe.get("name", "")
            category = recipe.get("category", "")
            cuisine = recipe.get("cuisine", "")
            difficulty = recipe.get("difficulty", "")
            ings = entry.get("ingredients", [])
            similar = entry.get("similar_dishes", [])

            desc_parts = [f"菜名: {name}"]
            if category: desc_parts.append(f"分类: {category}")
            if cuisine: desc_parts.append(f"菜系: {cuisine}")
            if difficulty: desc_parts.append(f"难度: {difficulty}")
            if ings: desc_parts.append(f"食材: {', '.join(ings[:12])}")
            if similar: desc_parts.append(f"类似菜品: {', '.join(similar)}")
            readable = " | ".join(desc_parts)

            docs.append(Document(
                page_content=readable,
                metadata={
                    "search_type": "graph_path",
                    "structured_data": json.dumps({
                        "path_type": "intersection",
                        "ingredients": ings,
                        "similar_dishes": similar,
                    }, ensure_ascii=False),
                    "path_length": entry.get("path_length", 1),
                    "relevance_score": entry.get("relevance_score", 0.9),
                    "node_count": len(nodes),
                    "recipe_name": name,
                    "search_source": "graph_rag",
                }
            ))
        return docs

    def _path_to_readable(self, path: Dict) -> str:
        parts = []
        nodes = path.get("nodes", [])
        rels = path.get("relationships", [])
        for i, node in enumerate(nodes):
            label = ",".join(node.get("labels", []))
            name = node.get("name", "")
            props = node.get("properties", {})
            category = props.get("category", "")
            extra = f"({category})" if category else ""
            parts.append(f"[{label}] {name}{extra}")
            if i < len(rels):
                rel_type = rels[i].get("type", "RELATED")
                parts.append(f" --{rel_type}--> ")
        return f"推理链 (深度{path.get('path_length', 0)}): " + "".join(parts)

    def _subgraph_to_documents(self, subgraph: Dict) -> List[Document]:
        docs = []
        central = subgraph.get("central_nodes", [])
        connected = subgraph.get("connected_nodes", [])
        rels = subgraph.get("relationships", [])
        metrics = subgraph.get("graph_metrics", {})

        for node in connected[:15]:
            label = ",".join(node.get("labels", []))
            name = node.get("name", "")[:80]
            cat = node.get("category", "")
            difficulty = node.get("difficulty", "")
            cuisine = node.get("cuisineType", "")
            servings = node.get("servings", "")
            extra_parts = []
            if cat: extra_parts.append(f"分类={cat}")
            if difficulty: extra_parts.append(f"难度={difficulty}")
            if cuisine: extra_parts.append(f"菜系={cuisine}")
            if servings: extra_parts.append(f"份量={servings}")
            extra = " " + ", ".join(extra_parts) if extra_parts else ""
            docs.append(Document(
                page_content=f"图谱节点: [{label}] {name}{extra}",
                metadata={
                    "search_type": "subgraph_node",
                    "node_label": label,
                    "node_name": name,
                    "relevance_score": 0.8,
                    "recipe_name": central[0].get("name", "") if central else "",
                    "search_source": "graph_rag",
                }
            ))

        if docs:
            docs.append(Document(
                page_content=f"子图统计: {metrics.get('node_count', len(connected))} 节点, {len(rels)} 关系",
                metadata={
                    "search_type": "subgraph_summary",
                    "node_count": metrics.get("node_count", len(connected)),
                    "relationship_count": len(rels),
                    "relevance_score": 0.9,
                    "recipe_name": central[0].get("name", "") if central else "",
                    "search_source": "graph_rag",
                }
            ))

        return docs or [Document(
            page_content="未找到相关子图信息",
            metadata={"search_type": "subgraph_empty", "search_source": "graph_rag"}
        )]

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("GraphRAG retrieval closed")
