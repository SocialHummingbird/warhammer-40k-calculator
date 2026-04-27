from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from . import data_review as data_review_service
from . import editions as edition_service
from .datasheet import _profile_priority, load_units_from_json
from .importers.csv_loader import load_units_from_directory
from .ml.advisory import load_advisory_model, model_status
from .profiles import UnitProfile
from .rules import get_ruleset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDITION = "10e"
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_CSV_DIR = PROJECT_ROOT / "data" / DEFAULT_EDITION / "latest"
LEGACY_CSV_DIR = PROJECT_ROOT / "data" / "latest"
DEFAULT_JSON_PATH = PROJECT_ROOT / "units.json"
WEB_ROOT = PROJECT_ROOT / "web"
MODEL_ROOT = PROJECT_ROOT / "models"


@dataclass
class EditionDataset:
    edition: str
    data_dir: Optional[Path]
    source: str
    units: Dict[str, UnitProfile]
    metadata: Optional[Dict[str, Any]]

    def __post_init__(self) -> None:
        self.supported_rules_editions = supported_rules_editions_from_metadata(self.metadata)
        self.units_by_id = {unit.unit_id: unit for unit in self.units.values() if unit.unit_id}
        self.units_by_name: Dict[str, list[UnitProfile]] = {}
        for unit in self.units.values():
            self.units_by_name.setdefault(unit.name.casefold(), []).append(unit)

    def require_unit(self, name: str = "", *, unit_id: Optional[str] = None) -> UnitProfile:
        if unit_id:
            unit = self.units_by_id.get(str(unit_id))
            if unit is not None:
                return unit
        key = (name or "").casefold()
        matches = self.units_by_name.get(key) or []
        if not matches:
            raise KeyError(unit_id or name)
        if len(matches) == 1:
            return matches[0]
        return sorted(matches, key=lambda profile: _profile_priority(profile, None), reverse=True)[0]


