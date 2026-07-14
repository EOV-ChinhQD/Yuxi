import asyncio
from typing import Any, Dict, List, Set
from sqlalchemy import select, update
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_knowledge import KnowledgeGraphEntity
from yuxi.knowledge.graphs.graph_utils import normalize_entity_name
from yuxi.utils.logging_config import logger

class EntityResolver:
    """Bộ giải quyết thực thể (Entity Resolution) chuẩn hóa và đồng bộ các bí danh (aliases) về Canonical Name."""

    async def resolve_entities(self, kb_id: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Nhận vào danh sách thực thể thô và cập nhật các trường canonical_name, aliases.
        
        Args:
            kb_id: ID cơ sở tri thức
            entities: Danh sách các dict thực thể dạng {"text": "...", "label": "...", "attributes": [...], "entity_id": "..."}
            
        Returns:
            Danh sách thực thể đã được điền canonical_name và aliases.
        """
        if not entities:
            return []

        # 1. Thu thập tất cả các entity_id từ danh sách thực thể
        entity_ids = {ent.get("entity_id") for ent in entities if ent.get("entity_id")}
        normalized_names = {normalize_entity_name(ent.get("text", "")) for ent in entities}

        async with pg_manager.get_async_session_context() as session:
            # 2. Truy vấn tất cả thực thể hiện có trong KB
            stmt = select(KnowledgeGraphEntity).where(KnowledgeGraphEntity.kb_id == kb_id)
            result = await session.execute(stmt)
            db_entities = result.scalars().all()

        # 3. Xây dựng bản đồ ánh xạ nhanh để tra cứu
        # Tra cứu theo normalized_name -> canonical_name
        name_to_canonical: Dict[str, str] = {}
        # Tra cứu theo alias -> canonical_name
        alias_to_canonical: Dict[str, str] = {}
        # Lưu trữ đối tượng DB entity để cập nhật aliases sau này
        db_entity_map: Dict[str, KnowledgeGraphEntity] = {}

        for db_ent in db_entities:
            c_name = db_ent.canonical_name or db_ent.name
            name_to_canonical[db_ent.normalized_name] = c_name
            db_entity_map[c_name] = db_ent
            
            aliases = db_ent.aliases or []
            for alias in aliases:
                norm_alias = normalize_entity_name(alias)
                alias_to_canonical[norm_alias] = c_name

        # 4. Thực hiện ánh xạ thực thể mới
        resolved_entities = []
        entities_to_update_aliases: Dict[str, Set[str]] = {}

        for ent in entities:
            name = ent.get("text", "")
            norm_name = normalize_entity_name(name)
            
            # Kiểm tra xem thực thể này đã được ánh xạ canonical_name chưa
            canonical_name = name_to_canonical.get(norm_name) or alias_to_canonical.get(norm_name)
            
            if canonical_name:
                # Tìm thấy canonical name hiện tại -> Ghi nhận canonical_name
                ent["canonical_name"] = canonical_name
                
                # Cập nhật aliases của canonical entity
                if canonical_name not in entities_to_update_aliases:
                    entities_to_update_aliases[canonical_name] = set()
                entities_to_update_aliases[canonical_name].add(name)
            else:
                # Chưa tồn tại -> Thiết lập chính nó làm canonical name
                canonical_name = name
                ent["canonical_name"] = canonical_name
                ent["aliases"] = [name]
                
                # Thêm vào bộ nhớ cache tạm thời để các thực thể trùng lặp tiếp theo trong cùng lô có thể nhận diện được
                name_to_canonical[norm_name] = canonical_name

            # Đảm bảo trường aliases được cập nhật
            db_ent_obj = db_entity_map.get(canonical_name)
            current_aliases = set(db_ent_obj.aliases) if db_ent_obj and db_ent_obj.aliases else {canonical_name}
            current_aliases.add(name)
            ent["aliases"] = list(current_aliases)
            resolved_entities.append(ent)

        # 5. Cập nhật aliases mới vào database
        if entities_to_update_aliases:
            async with pg_manager.get_async_session_context() as session:
                for c_name, new_aliases in entities_to_update_aliases.items():
                    db_ent_obj = db_entity_map.get(c_name)
                    if db_ent_obj:
                        current_aliases = set(db_ent_obj.aliases) if db_ent_obj.aliases else {c_name}
                        current_aliases.update(new_aliases)
                        
                        # Cập nhật trực tiếp trên model
                        await session.execute(
                            update(KnowledgeGraphEntity)
                            .where(KnowledgeGraphEntity.id == db_ent_obj.id)
                            .values(aliases=list(current_aliases))
                        )
                await session.commit()

        return resolved_entities
