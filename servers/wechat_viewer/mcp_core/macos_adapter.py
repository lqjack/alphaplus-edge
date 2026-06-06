"""
macOS Adapter for Universal Automation (Enhanced)

Implements platform-specific automation for macOS using Accessibility APIs (AXUIElement).
Supports targeted application control via AppProfiles and robust AppleScript searching.
"""
import ctypes
import platform
import logging
from difflib import SequenceMatcher
from typing import Dict, Optional, Any, Tuple, List
from .interfaces import IPlatformAdapter, PlatformCapabilities, ElementLocation
from .app_profile import get_app_registry


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

class MacOSAccessibilityAdapter(IPlatformAdapter):
    """macOS-specific universal automation adapter with deep search capabilities"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-universal-automation.macos_adapter")
        self.registry = get_app_registry()
        self._ax_runtime_available = False
        self._ax_trust_denied_logged = False
        self._assistive_access_denied_logged = False
        self._initialize_ax_runtime()
        self._initialize_accessibility_framework()

    def _initialize_ax_runtime(self):
        try:
            if platform.system().lower() != "darwin":
                return

            self._ax = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            self._cf = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
            )

            self._cf_string_encoding_utf8 = 0x08000100
            self._k_cf_number_double_type = 13
            self._k_ax_value_cgpoint_type = 1
            self._k_ax_value_cgsize_type = 2

            self._cf.CFStringCreateWithCString.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_uint32,
            ]
            self._cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            self._cf.CFStringGetLength.argtypes = [ctypes.c_void_p]
            self._cf.CFStringGetLength.restype = ctypes.c_long
            self._cf.CFStringGetCString.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_long,
                ctypes.c_uint32,
            ]
            self._cf.CFStringGetCString.restype = ctypes.c_bool
            self._cf.CFStringGetTypeID.restype = ctypes.c_ulong
            self._cf.CFNumberGetTypeID.restype = ctypes.c_ulong
            self._cf.CFBooleanGetTypeID.restype = ctypes.c_ulong
            self._cf.CFArrayGetTypeID.restype = ctypes.c_ulong
            self._cf.CFGetTypeID.argtypes = [ctypes.c_void_p]
            self._cf.CFGetTypeID.restype = ctypes.c_ulong
            self._cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
            self._cf.CFArrayGetCount.restype = ctypes.c_long
            self._cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
            self._cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
            self._cf.CFCopyDescription.argtypes = [ctypes.c_void_p]
            self._cf.CFCopyDescription.restype = ctypes.c_void_p
            self._cf.CFNumberGetValue.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_void_p,
            ]
            self._cf.CFNumberGetValue.restype = ctypes.c_bool
            self._cf.CFRetain.argtypes = [ctypes.c_void_p]
            self._cf.CFRetain.restype = ctypes.c_void_p
            self._cf.CFRelease.argtypes = [ctypes.c_void_p]
            self._cf.CFRelease.restype = None

            self._ax.AXIsProcessTrusted.restype = ctypes.c_bool
            self._ax.AXUIElementCreateApplication.argtypes = [ctypes.c_int]
            self._ax.AXUIElementCreateApplication.restype = ctypes.c_void_p
            self._ax.AXUIElementCopyAttributeValue.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            self._ax.AXUIElementCopyAttributeValue.restype = ctypes.c_int
            self._ax.AXUIElementPerformAction.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            self._ax.AXUIElementPerformAction.restype = ctypes.c_int
            self._ax.AXUIElementCopyActionNames.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            self._ax.AXUIElementCopyActionNames.restype = ctypes.c_int
            self._ax.AXValueGetTypeID.restype = ctypes.c_ulong
            self._ax.AXUIElementGetTypeID.restype = ctypes.c_ulong
            self._ax.AXValueGetType.argtypes = [ctypes.c_void_p]
            self._ax.AXValueGetType.restype = ctypes.c_uint
            self._ax.AXValueGetValue.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
            ]
            self._ax.AXValueGetValue.restype = ctypes.c_bool

            self._cf_string_type_id = self._cf.CFStringGetTypeID()
            self._cf_number_type_id = self._cf.CFNumberGetTypeID()
            self._cf_boolean_type_id = self._cf.CFBooleanGetTypeID()
            self._cf_array_type_id = self._cf.CFArrayGetTypeID()
            self._ax_value_type_id = self._ax.AXValueGetTypeID()
            self._ax_element_type_id = self._ax.AXUIElementGetTypeID()
            self._ax_runtime_available = True
        except Exception as exc:
            self.logger.debug("Failed to initialize native AX runtime: %s", exc)
            self._ax_runtime_available = False

    def _initialize_accessibility_framework(self):
        try:
            if platform.system().lower() != "darwin":
                return
            probe = self._probe_system_events_accessibility()
            self._accessibility_available = (
                self._ax_is_trusted()
                or probe.get("system_events_ui_enabled", False)
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize accessibility: {e}")
            self._accessibility_available = False

    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            supports_accessibility_api=True,
            supports_ocr=True,
            supports_vision_llm=True,
            requires_permissions=["Accessibility", "Screen Recording"]
        )

    def _get_target_process_name(self, app_name: Optional[str]) -> str:
        target = app_name or "WeChat"
        profile = self.registry.get_profile(target)
        return profile.process_names[0] if profile else target

    def _applescript_string(self, value: Optional[str]) -> str:
        escaped = (value or "").replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _run_osascript(self, script: str) -> str:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            return ""
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if stderr:
                if "not allowed assistive access" in stderr.lower():
                    if not self._assistive_access_denied_logged:
                        self.logger.warning(
                            "macOS Accessibility snapshot denied by System Events. "
                            "Grant Accessibility permission to the current shell/python runtime or osascript."
                        )
                        self._assistive_access_denied_logged = True
                self.logger.debug("osascript failed: %s", stderr)
            return ""
        return (result.stdout or "").strip()

    def _normalized(self, value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    def _text_similarity(self, left: Any, right: Any) -> float:
        norm_left = self._normalized(left)
        norm_right = self._normalized(right)
        if not norm_left or not norm_right:
            return 0.0
        if norm_left == norm_right:
            return 1.0
        return SequenceMatcher(None, norm_left, norm_right).ratio()

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

    def _ax_is_trusted(self) -> bool:
        if not self._ax_runtime_available:
            return False
        try:
            trusted = bool(self._ax.AXIsProcessTrusted())
        except Exception as exc:
            self.logger.debug("AXIsProcessTrusted failed: %s", exc)
            return False

        if not trusted and not self._ax_trust_denied_logged:
            self.logger.warning(
                "Native macOS AX runtime is not trusted for the current Python process. "
                "Grant Accessibility permission to the terminal or python runtime to enable accessibility-first snapshots."
            )
            self._ax_trust_denied_logged = True
        return trusted

    def _probe_system_events_accessibility(self) -> Dict[str, Any]:
        status = {
            "system_events_accessible": False,
            "system_events_ui_enabled": False,
            "assistive_access_denied": False,
            "system_events_error": "",
        }
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            status["system_events_error"] = "subprocess_unavailable"
            return status

        script = 'tell application "System Events" to return UI elements enabled'
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            status["system_events_error"] = str(exc)
            return status

        stdout = (result.stdout or "").strip().lower()
        stderr = (result.stderr or "").strip()
        assistive_denied = "not allowed assistive access" in stderr.lower()
        status.update(
            {
                "system_events_accessible": result.returncode == 0,
                "system_events_ui_enabled": result.returncode == 0 and "true" in stdout,
                "assistive_access_denied": assistive_denied,
                "system_events_error": stderr,
            }
        )
        return status

    def get_accessibility_status(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        native_ax_trusted = self._ax_is_trusted()
        system_events_status = self._probe_system_events_accessibility()
        native_ax_ready = bool(self._ax_runtime_available and native_ax_trusted)
        system_events_ready = bool(
            system_events_status.get("system_events_accessible")
            and system_events_status.get("system_events_ui_enabled")
        )
        accessibility_available = native_ax_ready or system_events_ready
        assistive_access_denied = bool(
            system_events_status.get("assistive_access_denied")
            or (self._ax_runtime_available and not native_ax_trusted)
        )

        if native_ax_ready:
            recommended_backend = "native_ax"
        elif system_events_ready:
            recommended_backend = "system_events"
        else:
            recommended_backend = "ocr_only"

        return {
            "platform": platform.system().lower(),
            "adapter": type(self).__name__,
            "app_name": self._get_target_process_name(app_name),
            "ax_runtime_available": bool(self._ax_runtime_available),
            "native_ax_trusted": native_ax_trusted,
            "native_ax_ready": native_ax_ready,
            "system_events_accessible": bool(system_events_status.get("system_events_accessible")),
            "system_events_ui_enabled": bool(system_events_status.get("system_events_ui_enabled")),
            "system_events_ready": system_events_ready,
            "assistive_access_denied": assistive_access_denied,
            "system_events_error": system_events_status.get("system_events_error", ""),
            "accessibility_available": accessibility_available,
            "permission_required": not accessibility_available,
            "recommended_backend": recommended_backend,
            "settings_hint": "System Settings > Privacy & Security > Accessibility",
            "settings_url": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        }

    def request_accessibility_permission(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        status = self.get_accessibility_status(app_name=app_name)
        if status.get("accessibility_available"):
            return {
                "success": True,
                "action_taken": "already_available",
                "settings_opened": False,
                "status": status,
            }

        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            return {
                "success": False,
                "action_taken": "no_subprocess",
                "settings_opened": False,
                "status": status,
                "message": "subprocess dependency unavailable",
            }

        settings_url = status.get("settings_url") or (
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        )
        try:
            result = subprocess.run(
                ["open", settings_url],
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            return {
                "success": False,
                "action_taken": "open_failed",
                "settings_opened": False,
                "status": status,
                "message": str(exc),
            }

        message = (
            "Opened macOS Accessibility settings. Grant access to the current terminal/python runtime, "
            "then rerun wechat_check_accessibility."
        )
        return {
            "success": result.returncode == 0,
            "action_taken": "opened_settings" if result.returncode == 0 else "open_failed",
            "settings_opened": result.returncode == 0,
            "status": self.get_accessibility_status(app_name=app_name),
            "message": message if result.returncode == 0 else (result.stderr or result.stdout or "").strip(),
        }

    def _cf_release(self, value_ref: Optional[int]) -> None:
        if self._ax_runtime_available and value_ref:
            try:
                self._cf.CFRelease(value_ref)
            except Exception:
                pass

    def _cf_string(self, value: str) -> Optional[int]:
        if not self._ax_runtime_available:
            return None
        try:
            return self._cf.CFStringCreateWithCString(
                None,
                (value or "").encode("utf-8"),
                self._cf_string_encoding_utf8,
            )
        except Exception as exc:
            self.logger.debug("Failed to create CFString for %r: %s", value, exc)
            return None

    def _cf_string_to_python(self, value_ref: Optional[int]) -> str:
        if not value_ref or not self._ax_runtime_available:
            return ""
        try:
            length = int(self._cf.CFStringGetLength(value_ref))
            buffer = ctypes.create_string_buffer(max(4, length * 4 + 1))
            if self._cf.CFStringGetCString(
                value_ref,
                buffer,
                len(buffer),
                self._cf_string_encoding_utf8,
            ):
                return buffer.value.decode("utf-8", errors="ignore")
        except Exception as exc:
            self.logger.debug("Failed converting CFString to python string: %s", exc)
        return ""

    def _cf_description(self, value_ref: Optional[int]) -> str:
        if not value_ref or not self._ax_runtime_available:
            return ""
        desc_ref = None
        try:
            desc_ref = self._cf.CFCopyDescription(value_ref)
            return self._cf_string_to_python(desc_ref)
        except Exception as exc:
            self.logger.debug("Failed to copy CF description: %s", exc)
            return ""
        finally:
            self._cf_release(desc_ref)

    def _cf_number_to_python(self, value_ref: Optional[int]) -> Optional[float]:
        if not value_ref or not self._ax_runtime_available:
            return None
        try:
            output = ctypes.c_double()
            if self._cf.CFNumberGetValue(
                value_ref,
                self._k_cf_number_double_type,
                ctypes.byref(output),
            ):
                return float(output.value)
        except Exception as exc:
            self.logger.debug("Failed converting CFNumber to python number: %s", exc)
        return None

    def _cf_value_to_text(self, value_ref: Optional[int]) -> str:
        if not value_ref or not self._ax_runtime_available:
            return ""
        try:
            type_id = self._cf.CFGetTypeID(value_ref)
        except Exception as exc:
            self.logger.debug("Failed reading CF type id: %s", exc)
            return ""

        if type_id == self._cf_string_type_id:
            return self._cf_string_to_python(value_ref)
        if type_id == self._cf_number_type_id:
            number = self._cf_number_to_python(value_ref)
            return "" if number is None else str(number)
        if type_id == self._cf_boolean_type_id:
            return self._cf_description(value_ref).lower()
        if type_id in {self._cf_array_type_id, self._ax_element_type_id}:
            return ""
        return self._cf_description(value_ref)

    def _ax_copy_attribute_ref(self, element_ref: int, attribute: str) -> Optional[int]:
        if not self._ax_runtime_available or not element_ref:
            return None
        attr_ref = self._cf_string(attribute)
        if not attr_ref:
            return None
        value_ref = ctypes.c_void_p()
        try:
            error = int(
                self._ax.AXUIElementCopyAttributeValue(
                    element_ref,
                    attr_ref,
                    ctypes.byref(value_ref),
                )
            )
            if error != 0 or not value_ref.value:
                return None
            return int(value_ref.value)
        except Exception as exc:
            self.logger.debug("AX attribute copy failed for %s: %s", attribute, exc)
            return None
        finally:
            self._cf_release(attr_ref)

    def _ax_copy_attribute_text(self, element_ref: int, attribute: str) -> str:
        value_ref = self._ax_copy_attribute_ref(element_ref, attribute)
        if not value_ref:
            return ""
        try:
            return self._cf_value_to_text(value_ref).strip()
        finally:
            self._cf_release(value_ref)

    def _ax_copy_attribute_point(self, element_ref: int, attribute: str) -> Optional[Tuple[int, int]]:
        value_ref = self._ax_copy_attribute_ref(element_ref, attribute)
        if not value_ref:
            return None
        point = CGPoint()
        try:
            value_type = int(self._ax.AXValueGetType(value_ref))
            if value_type != self._k_ax_value_cgpoint_type:
                return None
            if not self._ax.AXValueGetValue(
                value_ref,
                self._k_ax_value_cgpoint_type,
                ctypes.byref(point),
            ):
                return None
            return (int(round(point.x)), int(round(point.y)))
        except Exception as exc:
            self.logger.debug("AX point extraction failed for %s: %s", attribute, exc)
            return None
        finally:
            self._cf_release(value_ref)

    def _ax_copy_attribute_size(self, element_ref: int, attribute: str) -> Optional[Tuple[int, int]]:
        value_ref = self._ax_copy_attribute_ref(element_ref, attribute)
        if not value_ref:
            return None
        size = CGSize()
        try:
            value_type = int(self._ax.AXValueGetType(value_ref))
            if value_type != self._k_ax_value_cgsize_type:
                return None
            if not self._ax.AXValueGetValue(
                value_ref,
                self._k_ax_value_cgsize_type,
                ctypes.byref(size),
            ):
                return None
            return (
                max(int(round(size.width)), 1),
                max(int(round(size.height)), 1),
            )
        except Exception as exc:
            self.logger.debug("AX size extraction failed for %s: %s", attribute, exc)
            return None
        finally:
            self._cf_release(value_ref)

    def _find_process_pid(self, process_name: str) -> Optional[int]:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            return None
        try:
            result = subprocess.run(
                ["pgrep", "-x", process_name],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line)
        except Exception as exc:
            self.logger.debug("Failed to resolve process pid for %s: %s", process_name, exc)
        return None

    def _select_ax_window(self, app_ref: int, window_title: Optional[str]) -> Optional[int]:
        candidates: List[int] = []
        for attribute in ("AXFocusedWindow", "AXMainWindow"):
            window_ref = self._ax_copy_attribute_ref(app_ref, attribute)
            if not window_ref:
                continue
            if window_title:
                title = self._ax_copy_attribute_text(window_ref, "AXTitle")
                if title and title != window_title:
                    self._cf_release(window_ref)
                    continue
            candidates.append(window_ref)

        if not candidates:
            windows_ref = self._ax_copy_attribute_ref(app_ref, "AXWindows")
            if windows_ref:
                try:
                    count = int(self._cf.CFArrayGetCount(windows_ref))
                    for index in range(count):
                        window_ref = int(self._cf.CFArrayGetValueAtIndex(windows_ref, index) or 0)
                        if not window_ref:
                            continue
                        if window_title:
                            title = self._ax_copy_attribute_text(window_ref, "AXTitle")
                            if title != window_title:
                                continue
                        window_ref = int(self._cf.CFRetain(window_ref) or 0)
                        if not window_ref:
                            continue
                        candidates.append(window_ref)
                        if window_title:
                            break
                finally:
                    self._cf_release(windows_ref)

        return candidates[0] if candidates else None

    def _walk_ax_tree(
        self,
        element_ref: int,
        output: List[Dict[str, Any]],
        max_items: int,
    ) -> None:
        if not element_ref or len(output) >= max_items:
            return

        role = self._ax_copy_attribute_text(element_ref, "AXRole")
        subrole = self._ax_copy_attribute_text(element_ref, "AXSubrole")
        title = self._ax_copy_attribute_text(element_ref, "AXTitle")
        description = self._ax_copy_attribute_text(element_ref, "AXDescription")
        value = self._ax_copy_attribute_text(element_ref, "AXValue")
        position = self._ax_copy_attribute_point(element_ref, "AXPosition")
        size = self._ax_copy_attribute_size(element_ref, "AXSize")
        primary_text = title or description or value

        if primary_text and position and size:
            output.append(
                {
                    "role": role or "AXUnknown",
                    "subrole": subrole,
                    "text": primary_text,
                    "name": title,
                    "description": description,
                    "value": value,
                    "x": int(position[0]),
                    "y": int(position[1]),
                    "width": max(int(size[0]), 1),
                    "height": max(int(size[1]), 1),
                    "method": "native_ax",
                }
            )
            if len(output) >= max_items:
                return

        children_ref = self._ax_copy_attribute_ref(element_ref, "AXChildren")
        if not children_ref:
            return
        try:
            count = int(self._cf.CFArrayGetCount(children_ref))
            for index in range(count):
                child_ref = int(self._cf.CFArrayGetValueAtIndex(children_ref, index) or 0)
                if not child_ref:
                    continue
                self._walk_ax_tree(child_ref, output, max_items)
                if len(output) >= max_items:
                    return
        finally:
            self._cf_release(children_ref)

    def _ax_role_allowed(
        self,
        role: str,
        subrole: str,
        allowed_roles: Optional[List[str]],
    ) -> bool:
        if not allowed_roles:
            return True
        allowed = {self._normalized(item) for item in allowed_roles}
        return self._normalized(role) in allowed or self._normalized(subrole) in allowed

    def _ax_target_score(
        self,
        candidate_text: str,
        targets: List[str],
    ) -> Tuple[float, Optional[str]]:
        normalized_candidate = self._normalized(candidate_text)
        best_score = 0.0
        best_target = None
        for target in targets:
            normalized_target = self._normalized(target)
            if not normalized_target:
                continue
            if normalized_candidate == normalized_target:
                score = 1.0
            elif normalized_target in normalized_candidate:
                score = 0.96
            else:
                score = self._text_similarity(candidate_text, target)
            if score > best_score:
                best_score = score
                best_target = target
        return best_score, best_target

    def _ax_copy_action_names(self, element_ref: int) -> List[str]:
        if not self._ax_runtime_available or not element_ref:
            return []
        action_names_ref = ctypes.c_void_p()
        try:
            error = int(
                self._ax.AXUIElementCopyActionNames(
                    element_ref,
                    ctypes.byref(action_names_ref),
                )
            )
            if error != 0 or not action_names_ref.value:
                return []
            action_array_ref = int(action_names_ref.value)
            if int(self._cf.CFGetTypeID(action_array_ref)) != self._cf_array_type_id:
                return []
            names: List[str] = []
            count = int(self._cf.CFArrayGetCount(action_array_ref))
            for index in range(count):
                item_ref = int(self._cf.CFArrayGetValueAtIndex(action_array_ref, index) or 0)
                if not item_ref:
                    continue
                name = self._cf_value_to_text(item_ref).strip()
                if name:
                    names.append(name)
            return names
        except Exception as exc:
            self.logger.debug("Failed to read AX action names: %s", exc)
            return []
        finally:
            self._cf_release(action_names_ref.value if action_names_ref.value else None)

    def _ax_perform_action(self, element_ref: int, action_name: str) -> bool:
        if not self._ax_runtime_available or not element_ref or not action_name:
            return False
        action_ref = self._cf_string(action_name)
        if not action_ref:
            return False
        try:
            error = int(self._ax.AXUIElementPerformAction(element_ref, action_ref))
            return error == 0
        except Exception as exc:
            self.logger.debug("Failed to perform AX action %s: %s", action_name, exc)
            return False
        finally:
            self._cf_release(action_ref)

    def _release_ax_match(self, match: Optional[Dict[str, Any]]) -> None:
        if isinstance(match, dict):
            self._cf_release(match.get("ref"))

    def _find_best_ax_element_ref(
        self,
        element_ref: int,
        targets: List[str],
        *,
        region: Optional[Dict[str, int]] = None,
        allowed_roles: Optional[List[str]] = None,
        min_similarity: float = 0.72,
        blocked_terms: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not element_ref:
            return None

        blocked = [self._normalized(term) for term in (blocked_terms or []) if term]
        best_match: Optional[Dict[str, Any]] = None

        role = self._ax_copy_attribute_text(element_ref, "AXRole")
        subrole = self._ax_copy_attribute_text(element_ref, "AXSubrole")
        title = self._ax_copy_attribute_text(element_ref, "AXTitle")
        description = self._ax_copy_attribute_text(element_ref, "AXDescription")
        value = self._ax_copy_attribute_text(element_ref, "AXValue")
        position = self._ax_copy_attribute_point(element_ref, "AXPosition")
        size = self._ax_copy_attribute_size(element_ref, "AXSize")
        candidate_text = title or description or value or ""

        if candidate_text and position and size and self._ax_role_allowed(role, subrole, allowed_roles):
            normalized_candidate = self._normalized(candidate_text)
            if not any(term in normalized_candidate for term in blocked):
                center_x = int(position[0] + max(size[0], 1) / 2)
                center_y = int(position[1] + max(size[1], 1) / 2)
                if self._point_in_region(center_x, center_y, region):
                    score, matched_target = self._ax_target_score(candidate_text, targets)
                    if score >= min_similarity:
                        retained_ref = int(self._cf.CFRetain(element_ref) or 0)
                        if retained_ref:
                            best_match = {
                                "ref": retained_ref,
                                "score": score,
                                "text": candidate_text,
                                "role": role,
                                "subrole": subrole,
                                "matched_target": matched_target,
                                "x": center_x,
                                "y": center_y,
                                "width": max(int(size[0]), 1),
                                "height": max(int(size[1]), 1),
                            }

        children_ref = self._ax_copy_attribute_ref(element_ref, "AXChildren")
        if not children_ref:
            return best_match
        try:
            count = int(self._cf.CFArrayGetCount(children_ref))
            for index in range(count):
                child_ref = int(self._cf.CFArrayGetValueAtIndex(children_ref, index) or 0)
                if not child_ref:
                    continue
                child_match = self._find_best_ax_element_ref(
                    child_ref,
                    targets,
                    region=region,
                    allowed_roles=allowed_roles,
                    min_similarity=min_similarity,
                    blocked_terms=blocked_terms,
                )
                if not child_match:
                    continue
                if not best_match or child_match["score"] > best_match["score"]:
                    self._release_ax_match(best_match)
                    best_match = child_match
                else:
                    self._release_ax_match(child_match)
        finally:
            self._cf_release(children_ref)
        return best_match

    def _snapshot_visible_elements_ax(
        self,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        max_items: int = 250,
    ) -> List[Dict[str, Any]]:
        if not self._ax_runtime_available or not self._ax_is_trusted():
            return []

        proc_name = self._get_target_process_name(app_name)
        pid = self._find_process_pid(proc_name)
        if not pid:
            return []

        try:
            app_ref = self._ax.AXUIElementCreateApplication(pid)
            if not app_ref:
                return []
            window_ref = self._select_ax_window(app_ref, window_title)
            if not window_ref:
                return []

            elements: List[Dict[str, Any]] = []
            self._walk_ax_tree(window_ref, elements, max(1, int(max_items)))
            return elements
        except Exception as exc:
            self.logger.debug("Native AX snapshot failed: %s", exc)
            return []

    def snapshot_visible_elements(
        self,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        max_items: int = 250,
    ) -> List[Dict[str, Any]]:
        """Return a lightweight AX snapshot for the front WeChat window."""
        native_elements = self._snapshot_visible_elements_ax(
            app_name=app_name,
            window_title=window_title,
            max_items=max_items,
        )
        if native_elements:
            return native_elements

        proc_name = self._get_target_process_name(app_name)
        quoted_process = self._applescript_string(proc_name)
        quoted_title = self._applescript_string(window_title or "")
        output = self._run_osascript(
            f'''
            on sanitizeText(valueText)
                try
                    set rawText to valueText as string
                on error
                    set rawText to ""
                end try
                set AppleScript's text item delimiters to {{linefeed, return, tab, "¦"}}
                set rawParts to every text item of rawText
                set AppleScript's text item delimiters to " "
                set cleanedText to rawParts as string
                set AppleScript's text item delimiters to ""
                return cleanedText
            end sanitizeText

            set maxItems to {max(1, int(max_items))}
            tell application "System Events"
                if not (exists process {quoted_process}) then
                    return ""
                end if
                tell process {quoted_process}
                    set targetWindow to missing value
                    if {quoted_title} is not "" then
                        repeat with candidateWindow in windows
                            try
                                if name of candidateWindow is {quoted_title} then
                                    set targetWindow to candidateWindow
                                    exit repeat
                                end if
                            end try
                        end repeat
                    end if
                    if targetWindow is missing value then
                        if (count of windows) is 0 then
                            return ""
                        end if
                        set targetWindow to front window
                    end if

                    set outputText to ""
                    set itemCount to 0
                    try
                        set elementList to {{targetWindow}} & (entire contents of targetWindow)
                    on error
                        set elementList to {{targetWindow}}
                    end try

                    repeat with el in elementList
                        if itemCount is greater than or equal to maxItems then
                            exit repeat
                        end if
                        try
                            set elRole to my sanitizeText(role of el)
                            if elRole is "" then
                                set elRole to "AXUnknown"
                            end if
                            set elSubrole to ""
                            try
                                set elSubrole to my sanitizeText(subrole of el)
                            end try
                            set elName to ""
                            try
                                set elName to my sanitizeText(name of el)
                            end try
                            set elDescription to ""
                            try
                                set elDescription to my sanitizeText(description of el)
                            end try
                            set elValue to ""
                            try
                                set elValue to my sanitizeText(value of el)
                            end try
                            set primaryText to elName
                            if primaryText is "" then set primaryText to elDescription
                            if primaryText is "" then set primaryText to elValue
                            if primaryText is "" then
                                set primaryText to ""
                            end if
                            if primaryText is not "" then
                                set posX to ""
                                set posY to ""
                                try
                                    set pos to position of el
                                    set posX to item 1 of pos as string
                                    set posY to item 2 of pos as string
                                end try
                                set sizeW to ""
                                set sizeH to ""
                                try
                                    set siz to size of el
                                    set sizeW to item 1 of siz as string
                                    set sizeH to item 2 of siz as string
                                end try
                                set outputText to outputText & elRole & "¦" & elSubrole & "¦" & primaryText & "¦" & elName & "¦" & elDescription & "¦" & elValue & "¦" & posX & "¦" & posY & "¦" & sizeW & "¦" & sizeH & linefeed
                                set itemCount to itemCount + 1
                            end if
                        end try
                    end repeat

                    return outputText
                end tell
            end tell
            '''
        )
        if not output:
            return []

        elements: List[Dict[str, Any]] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("¦")
            if len(parts) < 10:
                continue
            role, subrole, primary_text, name, description, value, x, y, width, height = (
                parts[:10]
            )
            try:
                element = {
                    "role": role,
                    "subrole": subrole,
                    "text": primary_text,
                    "name": name,
                    "description": description,
                    "value": value,
                    "x": int(float(x or 0)),
                    "y": int(float(y or 0)),
                    "width": max(int(float(width or 0)), 1),
                    "height": max(int(float(height or 0)), 1),
                }
            except ValueError:
                continue
            elements.append(element)
        return elements

    def invoke_named_element(
        self,
        targets: List[str] | str,
        app_name: Optional[str] = None,
        *,
        region: Optional[Dict[str, int]] = None,
        window_title: Optional[str] = None,
        allowed_roles: Optional[List[str]] = None,
        min_similarity: float = 0.72,
        blocked_terms: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
    ) -> bool:
        if isinstance(targets, str):
            targets = [targets]
        targets = [target for target in targets if self._normalized(target)]
        if not targets or not self._ax_runtime_available or not self._ax_is_trusted():
            return False

        proc_name = self._get_target_process_name(app_name)
        pid = self._find_process_pid(proc_name)
        if not pid:
            return False

        app_ref = None
        window_ref = None
        match = None
        try:
            app_ref = self._ax.AXUIElementCreateApplication(pid)
            if not app_ref:
                return False
            window_ref = self._select_ax_window(app_ref, window_title)
            if not window_ref:
                return False
            match = self._find_best_ax_element_ref(
                window_ref,
                list(targets),
                region=region,
                allowed_roles=allowed_roles,
                min_similarity=min_similarity,
                blocked_terms=blocked_terms,
            )
            if not match:
                return False

            available_actions = self._ax_copy_action_names(match["ref"])
            candidate_actions = actions or ["AXPress", "AXOpen", "AXConfirm", "AXShowDefaultUI"]
            for action_name in candidate_actions:
                if available_actions and action_name not in available_actions:
                    continue
                if self._ax_perform_action(match["ref"], action_name):
                    self.logger.info(
                        "Invoked AX action %s for '%s' at (%s, %s) role=%s",
                        action_name,
                        match.get("text"),
                        match.get("x"),
                        match.get("y"),
                        match.get("role"),
                    )
                    return True

            self.logger.info(
                "AX element matched for %s but no supported action succeeded; available_actions=%s",
                targets[0],
                available_actions,
            )
            return False
        except Exception as exc:
            self.logger.debug("Failed to invoke named AX element %s: %s", targets, exc)
            return False
        finally:
            self._release_ax_match(match)
            self._cf_release(window_ref)
            self._cf_release(app_ref)

    def click_at(self, x: int, y: int) -> bool:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if subprocess:
            script = f'tell application "System Events" to click at {{{x}, {y}}}'
            if subprocess.run(["osascript", "-e", script]).returncode == 0:
                return True
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if pyautogui:
            pyautogui.click(x=x, y=y)
            return True
        return False

    def type_text(self, text: str) -> bool:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if subprocess:
            safe_text = text.replace('"', '\\"')
            script = f'tell application "System Events" to keystroke "{safe_text}"'
            if subprocess.run(["osascript", "-e", script]).returncode == 0:
                return True
        return False

    def press_key(self, key: str) -> bool:
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if pyautogui:
            pyautogui.press(key)
            return True
        return False

    def scroll_down(self) -> bool:
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if pyautogui:
            pyautogui.scroll(-10)
            return True
        return False

    def find_element_by_name(
        self,
        name: str,
        app_name: Optional[str] = None,
        *,
        region: Optional[Dict[str, int]] = None,
        window_title: Optional[str] = None,
        allowed_roles: Optional[List[str]] = None,
    ) -> Optional[ElementLocation]:
        """Deep search for an element by name using AppleScript recursive search"""
        elements = self.snapshot_visible_elements(
            app_name=app_name,
            window_title=window_title,
        )
        if elements:
            best_match = None
            best_score = 0.0
            allowed = {role.lower() for role in allowed_roles or []}
            for element in elements:
                center_x = int(element["x"] + max(element["width"], 1) / 2)
                center_y = int(element["y"] + max(element["height"], 1) / 2)
                if not self._point_in_region(center_x, center_y, region):
                    continue
                if allowed:
                    role = self._normalized(element.get("role"))
                    subrole = self._normalized(element.get("subrole"))
                    if role not in allowed and subrole not in allowed:
                        continue

                candidate_text = (
                    element.get("text")
                    or element.get("name")
                    or element.get("description")
                    or element.get("value")
                    or ""
                )
                if not candidate_text:
                    continue

                normalized_candidate = self._normalized(candidate_text)
                normalized_target = self._normalized(name)
                if not normalized_target:
                    continue

                if normalized_candidate == normalized_target:
                    score = 1.0
                elif normalized_target in normalized_candidate:
                    score = 0.96
                else:
                    score = self._text_similarity(candidate_text, name)

                if score < 0.72 or score <= best_score:
                    continue

                best_score = score
                best_match = (element, candidate_text)

            if best_match:
                element, candidate_text = best_match
                loc = ElementLocation(
                    x=int(element["x"]),
                    y=int(element["y"]),
                    width=max(int(element["width"]), 1),
                    height=max(int(element["height"]), 1),
                    confidence=min(0.98, best_score),
                    strategy_used="accessibility_snapshot",
                    element_name=candidate_text,
                    metadata={
                        "role": element.get("role"),
                        "subrole": element.get("subrole"),
                        "window_title": window_title,
                    },
                )
                self.logger.info(
                    "Found '%s' via accessibility snapshot at (%s, %s) role=%s",
                    name,
                    loc.x,
                    loc.y,
                    element.get("role"),
                )
                return loc

        self.logger.warning(f"Element '{name}' not found in accessibility snapshot")
        return None

    def find_element_by_type_and_index(self, role: str, index: int, app_name: Optional[str] = None) -> Optional[ElementLocation]:
        """Find an element by its accessibility role and index"""
        proc_name = self._get_target_process_name(app_name)
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess: return None
        
        script = f'''
        tell application "System Events"
            tell process "{proc_name}"
                try
                    set target to element {index} of (every UI element whose role is "{role}")
                    set pos to position of target
                    set siz to size of target
                    return (item 1 of pos as string) & "," & (item 2 of pos as string) & "," & (item 1 of siz as string) & "," & (item 2 of siz as string)
                on error
                    return "NOT_FOUND"
                end try
            end tell
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0 and "NOT_FOUND" not in result.stdout:
             parts = result.stdout.strip().split(',')
             if len(parts) == 4:
                return ElementLocation(
                    x=int(float(parts[0])), y=int(float(parts[1])), 
                    width=int(float(parts[2])), height=int(float(parts[3])),
                    confidence=0.8, strategy_used="accessibility_role"
                )
        return None

    def extract_text_elements(self, app_name: Optional[str] = None) -> List[str]:
        """Extract all static text elements from the target application's front window"""
        elements = self.snapshot_visible_elements(app_name=app_name)
        texts: List[str] = []
        seen = set()
        for element in elements:
            text = (
                element.get("text")
                or element.get("name")
                or element.get("description")
                or element.get("value")
                or ""
            ).strip()
            key = self._normalized(text)
            if text and key and key not in seen:
                seen.add(key)
                texts.append(text)
        self.logger.info("Successfully extracted %d text candidates", len(texts))
        return texts

    def close_tab(self) -> bool:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if subprocess:
            # Common shortcut for closing tab/window on macOS
            script = 'tell application "System Events" to keystroke "w" using command down'
            if subprocess.run(["osascript", "-e", script]).returncode == 0:
                return True
        return False

    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot using macOS screencapture utility"""
        from mcp_core.dependency_types import OCR_PROCESSOR
        ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
        if ocr_processor:
            # Re-use existing OCR processor's screenshot capability
            r = (region["X"], region["Y"], region["Width"], region["Height"]) if region else None
            return ocr_processor.capture_screenshot(r)
        return None

    def clear_input(self) -> bool:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if subprocess:
            # Select all and delete
            script = 'tell application "System Events" to keystroke "a" using command down'
            subprocess.run(["osascript", "-e", script])
            script = 'tell application "System Events" to key code 51' # Delete key
            if subprocess.run(["osascript", "-e", script]).returncode == 0:
                return True
        return False

    def find_element_by_accessibility_id(self, element_id: str, app_name: Optional[str] = None) -> Optional[ElementLocation]:
        """MacOS often uses description or identifier as accessibility id"""
        return self.find_element_by_name(element_id, app_name)

    def find_elements_by_type(self, element_type: str, app_name: Optional[str] = None) -> List[ElementLocation]:
        """Find elements by their accessibility role (e.g., 'AXButton')"""
        locations = []
        target_role = self._normalized(element_type)
        for element in self.snapshot_visible_elements(app_name=app_name):
            role = self._normalized(element.get("role"))
            subrole = self._normalized(element.get("subrole"))
            if role != target_role and subrole != target_role:
                continue
            locations.append(
                ElementLocation(
                    x=int(element["x"]),
                    y=int(element["y"]),
                    width=max(int(element["width"]), 1),
                    height=max(int(element["height"]), 1),
                    confidence=0.74,
                    strategy_used="accessibility_type",
                    element_name=element.get("text"),
                    metadata={
                        "role": element.get("role"),
                        "subrole": element.get("subrole"),
                    },
                )
            )
        return locations

    def get_active_window_info(self) -> Optional[Dict[str, Any]]:
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess: return None
        script = '''
        tell application "System Events"
            set proc to first application process whose frontmost is true
            set win to window 1 of proc
            set pos to position of win
            set siz to size of win
            return (name of proc) & "|" & (name of win) & "|" & (item 1 of pos) & "," & (item 2 of pos) & "," & (item 1 of siz) & "," & (item 2 of siz)
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0:
            parts = result.stdout.strip().split('|')
            if len(parts) == 3:
                coords = parts[2].split(',')
                return {"application": parts[0], "title": parts[1], "X": float(coords[0]), "Y": float(coords[1]), "Width": float(coords[2]), "Height": float(coords[3])}
        return None