class AppState:
    def __init__(self, *, csv_dir: Optional[Path], json_path: Optional[Path], model_path: Optional[Path] = None) -> None:
        if csv_dir:
            self.data_dir = csv_dir
            self.units = load_units_from_directory(csv_dir)
            self.source = str(csv_dir)
        elif json_path:
            self.data_dir = default_data_dir()
            self.units = load_units_from_json(json_path)
            self.source = str(json_path)
        elif default_data_dir():
            self.data_dir = default_data_dir()
            self.units = load_units_from_directory(self.data_dir)
            self.source = str(self.data_dir)
        else:
            self.data_dir = None
            self.units = load_units_from_json(DEFAULT_JSON_PATH)
            self.source = str(DEFAULT_JSON_PATH)

        self.metadata = data_review_service.load_json_file(self.data_dir / "metadata.json") if self.data_dir else None
        self.rules_edition = rules_edition_from_metadata(self.metadata)
        self.supported_rules_editions = supported_rules_editions_from_metadata(self.metadata)
        self.datasets: Dict[str, EditionDataset] = {
            self.rules_edition: EditionDataset(
                edition=self.rules_edition,
                data_dir=self.data_dir,
                source=self.source,
                units=self.units,
                metadata=self.metadata,
            )
        }
        discovered_editions = []
        if not json_path:
            discovered_editions = discover_edition_data_dirs(DATA_ROOT, active_data_dir=self.data_dir)
            for row in discovered_editions:
                edition = str(row["edition"])
                path = Path(str(row["path"]))
                if edition in self.datasets or not row.get("rules_available"):
                    continue
                self.datasets[edition] = load_edition_dataset(path, edition=edition)
        self.available_editions = available_edition_rows(
            self.datasets,
            active_edition=self.rules_edition,
            discovered_rows=discovered_editions,
        )
        self.ml_model_paths = {
            edition: self._model_path_for_loaded_edition(edition, explicit_model_path=model_path)
            for edition in self.datasets
        }
        self.ml_models = {
            edition: load_advisory_model(path)
            for edition, path in self.ml_model_paths.items()
        }

    def dataset_for_edition(self, edition: Optional[str] = None) -> EditionDataset:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        dataset = self.datasets.get(requested)
        if dataset is None:
            available = ", ".join(sorted(self.datasets))
            raise ValueError(f"Edition {requested!r} is not loaded; loaded editions: {available}")
        return dataset

    def require_unit(self, name: str = "", *, unit_id: Optional[str] = None, edition: Optional[str] = None) -> UnitProfile:
        return self.dataset_for_edition(edition).require_unit(name, unit_id=unit_id)

    def ml_model_for_edition(self, edition: Optional[str] = None) -> Optional[dict[str, Any]]:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        return self.ml_models.get(requested)

    def ml_model_path_for_edition(self, edition: Optional[str] = None) -> Path:
        requested = str(edition or self.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
        return self.ml_model_paths.get(requested, MODEL_ROOT / requested / "matchup_centroid_model.json")

    def ml_model_dir_for_edition(self, edition: Optional[str] = None) -> Path:
        return self.ml_model_path_for_edition(edition).parent

    def ml_model_status(self) -> dict[str, Any]:
        return {
            edition: model_status(model)
            for edition, model in self.ml_models.items()
        }

    def _model_path_for_loaded_edition(self, edition: str, *, explicit_model_path: Optional[Path]) -> Path:
        if explicit_model_path and edition == self.rules_edition:
            return Path(explicit_model_path)
        return MODEL_ROOT / edition / "matchup_centroid_model.json"


def default_data_dir() -> Optional[Path]:
    if DEFAULT_CSV_DIR.exists():
        return DEFAULT_CSV_DIR
    if LEGACY_CSV_DIR.exists():
        return LEGACY_CSV_DIR
    return None


def load_edition_dataset(data_dir: Path, *, edition: Optional[str] = None) -> EditionDataset:
    metadata = data_review_service.load_json_file(data_dir / "metadata.json")
    resolved_edition = edition or rules_edition_from_metadata(metadata)
    return EditionDataset(
        edition=resolved_edition,
        data_dir=data_dir,
        source=str(data_dir),
        units=load_units_from_directory(data_dir),
        metadata=metadata,
    )


def available_edition_rows(
    datasets: Dict[str, EditionDataset],
    *,
    active_edition: str,
    discovered_rows: Optional[list[Dict[str, Any]]] = None,
) -> list[Dict[str, Any]]:
    return edition_service.available_edition_rows(
        datasets,
        active_edition=active_edition,
        discovered_rows=discovered_rows,
    )


def discover_edition_data_dirs(data_root: Path, *, active_data_dir: Optional[Path] = None) -> list[Dict[str, Any]]:
    return edition_service.discover_edition_data_dirs(
        data_root,
        active_data_dir=active_data_dir,
        default_edition=DEFAULT_EDITION,
    )


def edition_data_info(
    *,
    edition: str,
    data_dir: Optional[Path],
    metadata: Dict[str, Any],
    active_data_dir: Optional[Path] = None,
    active_edition: Optional[str] = None,
    loaded: bool = False,
) -> Dict[str, Any]:
    return edition_service.edition_data_info(
        edition=edition,
        data_dir=data_dir,
        metadata=metadata,
        active_data_dir=active_data_dir,
        active_edition=active_edition,
        loaded=loaded,
    )


def edition_label(edition: str) -> str:
    return edition_service.edition_label(edition)


def same_path(left: Path, right: Optional[Path]) -> bool:
    return edition_service.same_path(left, right)


def rules_edition_from_metadata(metadata: Optional[Dict[str, Any]]) -> str:
    return edition_service.rules_edition_from_metadata(metadata, default=DEFAULT_EDITION)


def supported_rules_editions_from_metadata(metadata: Optional[Dict[str, Any]]) -> list[str]:
    return edition_service.supported_rules_editions_from_metadata(metadata)


def requested_rules_edition(value: Any, *, state: AppState) -> str:
    edition = str(value or state.rules_edition or DEFAULT_EDITION).strip() or DEFAULT_EDITION
    dataset = state.dataset_for_edition(edition)
    if edition not in dataset.supported_rules_editions:
        supported = ", ".join(dataset.supported_rules_editions)
        raise ValueError(f"Edition {edition!r} is not available for this dataset; available editions: {supported}")
    get_ruleset(edition)
    return edition
