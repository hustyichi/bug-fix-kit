from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .curl import ParsedRequestSample


@dataclass(frozen=True)
class ParameterMapping:
    name: str
    locations: list[str]
    required: bool
    default: str
    source: str = "sample"


def _flatten_dict(value: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    flattened: list[tuple[str, Any]] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.extend(_flatten_dict(item, path))
        else:
            flattened.append((path, item))
    return flattened


def _mapping_default(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text in {"file", "project", "true", "false"}:
        return text
    return "sample"


def _is_optional_mapping(name: str) -> bool:
    return name in {"eval", "stream", "model", "merge_preference", "merge_strategy", "resume", "answers"}


def _param_name_for_path(path: str) -> str:
    parts = path.split(".")
    if len(parts) == 1:
        return parts[0]
    if parts[0] in {"source", "target", "base"}:
        return f"{parts[0]}_{'_'.join(parts[1:])}"
    return "_".join(parts)


def _append_mapping(
    mappings: list[ParameterMapping],
    seen: set[str],
    *,
    name: str,
    locations: list[str],
    value: Any,
    source: str = "sample",
) -> None:
    if name in seen:
        return
    seen.add(name)
    mappings.append(
        ParameterMapping(
            name=name,
            locations=locations,
            required=not _is_optional_mapping(name),
            default=_mapping_default(value),
            source=source,
        )
    )


def parameter_mappings_from_sample(sample: ParsedRequestSample | None) -> list[ParameterMapping]:
    if sample is None:
        return []
    mappings: list[ParameterMapping] = []
    seen: set[str] = set()
    if isinstance(sample.body, dict):
        if "model" in sample.body:
            _append_mapping(mappings, seen, name="model", locations=["body.model"], value=sample.body.get("model"))
        if "stream" in sample.body:
            _append_mapping(mappings, seen, name="stream", locations=["body.stream"], value=sample.body.get("stream"))
    inner = sample.inner_payload or {}
    if "eval" in inner:
        _append_mapping(mappings, seen, name="eval", locations=["text.eval"], value=inner.get("eval"), source="sample+code")
    params = inner.get("params")
    if not isinstance(params, dict):
        return mappings

    for shared_name in ("code", "biz_type", "project_code", "tenant_code", "project_sub_type"):
        source = params.get("source")
        target = params.get("target")
        if isinstance(source, dict) and isinstance(target, dict) and source.get(shared_name) == target.get(shared_name):
            _append_mapping(
                mappings,
                seen,
                name=shared_name,
                locations=[f"text.params.source.{shared_name}", f"text.params.target.{shared_name}"],
                value=source.get(shared_name),
            )

    for path, value in _flatten_dict(params):
        _append_mapping(
            mappings,
            seen,
            name=_param_name_for_path(path),
            locations=[f"text.params.{path}"],
            value=value,
            source="sample+code" if path in {"task_id", "merge_code", "merge_type"} else "sample",
        )
    return mappings


def parse_params(raw_params: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    positional: list[str] = []
    for item in raw_params:
        if "=" in item:
            key, value = item.split("=", 1)
            params[key] = value
        else:
            positional.append(item)
    if positional and "value" not in params:
        params["value"] = " ".join(positional)
    return params
