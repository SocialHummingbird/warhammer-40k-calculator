from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from . import api_payloads as api_payload_service
from . import battlefield as battlefield_service
from . import data_review as data_review_service
from . import matchup_payloads as payload_service
from . import unit_search as unit_search_service
from .rules import ruleset_registry_payload
from .web_state import AppState, requested_rules_edition


class WebApiNotFound(LookupError):
    pass


def health_payload(state: AppState) -> Dict[str, Any]:
    return {
        "ok": True,
        "source": state.source,
        "units": len(state.units),
        "source_info": data_review_service.source_info_from_metadata(state.metadata),
        "available_editions": state.available_editions,
        "rulesets": ruleset_registry_payload(),
        "ml_models": state.ml_model_status(),
    }


def data_review_payload_from_query(query: Dict[str, list[str]], *, state: AppState) -> Dict[str, Any]:
    dataset = state.dataset_for_edition(_query_value(query, "edition") or None)
    return data_review_service.data_review_payload(
        dataset.data_dir,
        edition=dataset.edition,
        model_dir=state.ml_model_dir_for_edition(dataset.edition),
        model_path=state.ml_model_path_for_edition(dataset.edition),
    )


def review_file_download(path: str, *, state: AppState) -> tuple[Path, str]:
    edition, filename = data_review_service.download_file_request_parts(
        path,
        prefix="/api/review-files/",
        default_edition=state.rules_edition,
    )
    dataset = state.dataset_for_edition(edition)
    if not dataset.data_dir or filename not in data_review_service.REVIEW_FILE_LABELS:
        raise WebApiNotFound("Unknown review file")
    return dataset.data_dir / filename, data_review_service.review_file_content_type(filename)


def model_file_download(path: str, *, state: AppState) -> tuple[Path, str]:
    edition, filename = data_review_service.download_file_request_parts(
        path,
        prefix="/api/ml-model-files/",
        default_edition=state.rules_edition,
    )
    state.dataset_for_edition(edition)
    selected_model = state.ml_model_path_for_edition(edition)
    selected_filenames = {selected_model.name, selected_model.with_suffix(".md").name}
    if filename not in data_review_service.MODEL_FILE_LABELS and filename not in selected_filenames:
        raise WebApiNotFound("Unknown ML model file")
    return state.ml_model_dir_for_edition(edition) / filename, data_review_service.review_file_content_type(filename)


def units_payload_from_query(query: Dict[str, list[str]], *, state: AppState) -> Dict[str, Any]:
    dataset = state.dataset_for_edition(_query_value(query, "edition") or None)
    units = unit_search_service.search_units(
        dataset.units.values(),
        text=_query_value(query, "q"),
        faction=_query_value(query, "faction"),
        limit=api_payload_service.query_limit(_query_value(query, "limit", "300")),
    )
    return {
        "units": [payload_service.unit_summary(unit) for unit in units],
        "factions": unit_search_service.unit_factions(dataset.units.values()),
        "edition": dataset.edition,
    }


def unit_payload_from_query(query: Dict[str, list[str]], *, state: AppState) -> Dict[str, Any]:
    dataset = state.dataset_for_edition(_query_value(query, "edition") or None)
    try:
        unit = dataset.require_unit(
            _query_value(query, "name"),
            unit_id=_query_value(query, "id") or None,
        )
    except KeyError as exc:
        raise WebApiNotFound("Unknown unit") from exc
    return {"unit": payload_service.unit_detail(unit)}


def battlefield_templates_payload() -> Dict[str, Any]:
    return battlefield_service.battlefield_templates_payload()


def battlefield_validate_army_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.validate_army_payload(payload, dataset)
    result["edition"] = edition
    return result


def battlefield_validate_state_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.validate_state_payload(payload, dataset)
    result["edition"] = edition
    return result


def battlefield_actions_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.actions_payload(payload, dataset, edition=edition)
    result["edition"] = edition
    return result


def battlefield_resolve_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.resolve_payload(payload, dataset, edition=edition)
    result["edition"] = edition
    return result


def battlefield_advance_phase_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.advance_phase_payload(payload, dataset)
    result["edition"] = edition
    return result


def battlefield_ai_plan_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.ai_plan_payload(payload, dataset, edition=edition)
    result["edition"] = edition
    return result


def battlefield_autoplay_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.autoplay_payload(payload, dataset, edition=edition)
    result["edition"] = edition
    return result


def battlefield_new_state_payload(payload: Dict[str, Any], *, state: AppState) -> Dict[str, Any]:
    edition = requested_rules_edition(payload.get("edition"), state=state)
    dataset = state.dataset_for_edition(edition)
    result = battlefield_service.new_state_payload(payload, dataset)
    result["edition"] = edition
    return result


def _query_value(query: Dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return values[0] if values else default
