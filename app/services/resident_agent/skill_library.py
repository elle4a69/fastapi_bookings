"""RAG Skill Library Semantic Integration for Resident Autonomous Agent.

Discovers, indexes, and searches the engineering skill library at C:\\Users\\Frank\\skills
without loading full files into memory, enabling surgical token usage and contextual
skill citations in remediation plans and AI advisory responses.
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_PATH = r"C:\Users\Frank\skills"


class SkillLibrary:
    """Lightweight on-demand discovery and retrieval for engineering skills."""

    def __init__(self, skills_dir: Optional[str] = None) -> None:
        raw_path = skills_dir or os.getenv("SKILLS_DIR", DEFAULT_SKILLS_PATH)
        self.skills_dir = Path(raw_path)
        self._index_cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_index(self) -> List[Dict[str, Any]]:
        """Index skills by scanning directories and frontmatter without reading full files."""
        if self._index_cache is not None:
            return self._index_cache

        indexed: List[Dict[str, Any]] = []
        if not self.skills_dir.exists() or not self.skills_dir.is_dir():
            logger.warning("Skills directory does not exist: %s", self.skills_dir)
            self._index_cache = []
            return self._index_cache

        try:
            for entry in os.scandir(self.skills_dir):
                if entry.is_dir(follow_symlinks=False):
                    skill_id = entry.name
                    skill_file = Path(entry.path) / "SKILL.md"
                    if not skill_file.exists():
                        continue

                    name = skill_id
                    description = ""
                    tags: List[str] = []

                    # Surgically read only the frontmatter / header (first 2048 bytes)
                    try:
                        with open(skill_file, "r", encoding="utf-8", errors="ignore") as f:
                            header_content = f.read(2048)

                        # Parse YAML frontmatter between --- and ---
                        if header_content.startswith("---"):
                            end_marker = header_content.find("---", 3)
                            frontmatter = header_content[3:end_marker] if end_marker != -1 else header_content[:500]
                            for line in frontmatter.splitlines():
                                line_clean = line.strip()
                                if line_clean.startswith("name:"):
                                    name = line_clean.split("name:", 1)[1].strip().strip("'\"")
                                elif line_clean.startswith("description:"):
                                    description = line_clean.split("description:", 1)[1].strip().strip("'\"")
                                elif line_clean.startswith("tags:"):
                                    raw_tags = line_clean.split("tags:", 1)[1].strip().strip("[]'\"")
                                    tags = [t.strip().strip("'\"") for t in raw_tags.split(",") if t.strip()]

                        if not description:
                            # Fallback: extract first paragraph or instructions line
                            desc_match = re.search(r"## Purpose\s*\n+([^\n#]+)", header_content)
                            if desc_match:
                                description = desc_match.group(1).strip()
                            else:
                                description = f"Specialized skill instructions for {skill_id}."

                    except Exception as parse_err:
                        logger.debug("Could not parse header for skill %s: %s", skill_id, parse_err)
                        description = f"Specialized engineering skill: {skill_id}."

                    if not tags:
                        # Infer tags from skill name hyphenation
                        tags = [part for part in skill_id.split("-") if len(part) > 2]

                    indexed.append({
                        "skill_id": skill_id,
                        "name": name or skill_id,
                        "description": description,
                        "tags": tags,
                        "path": str(skill_file),
                    })

        except Exception as exc:
            logger.error("Failed indexing skills in %s: %s", self.skills_dir, exc)

        self._index_cache = indexed
        return self._index_cache

    def find_relevant_skills(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for top matching engineering skills based on query terms.
        
        Scans skill titles and SKILL.md frontmatter/descriptions without loading full
        files into memory.
        """
        index = self._ensure_index()
        if not index:
            return []

        # Tokenize query
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        if not tokens:
            return index[:top_k]

        scored_skills = []
        clean_query = query.strip().lower()

        for item in index:
            score = 0.0
            s_id = item["skill_id"].lower()
            s_name = item["name"].lower()
            s_desc = item["description"].lower()
            s_tags = [t.lower() for t in item["tags"]]

            # Exact query matches
            if clean_query in s_id or clean_query in s_name:
                score += 15.0

            # Token level scoring
            for token in tokens:
                if token in s_id:
                    score += 6.0
                elif token in s_name:
                    score += 5.0

                if any(token == tag for tag in s_tags):
                    score += 4.0
                elif any(token in tag for tag in s_tags):
                    score += 2.0

                if token in s_desc:
                    score += 1.5

            if score > 0:
                scored_skills.append({
                    **item,
                    "score": round(score, 2),
                })

        # Sort descending by score
        scored_skills.sort(key=lambda x: x["score"], reverse=True)
        return scored_skills[:top_k]

    def read_skill(self, skill_id: str) -> str:
        """Load the specific SKILL.md on demand for surgical token usage (no context flooding!)."""
        # Protect against path traversal
        clean_id = os.path.basename(skill_id.strip())
        skill_file = self.skills_dir / clean_id / "SKILL.md"

        if not skill_file.exists():
            # Check if skill_id directly matches file path
            direct_path = Path(skill_id)
            if direct_path.exists() and direct_path.is_file():
                skill_file = direct_path
            else:
                raise FileNotFoundError(f"Skill '{skill_id}' not found in library at {self.skills_dir}.")

        with open(skill_file, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def get_library_stats(self) -> Dict[str, Any]:
        """Return summary statistics of available skills."""
        index = self._ensure_index()
        return {
            "total_skills": len(index),
            "skills_dir": str(self.skills_dir),
            "is_available": self.skills_dir.exists(),
        }


# Global singleton instance
skill_library = SkillLibrary()
