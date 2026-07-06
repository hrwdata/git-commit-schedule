from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from . import git_ops


CONFIG_PREFIX = "git-commit-schedule"


@dataclass(frozen=True)
class Config:
    enabled: bool = False
    timezone: str = "America/Chicago"
    window_start: time = time(17, 30)
    window_end: time = time(21, 30)
    min_gap_minutes: int = 17
    max_gap_minutes: int = 41
    fallback_hook: bool = True
    enforce_push: bool = True
    auto_push: bool = False
    allow_merge_rewrite: bool = False
    allow_signed_rewrite: bool = False


DEFAULT_CONFIG = Config()


def parse_hhmm(value: str, default: time) -> time:
    try:
        hour_text, minute_text = value.split(":", 1)
        return time(int(hour_text), int(minute_text))
    except (ValueError, TypeError):
        return default


def format_hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def _config_key(name: str) -> str:
    return f"{CONFIG_PREFIX}.{name}"


def _get_bool(name: str, default: bool) -> bool:
    value = git_ops.git_config_get(_config_key(name))
    if value is None:
        return default
    return value.strip().lower() == "true"


def _get_int(name: str, default: int) -> int:
    value = git_ops.git_config_get(_config_key(name))
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_str(name: str, default: str) -> str:
    return git_ops.git_config_get(_config_key(name)) or default


def load_effective_config() -> Config:
    cfg = Config(
        enabled=_get_bool("enabled", DEFAULT_CONFIG.enabled),
        timezone=_get_str("timezone", DEFAULT_CONFIG.timezone),
        window_start=parse_hhmm(
            _get_str("windowStart", format_hhmm(DEFAULT_CONFIG.window_start)),
            DEFAULT_CONFIG.window_start,
        ),
        window_end=parse_hhmm(
            _get_str("windowEnd", format_hhmm(DEFAULT_CONFIG.window_end)),
            DEFAULT_CONFIG.window_end,
        ),
        min_gap_minutes=_get_int("minGapMinutes", DEFAULT_CONFIG.min_gap_minutes),
        max_gap_minutes=_get_int("maxGapMinutes", DEFAULT_CONFIG.max_gap_minutes),
        fallback_hook=_get_bool("fallbackHook", DEFAULT_CONFIG.fallback_hook),
        enforce_push=_get_bool("enforcePush", DEFAULT_CONFIG.enforce_push),
        auto_push=_get_bool("autoPush", DEFAULT_CONFIG.auto_push),
        allow_merge_rewrite=_get_bool(
            "allowMergeRewrite", DEFAULT_CONFIG.allow_merge_rewrite
        ),
        allow_signed_rewrite=_get_bool(
            "allowSignedRewrite", DEFAULT_CONFIG.allow_signed_rewrite
        ),
    )
    validate_config(cfg)
    return cfg


def validate_config(cfg: Config) -> None:
    if cfg.window_start >= cfg.window_end:
        raise RuntimeError("windowStart must be earlier than windowEnd")
    if cfg.min_gap_minutes <= 0:
        raise RuntimeError("minGapMinutes must be positive")
    if cfg.max_gap_minutes < cfg.min_gap_minutes:
        raise RuntimeError("maxGapMinutes must be greater than or equal to minGapMinutes")


def config_provenance_lines() -> list[str]:
    return git_ops.git_config_entries(r"^git-commit-schedule\.")


def _write_if_missing(name: str, value: str) -> None:
    if git_ops.git_config_get(_config_key(name), local_only=True) is None:
        git_ops.git_config_set(_config_key(name), value, local_only=True)


def ensure_local_defaults() -> None:
    _write_if_missing("enabled", str(DEFAULT_CONFIG.enabled).lower())
    _write_if_missing("timezone", DEFAULT_CONFIG.timezone)
    _write_if_missing("windowStart", format_hhmm(DEFAULT_CONFIG.window_start))
    _write_if_missing("windowEnd", format_hhmm(DEFAULT_CONFIG.window_end))
    _write_if_missing("minGapMinutes", str(DEFAULT_CONFIG.min_gap_minutes))
    _write_if_missing("maxGapMinutes", str(DEFAULT_CONFIG.max_gap_minutes))
    _write_if_missing("fallbackHook", str(DEFAULT_CONFIG.fallback_hook).lower())
    _write_if_missing("enforcePush", str(DEFAULT_CONFIG.enforce_push).lower())
    _write_if_missing("autoPush", str(DEFAULT_CONFIG.auto_push).lower())
    _write_if_missing(
        "allowMergeRewrite", str(DEFAULT_CONFIG.allow_merge_rewrite).lower()
    )
    _write_if_missing(
        "allowSignedRewrite", str(DEFAULT_CONFIG.allow_signed_rewrite).lower()
    )


def write_repo_config(
    *,
    enabled: bool | None = None,
    auto_push: bool | None = None,
    enforce_push: bool | None = None,
) -> None:
    ensure_local_defaults()
    if enabled is not None:
        git_ops.git_config_set(_config_key("enabled"), str(enabled).lower(), local_only=True)
    if auto_push is not None:
        git_ops.git_config_set(_config_key("autoPush"), str(auto_push).lower(), local_only=True)
    if enforce_push is not None:
        git_ops.git_config_set(
            _config_key("enforcePush"), str(enforce_push).lower(), local_only=True
        )

