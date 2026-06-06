"""Accessibility-first helpers for WeChat desktop automation."""

from __future__ import annotations

import logging
import platform
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence


class WeChatAccessibilityService:
    """Query platform adapters for visible UI elements before falling back to OCR."""

    def __init__(self, dep_manager=None, logger: Optional[logging.Logger] = None):
        self.dep_manager = dep_manager
        self.logger = logger or logging.getLogger(
            "mcp-server-wechat-viewer-mcp.accessibility_service"
        )

    def _iter_adapters(self) -> Iterable[Any]:
        if not self.dep_manager:
            return []

        try:
            from mcp_core.dependency_types import MACOS_ADAPTER, WINDOWS_ADAPTER
        except Exception:
            return []

        adapters = []
        for dep_name in (MACOS_ADAPTER, WINDOWS_ADAPTER):
            try:
                adapter = self.dep_manager.get_dependency(dep_name)
            except Exception as exc:
                self.logger.debug("Accessibility adapter %s unavailable: %s", dep_name, exc)
                continue
            if adapter:
                adapters.append(adapter)
        return adapters

    def _normalized(self, value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    def _similarity(self, left: Any, right: Any) -> float:
        norm_left = self._normalized(left)
        norm_right = self._normalized(right)
        if not norm_left or not norm_right:
            return 0.0
        if norm_left == norm_right:
            return 1.0
        return SequenceMatcher(None, norm_left, norm_right).ratio()

    def _element_text(self, element: Dict[str, Any]) -> str:
        return (
            element.get("text")
            or element.get("name")
            or element.get("description")
            or element.get("value")
            or ""
        ).strip()

    def _element_center(self, element: Dict[str, Any]) -> Optional[tuple[int, int]]:
        x = element.get("x")
        y = element.get("y")
        width = element.get("width")
        height = element.get("height")
        if x is None or y is None:
            return None
        width = max(int(width or 0), 1)
        height = max(int(height or 0), 1)
        return (int(x) + width // 2, int(y) + height // 2)

    def _point_in_region(
        self,
        x: int,
        y: int,
        region: Optional[Dict[str, int]],
    ) -> bool:
        if not region:
            return True
        return (
            region["X"] <= x <= region["X"] + region["Width"]
            and region["Y"] <= y <= region["Y"] + region["Height"]
        )

    def _role_allowed(
        self,
        element: Dict[str, Any],
        allowed_roles: Optional[Sequence[str]],
    ) -> bool:
        if not allowed_roles:
            return True
        allowed = {role.lower() for role in allowed_roles}
        role = self._normalized(element.get("role"))
        subrole = self._normalized(element.get("subrole"))
        return role in allowed or subrole in allowed

    def visible_elements(
        self,
        *,
        app_name: str = "WeChat",
        window_title: Optional[str] = None,
        region: Optional[Dict[str, int]] = None,
        allowed_roles: Optional[Sequence[str]] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        """Return visible accessibility elements for the current WeChat surface."""
        for adapter in self._iter_adapters():
            snapshotter = getattr(adapter, "snapshot_visible_elements", None)
            if not callable(snapshotter):
                continue
            try:
                elements = snapshotter(
                    app_name=app_name,
                    window_title=window_title,
                    max_items=limit,
                )
            except Exception as exc:
                self.logger.debug(
                    "Accessibility snapshot failed via %s: %s",
                    type(adapter).__name__,
                    exc,
                )
                continue

            filtered: List[Dict[str, Any]] = []
            for element in elements or []:
                center = self._element_center(element)
                if center is None:
                    continue
                if not self._point_in_region(center[0], center[1], region):
                    continue
                if not self._role_allowed(element, allowed_roles):
                    continue
                filtered.append(element)

            if filtered:
                filtered.sort(
                    key=lambda item: (
                        int(item.get("y", 0)),
                        int(item.get("x", 0)),
                    )
                )
                return filtered
        return []

    def collect_texts(
        self,
        *,
        app_name: str = "WeChat",
        window_title: Optional[str] = None,
        region: Optional[Dict[str, int]] = None,
        allowed_roles: Optional[Sequence[str]] = None,
        limit: int = 250,
    ) -> List[str]:
        texts: List[str] = []
        seen = set()
        for element in self.visible_elements(
            app_name=app_name,
            window_title=window_title,
            region=region,
            allowed_roles=allowed_roles,
            limit=limit,
        ):
            text = self._element_text(element)
            key = self._normalized(text)
            if text and key and key not in seen:
                seen.add(key)
                texts.append(text)
        return texts

    def find_named_element(
        self,
        targets: Sequence[str] | str,
        *,
        app_name: str = "WeChat",
        window_title: Optional[str] = None,
        region: Optional[Dict[str, int]] = None,
        allowed_roles: Optional[Sequence[str]] = None,
        min_similarity: float = 0.72,
        blocked_terms: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(targets, str):
            targets = [targets]

        blocked_terms = tuple(blocked_terms or ())

        for adapter in self._iter_adapters():
            best_match: Optional[Dict[str, Any]] = None
            best_score = 0.0

            snapshotter = getattr(adapter, "snapshot_visible_elements", None)
            if callable(snapshotter):
                elements = self.visible_elements(
                    app_name=app_name,
                    window_title=window_title,
                    region=region,
                    allowed_roles=allowed_roles,
                )
                for element in elements:
                    text = self._element_text(element)
                    normalized_text = self._normalized(text)
                    if not normalized_text:
                        continue
                    if any(term and term.lower() in normalized_text for term in blocked_terms):
                        continue

                    target_score = 0.0
                    matched_target = None
                    for target in targets:
                        normalized_target = self._normalized(target)
                        if not normalized_target:
                            continue
                        if normalized_text == normalized_target:
                            score = 1.0
                        elif normalized_target in normalized_text:
                            score = 0.96
                        else:
                            score = self._similarity(text, target)
                        if score > target_score:
                            target_score = score
                            matched_target = target

                    if target_score < min_similarity:
                        continue

                    role_bonus = 0.04 if self._role_allowed(element, allowed_roles) else 0.0
                    score = min(0.99, target_score + role_bonus)
                    if score <= best_score:
                        continue

                    center = self._element_center(element)
                    if center is None:
                        continue
                    best_score = score
                    best_match = {
                        "x": center[0],
                        "y": center[1],
                        "width": max(int(element.get("width", 1) or 1), 1),
                        "height": max(int(element.get("height", 1) or 1), 1),
                        "text": text,
                        "role": element.get("role"),
                        "subrole": element.get("subrole"),
                        "confidence": score,
                        "method": "accessibility_snapshot",
                        "matched_target": matched_target,
                        "source": type(adapter).__name__,
                    }

            if best_match:
                return best_match

            finder = getattr(adapter, "find_element_by_name", None)
            if not callable(finder):
                continue

            for target in targets:
                try:
                    location = finder(
                        target,
                        app_name,
                        region=region,
                        window_title=window_title,
                        allowed_roles=allowed_roles,
                    )
                except TypeError:
                    try:
                        location = finder(target, app_name)
                    except Exception as exc:
                        self.logger.debug(
                            "Fallback accessibility lookup failed via %s: %s",
                            type(adapter).__name__,
                            exc,
                        )
                        continue
                except Exception as exc:
                    self.logger.debug(
                        "Accessibility lookup failed via %s: %s",
                        type(adapter).__name__,
                        exc,
                    )
                    continue

                if not location:
                    continue

                center_x = int(location.x + max(location.width, 1) / 2)
                center_y = int(location.y + max(location.height, 1) / 2)
                if not self._point_in_region(center_x, center_y, region):
                    continue
                return {
                    "x": center_x,
                    "y": center_y,
                    "width": max(int(getattr(location, "width", 1) or 1), 1),
                    "height": max(int(getattr(location, "height", 1) or 1), 1),
                    "text": target,
                    "confidence": getattr(location, "confidence", 0.88),
                    "method": "accessibility_lookup",
                    "source": type(adapter).__name__,
                }

        return None

    def invoke_named_element(
        self,
        targets: Sequence[str] | str,
        *,
        app_name: str = "WeChat",
        window_title: Optional[str] = None,
        region: Optional[Dict[str, int]] = None,
        allowed_roles: Optional[Sequence[str]] = None,
        min_similarity: float = 0.72,
        blocked_terms: Optional[Sequence[str]] = None,
        actions: Optional[Sequence[str]] = None,
    ) -> bool:
        if isinstance(targets, str):
            targets = [targets]
        target_list = [target for target in targets if self._normalized(target)]
        if not target_list:
            return False

        for adapter in self._iter_adapters():
            invoker = getattr(adapter, "invoke_named_element", None)
            if not callable(invoker):
                continue
            try:
                if invoker(
                    list(target_list),
                    app_name=app_name,
                    window_title=window_title,
                    region=region,
                    allowed_roles=list(allowed_roles) if allowed_roles else None,
                    min_similarity=min_similarity,
                    blocked_terms=list(blocked_terms) if blocked_terms else None,
                    actions=list(actions) if actions else None,
                ):
                    return True
            except Exception as exc:
                self.logger.debug(
                    "Accessibility invoke failed via %s: %s",
                    type(adapter).__name__,
                    exc,
                )
        return False

    def get_accessibility_status(self, *, app_name: str = "WeChat") -> Dict[str, Any]:
        default_status = {
            "platform": platform.system().lower(),
            "adapter": None,
            "app_name": app_name,
            "ax_runtime_available": False,
            "native_ax_trusted": False,
            "native_ax_ready": False,
            "system_events_accessible": False,
            "system_events_ui_enabled": False,
            "system_events_ready": False,
            "assistive_access_denied": False,
            "system_events_error": "",
            "accessibility_available": False,
            "permission_required": False,
            "recommended_backend": "ocr_only",
            "settings_hint": None,
            "settings_url": None,
        }

        for adapter in self._iter_adapters():
            getter = getattr(adapter, "get_accessibility_status", None)
            if not callable(getter):
                continue
            try:
                status = getter(app_name=app_name)
            except TypeError:
                try:
                    status = getter()
                except Exception as exc:
                    self.logger.debug(
                        "Accessibility status probe failed via %s: %s",
                        type(adapter).__name__,
                        exc,
                    )
                    continue
            except Exception as exc:
                self.logger.debug(
                    "Accessibility status probe failed via %s: %s",
                    type(adapter).__name__,
                    exc,
                )
                continue

            if isinstance(status, dict):
                merged = dict(default_status)
                merged.update(status)
                merged["adapter"] = merged.get("adapter") or type(adapter).__name__
                return merged

        return default_status

    def request_accessibility_permission(self, *, app_name: str = "WeChat") -> Dict[str, Any]:
        default_response = {
            "success": False,
            "action_taken": "unsupported",
            "settings_opened": False,
            "status": self.get_accessibility_status(app_name=app_name),
            "message": "No accessibility adapter can request permissions on this platform.",
        }

        for adapter in self._iter_adapters():
            requester = getattr(adapter, "request_accessibility_permission", None)
            if not callable(requester):
                continue
            try:
                response = requester(app_name=app_name)
            except TypeError:
                try:
                    response = requester()
                except Exception as exc:
                    self.logger.debug(
                        "Accessibility permission request failed via %s: %s",
                        type(adapter).__name__,
                        exc,
                    )
                    continue
            except Exception as exc:
                self.logger.debug(
                    "Accessibility permission request failed via %s: %s",
                    type(adapter).__name__,
                    exc,
                )
                continue

            if isinstance(response, dict):
                merged = dict(default_response)
                merged.update(response)
                if not isinstance(merged.get("status"), dict):
                    merged["status"] = self.get_accessibility_status(app_name=app_name)
                return merged

        return default_response
