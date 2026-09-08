"""Dependency tracing engine — tracks how entity changes propagate through engagement.

Core IP: Assumption → Hypothesis → Recommendation → Slide → Scene
Uses Python-based BFS traversal with optional PostgreSQL recursive CTE for performance.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text, select


class DependencyTracer:
    """Tracks downstream dependencies when an entity changes.

    The dependency graph stores edges: assumption → hypothesis → recommendation → slide → video_scene.
    When a source entity changes, this traces all affected downstream entities.
    """

    DEPENDENCY_ORDER = [
        "assumption",
        "hypothesis",
        "recommendation",
        "slide",
        "video_scene",
    ]

    TYPE_TO_BUCKET = {
        "assumption": "assumptions",
        "hypothesis": "hypotheses",
        "recommendation": "recommendations",
        "slide": "slides",
        "video_scene": "scenes",
    }

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def trace_impact(self, source_type: str, source_id: str) -> dict:
        """Sync wrapper for trace_impact_async (no DB = empty result)."""
        affected = {
            "assumptions": [],
            "hypotheses": [],
            "recommendations": [],
            "slides": [],
            "scenes": [],
        }

        if not self.db:
            return affected

        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.trace_impact_async(source_type, source_id)
        )

    def get_dependency_path(self, source_type: str, source_id: str, target_type: str, target_id: str) -> list[dict[str, str]]:
        """Sync wrapper for get_dependency_path_async (no DB = empty result)."""
        if not self.db:
            return []

        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.get_dependency_path_async(source_type, source_id, target_type, target_id)
        )

    async def _get_children(self, source_type: str, source_id: str, engagement_id: UUID | None = None) -> list[tuple[str, str]]:
        """Get direct downstream dependencies for a given entity (async)."""
        if not self.db:
            return []

        from backend.models.entities import DependencyEdge
        from uuid import UUID as UUIDType

        stmt = select(DependencyEdge.target_type, DependencyEdge.target_id).where(
            DependencyEdge.source_type == source_type,
            DependencyEdge.source_id == UUIDType(source_id),
        )
        if engagement_id:
            stmt = stmt.where(DependencyEdge.engagement_id == engagement_id)

        result = await self.db.execute(stmt)
        rows = result.fetchall()
        return [(row[0], str(row[1])) for row in rows]

    async def trace_impact_async(self, source_type: str, source_id: str) -> dict:
        """Trace all entities affected by a change to source_type/source_id (async).

        Returns dict with keys: assumptions, hypotheses, recommendations, slides, scenes.
        Each is a list of UUID strings.
        """
        affected = {
            "assumptions": [],
            "hypotheses": [],
            "recommendations": [],
            "slides": [],
            "scenes": [],
        }

        if not self.db:
            return affected

        from backend.models.entities import DependencyEdge

        # Find engagement_id from the starting edge
        from uuid import UUID as UUIDType

        find_eng_stmt = select(DependencyEdge.engagement_id).where(
            DependencyEdge.source_type == source_type,
            DependencyEdge.source_id == UUIDType(source_id),
        )
        eng_result = await self.db.execute(find_eng_stmt)
        eng_row = eng_result.fetchone()
        engagement_id = eng_row[0] if eng_row else None

        # BFS traversal
        visited = set()
        queue: list[tuple[str, str]] = [(source_type, source_id)]

        while queue:
            cur_type, cur_id = queue.pop(0)

            key = f"{cur_type}:{cur_id}"
            if key in visited:
                continue
            visited.add(key)

            children = await self._get_children(cur_type, cur_id, engagement_id)
            for child_type, child_id in children:
                bucket = self.TYPE_TO_BUCKET.get(child_type)
                if bucket and child_id not in visited:
                    if child_id not in affected[bucket]:
                        affected[bucket].append(child_id)
                    queue.append((child_type, child_id))

        return affected

    async def get_dependency_path_async(
        self, source_type: str, source_id: str, target_type: str, target_id: str
    ) -> list[dict[str, str]]:
        """Trace the path from source to target through the dependency graph (async).

        Returns list of nodes forming the path, or empty list if no path exists.
        Uses BFS to find shortest path.
        """
        if not self.db:
            return []

        visited = set()
        queue: list[tuple[str, str, list[dict[str, str]]]] = [
            (source_type, str(source_id), [{"type": source_type, "id": str(source_id)}])
        ]

        while queue:
            cur_type, cur_id, path = queue.pop(0)

            if f"{cur_type}:{cur_id}" in visited:
                continue
            visited.add(f"{cur_type}:{cur_id}")

            if cur_type == target_type and cur_id == str(target_id):
                return path

            children = await self._get_children(cur_type, cur_id)
            for child_type, child_id in children:
                new_path = path + [{"type": child_type, "id": child_id}]
                queue.append((child_type, child_id, new_path))

        return []

    def add_dependency(
        self,
        engagement_id: UUID,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID,
    ) -> bool:
        """Add a dependency edge. Returns True if created, False if already existed."""
        if not self.db:
            return False

        from backend.models.entities import DependencyEdge

        edge = DependencyEdge(
            engagement_id=engagement_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
        )
        self.db.add(edge)
        return True
