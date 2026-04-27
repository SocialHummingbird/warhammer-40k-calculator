from __future__ import annotations

from typing import Any, Dict, List

from .models import BattleMap, DeploymentZone, Objective, TerrainFeature, to_dict


def battlefield_templates() -> List[Dict[str, Any]]:
    return [
        {
            "id": "strike_force_44x60",
            "name": "Strike Force 44 x 60",
            "width": 44,
            "height": 60,
            "rules_preset": "tactical_mvp_v1",
            "description": "Balanced 10th edition Strike Force board with five objectives.",
        },
        {
            "id": "onslaught_44x90",
            "name": "Onslaught 44 x 90",
            "width": 44,
            "height": 90,
            "rules_preset": "tactical_mvp_v1",
            "description": "Longer board for larger games, using the same simplified terrain rules.",
        },
    ]


def battlefield_templates_payload() -> Dict[str, Any]:
    return {
        "templates": battlefield_templates(),
        "rules": {
            "preset": "tactical_mvp_v1",
            "assumptions": [
                "Terrain uses rectangular footprints with cover and line-of-sight flags.",
                "Deployment zones are fixed rectangles for the MVP.",
                "Objective control is based on unit centre distance to the objective marker.",
            ],
        },
    }


def generate_map(template_id: str = "strike_force_44x60") -> BattleMap:
    if template_id == "onslaught_44x90":
        return _generated_map("onslaught_44x90", "Onslaught 44 x 90", 44, 90)
    return _generated_map("strike_force_44x60", "Strike Force 44 x 60", 44, 60)


def generated_map_payload(template_id: str = "strike_force_44x60") -> Dict[str, Any]:
    return to_dict(generate_map(template_id))


def _generated_map(template_id: str, name: str, width: float, height: float) -> BattleMap:
    dz_depth = 10.0 if height <= 60 else 14.0
    terrain = [
        TerrainFeature("ruin-nw", "Northwest ruin", "ruin", 5, height * 0.22, 10, 8, True, True, 2),
        TerrainFeature("ruin-se", "Southeast ruin", "ruin", width - 15, height * 0.64, 10, 8, True, True, 2),
        TerrainFeature("forest-sw", "Southwest woods", "woods", 7, height * 0.68, 8, 7, True, False, 1),
        TerrainFeature("forest-ne", "Northeast woods", "woods", width - 15, height * 0.2, 8, 7, True, False, 1),
        TerrainFeature("crater-mid", "Central crater", "crater", width / 2 - 5, height / 2 - 4, 10, 8, True, False, 0),
    ]
    objectives = [
        Objective("obj-home-red", "Red home", width / 2, dz_depth / 2, 3, 5),
        Objective("obj-home-blue", "Blue home", width / 2, height - dz_depth / 2, 3, 5),
        Objective("obj-west", "West midfield", width * 0.25, height / 2, 3, 5),
        Objective("obj-centre", "Centre", width / 2, height / 2, 3, 5),
        Objective("obj-east", "East midfield", width * 0.75, height / 2, 3, 5),
    ]
    return BattleMap(
        id=template_id,
        name=name,
        width=width,
        height=height,
        deployment_zones=[
            DeploymentZone("red-dz", "red", 0, 0, width, dz_depth),
            DeploymentZone("blue-dz", "blue", 0, height - dz_depth, width, dz_depth),
        ],
        terrain=terrain,
        objectives=objectives,
    )
