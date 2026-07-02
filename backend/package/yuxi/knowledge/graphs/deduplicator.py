import asyncio
import json
import re
from typing import List, Dict, Any

from yuxi.utils import logger
from yuxi.models import select_model
from yuxi.storage.neo4j import neo4j_read, neo4j_write, safe_neo4j_label
from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService
from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore

class GraphDeduplicator:
    def __init__(self, kb_id: str, llm_model_spec: str = "gpt-4o"):
        self.kb_id = kb_id
        self.llm_model_spec = llm_model_spec
        self.graph_service = MilvusGraphService()
        self.label = safe_neo4j_label(kb_id)

    async def get_all_entities(self) -> List[Dict[str, str]]:
        cypher = f"""
        MATCH (e:Entity:MilvusKB:`{self.label}`)
        WHERE e.kb_id = $kb_id
        RETURN e.entity_id AS entity_id, e.name AS name
        """
        records = await asyncio.to_thread(neo4j_read, self.graph_service.driver, cypher, kb_id=self.kb_id)
        return [{"entity_id": r["entity_id"], "name": r["name"]} for r in records]

    async def cluster_entities_with_llm(self, entities: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
        if len(entities) < 2:
            return []

        names = [e["name"] for e in entities]
        # Xử lý theo lô tối đa 500 thực thể một lần để không vượt quá context window
        batch_size = 300
        all_clusters = []
        
        for i in range(0, len(names), batch_size):
            batch_names = names[i:i + batch_size]
            prompt = f"""Bạn là chuyên gia phân tích dữ liệu đồ thị tiếng Việt.
Dưới đây là danh sách các thực thể (entities). Hãy nhóm các thực thể đồng nghĩa, viết tắt, hoặc là biến thể của nhau vào chung một nhóm.
Chỉ gộp khi bạn CỰC KỲ CHẮC CHẮN chúng là một (ví dụ: 'HCM' và 'Hồ Chí Minh', 'Máy biến áp' và 'Máy biến thế', 'Công ty ABC' và 'CTY ABC').
Những thực thể không có đồng nghĩa thì bỏ qua, KHÔNG đưa vào output.

Danh sách thực thể:
{json.dumps(batch_names, ensure_ascii=False, indent=2)}

Trả về JSON chính xác theo định dạng sau (không giải thích thêm):
{{
  "clusters": [
    ["thực thể A", "thực thể biến thể A1", "thực thể biến thể A2"],
    ["thực thể B", "thực thể biến thể B1"]
  ]
}}
"""
            try:
                model = select_model(model_spec=self.llm_model_spec)
                response = await model.call(prompt)
                raw = response.content.strip()
                
                match = re.search(r'\{[\s\S]*\}', raw)
                if match:
                    data = json.loads(match.group())
                    clusters = data.get("clusters", [])
                    
                    # Ánh xạ ngược lại object chứa entity_id
                    name_to_obj = {e["name"]: e for e in entities}
                    for cluster in clusters:
                        if len(cluster) > 1:
                            cluster_objs = [name_to_obj[name] for name in cluster if name in name_to_obj]
                            if len(cluster_objs) > 1:
                                all_clusters.append(cluster_objs)
            except Exception as e:
                logger.error(f"[Deduplicator] LLM clustering failed for batch: {e}")
        
        return all_clusters

    async def merge_cluster(self, cluster: List[Dict[str, str]]):
        if len(cluster) < 2:
            return

        # Chọn target là thực thể có tên ngắn gọn nhất (thường là tên chính)
        cluster = sorted(cluster, key=lambda x: len(x["name"]))
        target = cluster[0]
        sources = cluster[1:]
        
        source_ids = [s["entity_id"] for s in sources]
        logger.info(f"[Deduplicator] Gộp {len(sources)} thực thể vào '{target['name']}'")

        cypher = f"""
        MATCH (target:Entity:MilvusKB:`{self.label}` {{entity_id: $target_id}})
        UNWIND $source_ids AS src_id
        MATCH (source:Entity:MilvusKB:`{self.label}` {{entity_id: src_id}})
        
        // Di chuyển RELATION đi ra
        WITH target, source, src_id
        OPTIONAL MATCH (source)-[r_out:RELATION]->(other)
        CALL apoc.do.when(
            r_out IS NOT NULL,
            "MERGE (target)-[new_out:RELATION {{kb_id: r_out.kb_id, type: r_out.type, target_name: r_out.target_name}}]->(other) SET new_out += properties(r_out) RETURN new_out",
            "",
            {{target: target, r_out: r_out, other: other}}
        ) YIELD value AS v1

        // Di chuyển RELATION đi vào
        WITH target, source, src_id
        OPTIONAL MATCH (other2)-[r_in:RELATION]->(source)
        CALL apoc.do.when(
            r_in IS NOT NULL,
            "MERGE (other2)-[new_in:RELATION {{kb_id: r_in.kb_id, type: r_in.type, source_name: r_in.source_name}}]->(target) SET new_in += properties(r_in) RETURN new_in",
            "",
            {{target: target, r_in: r_in, other2: other2}}
        ) YIELD value AS v2

        // Di chuyển MENTIONS
        WITH target, source, src_id
        OPTIONAL MATCH (c:Chunk)-[m:MENTIONS]->(source)
        CALL apoc.do.when(
            m IS NOT NULL,
            "MERGE (c)-[new_m:MENTIONS {{chunk_id: m.chunk_id, file_id: m.file_id, kb_id: m.kb_id}}]->(target) SET new_m += properties(m) RETURN new_m",
            "",
            {{target: target, m: m, c: c}}
        ) YIELD value AS v3

        WITH source
        DETACH DELETE source
        """
        
        # Vì apoc có thể không được bật trên server neo4j tiêu chuẩn của Yuxi
        # Ta viết lại Cypher thuần bằng thủ thuật COLLECT và FOREACH
        native_cypher = f"""
        MATCH (target:Entity:MilvusKB:`{self.label}` {{entity_id: $target_id}})
        UNWIND $source_ids AS src_id
        MATCH (source:Entity:MilvusKB:`{self.label}` {{entity_id: src_id}})
        
        // Move outgoing
        OPTIONAL MATCH (source)-[r_out:RELATION]->(other)
        WITH target, source, src_id, collect(r_out) AS r_outs, collect(other) AS others
        FOREACH (i IN range(0, size(r_outs)-1) | 
            FOREACH (ro IN [r_outs[i]] | FOREACH (ot IN [others[i]] | 
                MERGE (target)-[new_out:RELATION {{type: ro.type, target_name: ro.target_name, kb_id: ro.kb_id}}]->(ot)
                SET new_out += properties(ro)
            ))
        )
        
        // Move incoming
        WITH target, source, src_id
        OPTIONAL MATCH (other2)-[r_in:RELATION]->(source)
        WITH target, source, src_id, collect(r_in) AS r_ins, collect(other2) AS other2s
        FOREACH (i IN range(0, size(r_ins)-1) | 
            FOREACH (ri IN [r_ins[i]] | FOREACH (ot2 IN [other2s[i]] | 
                MERGE (ot2)-[new_in:RELATION {{type: ri.type, source_name: ri.source_name, kb_id: ri.kb_id}}]->(target)
                SET new_in += properties(ri)
            ))
        )

        // Move MENTIONS
        WITH target, source, src_id
        OPTIONAL MATCH (c:Chunk)-[m:MENTIONS]->(source)
        WITH target, source, src_id, collect(m) AS ms, collect(c) AS cs
        FOREACH (i IN range(0, size(ms)-1) | 
            FOREACH (mm IN [ms[i]] | FOREACH (cc IN [cs[i]] | 
                MERGE (cc)-[new_m:MENTIONS {{chunk_id: mm.chunk_id, file_id: mm.file_id, kb_id: mm.kb_id}}]->(target)
                SET new_m += properties(mm)
            ))
        )

        // Delete source
        WITH source
        DETACH DELETE source
        """
        
        try:
            await asyncio.to_thread(neo4j_write, self.graph_service.driver, native_cypher, target_id=target["entity_id"], source_ids=source_ids)
            
            # Xóa các entities đã gộp khỏi Milvus Graph Vector Store
            vector_store = MilvusGraphVectorStore()
            await vector_store.delete_graph_records(self.kb_id, entity_ids=source_ids, triple_ids=[])
            
        except Exception as e:
            logger.error(f"[Deduplicator] Lỗi khi gộp cluster {target['name']}: {e}")

    async def run(self):
        logger.info(f"[Deduplicator] Bắt đầu dọn dẹp đồ thị cho KB {self.kb_id}...")
        entities = await self.get_all_entities()
        logger.info(f"[Deduplicator] Tìm thấy {len(entities)} thực thể.")
        
        clusters = await self.cluster_entities_with_llm(entities)
        logger.info(f"[Deduplicator] LLM đã tìm ra {len(clusters)} nhóm thực thể trùng lặp.")
        
        merged_count = 0
        for cluster in clusters:
            await self.merge_cluster(cluster)
            merged_count += (len(cluster) - 1)
            
        logger.info(f"[Deduplicator] Đã gộp thành công {merged_count} thực thể.")
        return merged_count
