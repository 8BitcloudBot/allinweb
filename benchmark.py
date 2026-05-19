#!/usr/bin/env python3
"""ChefMate RAG + GraphRAG 综合测试套件 — 升级前后对比"""

import json, time, urllib.request, sys, ssl
from collections import defaultdict

RAG_API = "https://vincentbuilds.fun/api/chat"
GRAPH_API = "https://vincentbuilds.fun/api/graphchat"

# Bypass SSL for Let's Encrypt cert on local Python
ssl_ctx = ssl._create_unverified_context()

TEST_QUERIES = {
    "A_简单菜谱": [
        ("宫保鸡丁怎么做", None),
        ("红烧肉的做法", None),
        ("西红柿炒鸡蛋的做法", None),
        ("酸辣土豆丝的做法", None),
    ],
    "B_推荐查询": [
        ("推荐几个简单的素菜", None),
        ("清淡的汤有哪些", None),
        ("推荐几个下饭菜", None),
        ("有什么甜品推荐", None),
    ],
    "C_图谱推理": [
        ("鸡肉配什么蔬菜", "graph_rag"),
        ("土豆能替代什么食材", "graph_rag"),
        ("和宫保鸡丁类似的菜", "graph_rag"),
        ("大葱可以和什么一起炒", "graph_rag"),
    ],
    "D_反向查询": [
        ("用花椒做的菜有哪些", "graph_rag"),
        ("什么菜用了牛肉和土豆", "graph_rag"),
    ],
    "E_抽象查询": [
        ("推荐一些难度较高的菜", None),
        ("适合夏天的清淡菜", None),
        ("有没有口味比较重的菜", None),
    ],
    "F_边界查询": [
        ("你好", None),
        ("abcdefg12345", None),
        ("做菜", None),
    ],
}

RAG_TEST = [
    ("宫保鸡丁怎么做", None),
    ("推荐几个简单的素菜", None),
    ("清淡的汤有哪些", None),
    ("没有淀粉可以用什么代替", None),
    ("适合两个人吃的菜", None),
    ("夏天适合吃什么菜", None),
    ("推荐几个下饭菜", None),
]


def query_api(api_url, query):
    t0 = time.time()
    try:
        data = json.dumps({"query": query}).encode()
        req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=60, context=ssl_ctx)
        result = json.loads(resp.read())
        latency = time.time() - t0
        ri = result.get("routing_info", {})
        gm = result.get("graph_metrics", {})
        m = result.get("metrics", {})
        return {
            "query": query,
            "strategy": ri.get("strategy", "?"),
            "complexity": ri.get("query_complexity", 0),
            "intensity": ri.get("relationship_intensity", 0),
            "latency": round(latency, 3),
            "retrieval_count": m.get("retrieval_count", 0),
            "node_count": gm.get("node_count", 0),
            "depth": gm.get("traversal_depth", 0),
            "confidence": round(m.get("confidence_score", 0), 3),
            "answer_len": len(result.get("answer", "") or ""),
            "answer_preview": (result.get("answer", "") or "")[:80],
        }
    except Exception as e:
        return {
            "query": query,
            "strategy": "ERROR",
            "latency": round(time.time() - t0, 3),
            "error": str(e)[:80],
        }


def run_tests(label, api_url, queries):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    results = []
    for query, expected_strategy in queries:
        r = query_api(api_url, query)
        match = "✅" if (expected_strategy is None or r.get("strategy") == expected_strategy) else "❌"
        status = "EMPTY" if r.get("answer_len", 0) < 10 else f"{r.get('answer_len')}chars"
        error = r.get("error", "")
        aux = f" | {error}" if error else ""
        print(f"  {match} [{r['strategy']:20s}] {r['latency']:.2f}s | {status:10s} | {query[:30]}{aux}")
        results.append(r)
    return results


def summarize(results, label):
    counts = defaultdict(int)
    latencies = []
    retrievals = []
    nodes = []
    depths = []
    confidences = []
    answer_lens = []
    errors = 0
    empty = 0

    for r in results:
        counts[r["strategy"]] += 1
        if r["strategy"] == "ERROR":
            errors += 1
        else:
            latencies.append(r["latency"])
            retrievals.append(r["retrieval_count"])
            nodes.append(r["node_count"])
            depths.append(r["depth"])
            confidences.append(r["confidence"])
            answer_lens.append(r["answer_len"])
            if r["answer_len"] < 10:
                empty += 1

    def avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else 0

    print(f"\n{'─'*50}")
    print(f"  {label} SUMMARY ({len(results)} queries)")
    print(f"{'─'*50}")
    print(f"  Strategy distribution: {dict(counts)}")
    print(f"  Empty responses: {empty}/{len(results)}")
    print(f"  Errors: {errors}")
    print(f"  Avg latency: {avg(latencies)}s")
    print(f"  Avg retrieval count: {avg(retrievals)}")
    print(f"  Avg node count: {avg(nodes)}")
    print(f"  Avg depth: {avg(depths)}")
    print(f"  Avg confidence: {avg(confidences)}")
    print(f"  Avg answer length: {avg(answer_lens)} chars")
    return {
        "counts": dict(counts),
        "empty": empty,
        "errors": errors,
        "avg_latency": avg(latencies),
        "avg_retrieval": avg(retrievals),
        "avg_nodes": avg(nodes),
        "avg_depth": avg(depths),
        "avg_confidence": avg(confidences),
        "avg_answer_len": avg(answer_lens),
        "total_queries": len(results),
    }


if __name__ == "__main__":
    all_graph = []
    all_rag = []

    print("=" * 60)
    print("  CHEFMATE BENCHMARK — UPGRADED (bge-base)")
    print("=" * 60)

    # GraphRAG tests
    for label, queries in sorted(TEST_QUERIES.items()):
        res = run_tests(f"GraphRAG {label}", GRAPH_API, queries)
        all_graph.extend(res)
        time.sleep(1)

    # RAG tests
    res = run_tests("RAG queries", RAG_API, RAG_TEST)
    all_rag.extend(res)
    time.sleep(1)

    summary_graph = summarize(all_graph, "GraphRAG")
    summary_rag = summarize(all_rag, "RAG")

    # Save results
    output = {
        "version": "bge-base-zh-v1.5",
        "embedding": "bge-base-zh-v1.5",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "graphrag": summary_graph,
        "rag": summary_rag,
        "graphrag_details": all_graph,
        "rag_details": all_rag,
    }
    with open("benchmark_upgraded.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to benchmark_baseline.json")
