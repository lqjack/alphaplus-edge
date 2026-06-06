# Cross-Platform WeChat Automation MCP Server

An advanced Model Context Protocol (MCP) server for intelligent, cross-platform WeChat Official Account automation.

## Current Status

### 🔧 In Development
**Active Issue**: Search flow not completing - investigating root cause

**Current Focus**:
- Fixing coordinate bug where all clicks use fixed position (779.0, 210.0)
- Adding detailed logging to trace execution flow
- Verifying production uses real OCR vs mock data
- Confirming server deployment with bug fixes

**Progress**:
- ✅ OCR coordinate conversion bug fixed (wechat_automation.py lines 1699-1701)
- ✅ Key code locations identified
- 🔲 Adding execution tracing logs
- 🔲 Verifying mock vs real implementation
- 🔲 Root cause analysis in progress

## Key Features
- **Cross-Platform Bridge**: Unified architecture supporting both macOS (Native Accessibility/AppleScript) and Windows (UI Automation).
- **Intelligent Execution**: ML-driven `IntelligentExecutionMonitor` that validates UI states, detects errors, and handles automatic recovery.
- **Adaptive Locators**: Dynamic element location combining Accessibility APIs with OCR pattern matching for maximum reliability.
- **Goal-Driven Autonomy**: Integrated `LLMTaskPlanner` for decomposing high-level automation goals into executable steps.
- **State Persistence**: Deep checkpointing and session management for long-running automation tasks.

## Visual Protocols
- `computer_use_grounding`: Primary visual contract for single-target UI grounding. Use this for search box, account row, and other one-element location tasks.
- `legacy_visual_fallback`: Explicit compatibility path for older multimodal screenshot tasks such as candidate ranking and multi-item extraction.
- `analyze_screenshot`: Backward-compatible alias only. New code should not depend on it directly.

## Architecture
The system follows a bridge pattern where the `WindowManager` delegates high-level operations to the `CrossPlatformAutomationEngine`, which coordinates specialized adapters:
- `MacOSAccessibilityAdapter`: Native macOS interaction leveraging AppleScript and Quartz.
- `WindowsUIAutomationAdapter`: Native Windows interaction via UI Automation API.
- `OCRProcessor`: Tesseract-based visual verification of screen state.

### Key Components
| Component | Purpose |
|-----------|---------|
| `WeChatAutomation` | Main orchestrator for automation tasks |
| `search_account_v2` | Main entry point for search (line ~923) |
| `search_wechat_account` | Traditional search implementation (line ~691) |
| `_navigate_to_article_list` | Article list navigation (line ~946) |
| `run_cycle` | Main automation cycle (line ~1199) |
| `LLMElementLocator` | Single-target grounding via `computer_use_grounding` |
| `UnifiedElementLocator` | Candidate ranking / fallback chain using `legacy_visual_fallback` when needed |

## Prerequisites
- **macOS/Windows**: Fully supported with native adapters.
- **WeChat**: Installed and logged in on the host system.
- **Permissions**:
  - macOS: "Accessibility" and "Screen Recording" permissions required for the terminal/IDE.
  - Windows: UI Automation permissions enabled.

## MCP Tools
1. `wechat_run_once`: Executes a single, monitor-validated pass of checking specified or default accounts.
2. `wechat_start_automation`: Starts a recurring loop with intelligent health checks and performance monitoring.

## Configuration
The server uses a `.env` file for configuration. Key parameters include:
- `AI_MODEL`: LLM to use for task planning and decision making.
- `OCR_ENABLED`: Enable/disable visual verification (default: true).
- `PLATFORM_ADAPTER`: Automatically detected (macos/windows).

## Documentation
- [PLAN.md](PLAN.md) - Implementation plan and architecture
- [TEST_PLAN.md](TEST_PLAN.md) - Testing strategy and test cases
- [NOT_IN_SCOPE.md](NOT_IN_SCOPE.md) - Out of scope items
- [WHAT_ALREADY_EXISTS.md](WHAT_ALREADY_EXISTS.md) - Existing infrastructure leveraged

## Known Issues
1. **Fixed Coordinates**: All clicks currently use position (779.0, 210.0) - investigating
2. **Search Flow**: Search flow may not complete fully - root cause analysis in progress
3. **Mock Data**: Need to verify production doesn't use mock OCR implementation

## Related Files
- `wechat_automation.py` - Main automation implementation
- `test_wechat_automation_improved.py` - Test file (contains MockOCRProcessor)
- `mcp_core/ocr_processor.py` - Core OCR implementation
- `mcp_core/cross_platform_automation.py` - Platform abstraction
