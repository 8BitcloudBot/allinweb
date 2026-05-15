import re
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter


CATEGORY_MAP = {
    "meat_dish": "荤菜",
    "vegetable_dish": "素菜",
    "soup": "汤品",
    "dessert": "甜品",
    "breakfast": "早餐",
    "staple": "主食",
    "aquatic": "水产",
    "condiment": "调料",
    "drink": "饮品",
    "semi-finished": "半成品",
}


def _deterministic_id(file_path: Path) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(file_path)))


class DataPreparationModule:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.documents: List[Document] = []
        self.chunks: List[Document] = []
        self.parent_child_map: Dict[str, str] = {}

    def load_documents(self) -> List[Document]:
        documents = []
        for md_file in Path(self.data_path).rglob("*.md"):
            # 跳过 macOS 资源叉文件和隐藏文件
            if md_file.name.startswith("._") or md_file.name.startswith("."):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = md_file.read_text(encoding="gbk")
                except UnicodeDecodeError:
                    content = md_file.read_text(encoding="latin-1")
            parent_id = _deterministic_id(md_file)
            doc = Document(
                page_content=content,
                metadata={
                    "source": str(md_file),
                    "parent_id": parent_id,
                    "doc_type": "parent",
                },
            )
            documents.append(doc)

        for doc in documents:
            self._enhance_metadata(doc)

        self.documents = documents
        return documents

    def _enhance_metadata(self, doc: Document):
        file_path = Path(doc.metadata["source"])
        path_parts = file_path.parts

        for key, value in CATEGORY_MAP.items():
            if key in path_parts:
                doc.metadata["category"] = value
                break
        else:
            doc.metadata["category"] = "其他"

        doc.metadata["dish_name"] = file_path.stem

        content = doc.page_content
        
        # 提取份量信息
        servings_info = self._extract_servings(content)
        if servings_info:
            doc.metadata["servings_min"] = servings_info[0]
            doc.metadata["servings_max"] = servings_info[1]
        else:
            doc.metadata["servings_min"] = 1
            doc.metadata["servings_max"] = 2  # 默认假设1-2人份
        if "★★★★★" in content:
            doc.metadata["difficulty"] = "非常困难"
        elif "★★★★" in content and "★★★★★" not in content:
            doc.metadata["difficulty"] = "困难"
        elif "★★★" in content and "★★★★" not in content:
            doc.metadata["difficulty"] = "中等"
        elif "★★" in content and "★★★" not in content:
            doc.metadata["difficulty"] = "简单"
        elif "★" in content and "★★" not in content:
            doc.metadata["difficulty"] = "非常简单"
        else:
            doc.metadata["difficulty"] = "未标记"

    def _extract_servings(self, content: str) -> Optional[Tuple[int, int]]:
        """从菜谱内容中提取份量信息
        
        返回：(min_servings, max_servings) 或 None
        """
        patterns = [
            # "一份正好够 2 人吃" / "一份够 2 人"
            (r'一份[正只]?好?够?\s*(\d+)\s*人[吃食]', lambda m: (int(m.group(1)), int(m.group(1)))),
            # "按照 2 人的份量"
            (r'按照\s*(\d+)\s*人[的份]', lambda m: (int(m.group(1)), int(m.group(1)))),
            # "够 2-4 人食用" / "够 2 到 4 人"
            (r'够\s*(\d+)\s*[-到至]\s*(\d+)\s*人', lambda m: (int(m.group(1)), int(m.group(2)))),
            # "足够 2-4 人食用"
            (r'足够\s*(\d+)\s*[-到至]\s*(\d+)\s*人', lambda m: (int(m.group(1)), int(m.group(2)))),
            # "2-4 人份" / "2 到 4 人份"
            (r'(\d+)\s*[-到至]\s*(\d+)\s*人份', lambda m: (int(m.group(1)), int(m.group(2)))),
            # "2 人份" / "2 人食用"
            (r'(\d+)\s*人[份食]', lambda m: (int(m.group(1)), int(m.group(1)))),
            # "够 10 个人"
            (r'够\s*(\d+)\s*个?人', lambda m: (int(m.group(1)), int(m.group(1)))),
        ]
        
        for pattern, extractor in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    return extractor(match)
                except (ValueError, IndexError):
                    continue
        
        return None

    def chunk_documents(self) -> List[Document]:
        if not self.documents:
            raise ValueError("请先加载文档")

        headers_to_split_on = [
            ("#", "主标题"),
            ("##", "二级标题"),
            ("###", "三级标题"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
        )

        all_chunks = []
        for doc in self.documents:
            md_chunks = markdown_splitter.split_text(doc.page_content)
            parent_id = doc.metadata["parent_id"]

            for i, chunk in enumerate(md_chunks):
                child_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{parent_id}-{i}"))
                chunk.metadata.update(doc.metadata)
                chunk.metadata.update({
                    "chunk_id": child_id,
                    "parent_id": parent_id,
                    "doc_type": "child",
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                })
                self.parent_child_map[child_id] = parent_id
                all_chunks.append(chunk)

        self.chunks = all_chunks
        return all_chunks

    def get_parent_documents(self, child_chunks: List[Document]) -> List[Document]:
        parent_relevance = {}
        parent_docs_map = {}

        for chunk in child_chunks:
            parent_id = chunk.metadata.get("parent_id")
            if parent_id:
                parent_relevance[parent_id] = parent_relevance.get(parent_id, 0) + 1
                if parent_id not in parent_docs_map:
                    for doc in self.documents:
                        if doc.metadata.get("parent_id") == parent_id:
                            parent_docs_map[parent_id] = doc
                            break

        sorted_parent_ids = sorted(
            parent_relevance.keys(),
            key=lambda x: parent_relevance[x],
            reverse=True,
        )

        parent_docs = []
        for pid in sorted_parent_ids:
            if pid in parent_docs_map:
                parent_docs.append(parent_docs_map[pid])

        return parent_docs
