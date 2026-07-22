from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class CategoryProfile(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    version: str
    product_types: list[str]
    completeness_fields: list[str]
    risk_weights: dict[str, int]


def load_category_profiles(path: Path) -> dict[str, CategoryProfile]:
    profiles: dict[str, CategoryProfile] = {}
    for profile_path in sorted(path.glob("*.yaml")):
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        profile = CategoryProfile.model_validate(data)
        if profile.id in profiles:
            raise ValueError(f"duplicate category profile: {profile.id}")
        profiles[profile.id] = profile
    return profiles
