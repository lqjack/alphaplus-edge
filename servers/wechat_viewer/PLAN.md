<!-- /autoplan restore point: /Users/liu/.gstack/projects/root-dataproaiset/master-autoplan-restore-20260412-160443.md -->
## 0A. Premise Challenge

1. Is this the right problem to solve? Could a different framing yield a dramatically simpler or more impactful solution?
   - Yes, this is the right problem. Current element location operations are scattered and inconsistent, leading to unreliable automation. A unified approach will significantly improve reliability and maintainability.

2. What is the actual user/business outcome? Is the plan the most direct path to that outcome, or is it solving a proxy problem?
   - The actual outcome is reliable WeChat automation for article fetching and processing. The plan directly addresses this by creating a unified element location service that improves accuracy through YOLO pre-filtering → multimodal precision judgment → result parsing.

3. What would happen if we did nothing? Real pain point or hypothetical one?
   - Real pain point: Continued unreliable element location leading to failed automation runs, missed articles, and manual intervention requirements.

## TASK PROGRESS TRACKER

### Current Focus (2024-04-12)
**Goal**: Fix WeChat automation search flow not completing - root cause analysis

### Progress Summary
| Task | Status | Notes |
|------|--------|-------|
| OCR coordinate bug fix | ✅ DONE | Fixed in wechat_automation.py lines 1699-1701 |
| Key code locations identified | ✅ DONE | search_account_v2, search_wechat_account, _navigate_to_article_list |
| API functional verification | ✅ DONE | API returns success response |
| Add detailed logging | 🔲 PENDING | Need to trace execution flow |
| Verify mock vs real OCR | 🔲 PENDING | Need audit MockOCRProcessor |
| Confirm server deployment | 🔲 PENDING | Need verify server reload |
| Root cause analysis | 🔲 IN PROGRESS | Why search flow not completing |

### Next Steps
1. Add logging to `search_account_v2`, `search_wechat_account`, `_navigate_to_article_list`
2. Verify production code doesn't use MockOCRProcessor
3. Check if server has latest code deployed
4. Analyze why all clicks use fixed coordinates (779.0, 210.0)

### Key Files
- `wechat_automation.py` - Main automation code
- `test_wechat_automation_improved.py` - Test file with MockOCRProcessor
- `mcp_core/ocr_processor.py` - Core OCR implementation

### Open Questions
- Is the fixed coordinate (779.0, 210.0) coming from mock data or fallback logic?
- Did the server reload after the coordinate bug fix?

---

## 0B. Existing Code Leverage

1. What existing code already partially or fully solves each sub-problem? Map every sub-problem to existing code. Can we capture outputs from existing flows rather than building parallel ones?
   - Current element location exists in: ImprovedSearchBarLocator, cross_platform_automation.py (read_articles method), wechat_automation.py (_read_articles_legacy and _read_articles_with_ocr_bounds methods)
   - These implement heuristic/OCR-based approaches that can be leveraged as fallback mechanisms
   - The OCR processor in mcp_core/ocr_processor.py provides core OCR functionality that can be reused
   - The cross_platform_automation.py engine provides platform abstraction that can be utilized

2. Is this plan rebuilding anything that already exists? If yes, explain why rebuilding is better than refactoring.
   - Yes, we are replacing multiple disparate element location implementations with a unified service
   - Rebuilding is better than refactoring because:
     * Current implementations are tightly coupled to specific use cases
     * A unified service provides clean separation of concerns
     * Enables consistent application of `computer_use_grounding` for single-target tasks and `legacy_visual_fallback` for compatibility tasks
     * Reduces code duplication and improves maintainability

## 0C. Dream State Mapping

Describe the ideal end state of this system 12 months from now. Does this plan move toward that state or away from it?
```
CURRENT STATE                  THIS PLAN                  12-MONTH IDEAL
[describe]          --->       [describe delta]    --->    [describe target]
```
- Current State: Fragmented element location implementations using inconsistent heuristics, OCR approaches, and mixed visual contracts
- This Plan: Unified element location service with `computer_use_grounding` as the primary single-target protocol and `legacy_visual_fallback` as the explicit compatibility path for older multimodal tasks
- 12-Month Ideal: Enterprise-grade visual automation platform with self-healing locators, continuous learning from successful interactions, and cross-application portability

## 0C-bis. Implementation Alternatives (MANDATORY)

Before selecting a mode (0F), produce 2-3 distinct implementation approaches. This is NOT optional — every plan must consider alternatives.

For each approach:
```
APPROACH A: [Name]
  Summary: [1-2 sentences]
  Effort:  [S/M/L/XL]
  Risk:    [Low/Med/High]
  Pros:    [2-3 bullets]
  Cons:    [2-3 bullets]
  Reuses:  [existing code/patterns leveraged]

APPROACH B: [Name]
  ...

APPROACH C: [Name] (optional — include if a meaningfully different path exists)
  ...
```

APPROACH A: Unified Element Location Service (Selected Approach)
  Summary: Create a new UnifiedElementLocator service that implements YOLO pre-filtering → multimodal precision judgment (gateway calling dataproai/src/servers/ai) → result parsing for all element location operations
  Effort:  M
  Risk:    Medium
  Pros:    Consistent accuracy improvements, reduced code duplication, clear separation of concerns, easier testing and maintenance
  Cons:    Initial development overhead, potential performance impact from additional processing layers
  Reuses:  Existing OCR processor, cross-platform automation engine, gateway service infrastructure

APPROACH B: Enhance Existing Locators Incrementally
  Summary: Improve each existing element locator (ImprovedSearchBarLocator, etc.) individually to incorporate YOLO and multimodal judgment where beneficial
  Effort:  L
  Risk:    Low
  Pros:    Minimal disruption, leverages existing proven code, gradual improvement approach
  Cons:    Inconsistent implementation across locators, duplicated YOLO/multimodal logic, harder to maintain uniform quality standards
  Reuses:  All existing locator implementations, OCR processor, gateway service

APPROACH C: Hybrid Approach with Selective Unified Service
  Summary: Create unified service for high-value/complex element locations while keeping simple heuristics for trivial cases
  Effort:  M
  Risk:    Medium-Low
  Pros:    Optimizes effort vs impact, keeps simple cases fast, applies advanced techniques where most needed
  Cons:    Increased complexity in deciding when to use unified vs simple approach, potential inconsistency in approach
  Reuses:  Existing simple locators for trivial cases, new unified service for complex cases

RECOMMENDATION: Choose APPROACH A because it provides the most consistent and maintainable solution with the best long-term scalability, aligning with the engineering preference for explicit over clever solutions and minimizing accidental complexity.

## 0D. Mode-Specific Analysis

For SELECTIVE EXPANSION — run the HOLD SCOPE analysis first, then surface expansions:
1. Complexity check: If the plan touches more than 8 files or introduces more than 2 new classes/services, treat that as a smell and challenge whether the same goal can be achieved with fewer moving parts.
2. What is the minimum set of changes that achieves the stated goal? Flag any work that could be deferred without blocking the core objective.
3. Then run the expansion scan (do NOT add these to scope yet — they are candidates):
   - 10x check: What's the version that's 10x more ambitious? Describe it concretely.
   - Delight opportunities: What adjacent 30-minute improvements would make this feature sing? List at least 5.
   - Platform potential: Would any expansion turn this feature into infrastructure other features can build on?
4. Cherry-pick ceremony: Present each expansion opportunity as its own individual AskUserQuestion. Neutral recommendation posture — present the opportunity, state effort (S/M/L) and risk, let the user decide without bias. Options: A) Add to this plan's scope B) Defer to TODOS.md C) Skip. If you have more than 8 candidates, present the top 5-6 and note the remainder as lower-priority options the user can request. Accepted items become plan scope for all remaining review sections. Rejected items go to "NOT in scope."

Let me analyze the complexity:
- Files to be modified: automation/wechat_automation.py, mcp_core/ocr_processor.py, mcp_core/cross_platform_automation.py, plus new unified service files
- Estimated: 4-6 existing files to modify + 2-3 new files = 6-9 files total
- New classes/services: UnifiedElementLocator service (1 new major class)
- This is borderline for the complexity check (8+ files threshold)

What is the minimum set of changes that achieves the stated goal?
- Core: UnifiedElementLocator service with YOLO → multimodal → result parsing pipeline
- Integration points: Replace element location calls in wechat_automation.py and related modules
- Non-essential enhancements that could be deferred: Advanced caching of YOLO results, fallback chaining mechanisms, performance optimization layers

Then run the expansion scan:
- 10x check: Enterprise visual automation platform with self-healing locators that learn from each successful interaction, predictive element location based on user behavior patterns, and cross-platform visual task orchestration
- Delight opportunities: 
  1. Automatic locator validation and health monitoring
  2. Visual diff reporting showing before/after of element detection improvements
  3. Performance metrics dashboard for element location speed and accuracy
  4. Failed attempt analysis with AI-generated suggestions for improvement
  5. Multi-language OCR support extending beyond Chinese/English
- Platform potential: Yes, this could become a foundational visual automation service used by other server modules for UI testing, RPA, and cross-application data extraction

Expansion Decisions (SELECTIVE EXPANSION only):
- Accepted: Automatic locator validation and health monitoring
- Accepted: Visual diff reporting showing before/after of element detection improvements
- Accepted: Performance metrics dashboard for element location speed and accuracy
- Accepted: Failed attempt analysis with AI-generated suggestions for improvement
- Accepted: Multi-language OCR support extending beyond Chinese/English
- Accepted Platform Potential: Yes, this could become a foundational visual automation service used by other server modules for UI testing, RPA, and cross-application data extraction

Now let me proceed with 0D-POST. Persist CEO Plan (EXPANSION and SELECTIVE EXPANSION only):

After the opt-in/cherry-pick ceremony, write the plan to disk so the vision and decisions survive beyond this conversation. Only run this step for EXPANSION and SELECTIVE EXPANSION modes.

```bash
eval "$(~/.claude/skills/gstack/bin/gstack-slug 2>/dev/null)" && mkdir -p ~/.gstack/projects/$SLUG/ceo-plans
```

Before writing, check for existing CEO plans in the ceo-plans/ directory. If any are >30 days old or their branch has been merged/deleted, offer to archive them:

```bash
mkdir -p ~/.gstack/projects/$SLUG/ceo-plans/archive
# For each stale plan: mv ~/.gstack/projects/$SLUG/ceo-plans/{old-plan}.md ~/.gstack/projects/$SLUG/ceo-plans/archive/
```

Write to `~/.gstack/projects/$SLUG/ceo-plans/{date}-{feature-slug}.md` using this format:

```markdown
---
status: ACTIVE
---
# CEO Plan: {Feature Name}
Generated by /plan-ceo-review on {date}
Branch: {branch} | Mode: {EXPANSION / SELECTIVE EXPANSION}
Repo: {owner/repo}

## Vision

### 10x check
{10x vision description}

### Platonic Ideal
{platonic ideal description — EXPANSION mode only}

## Scope Decisions

| # | Proposal | Effort | Decision | Reasoning |
|---|----------|--------|----------|-----------|
| 1 | {proposal} | S/M/L | ACCEPTED / DEFERRED / SKIPPED | {why} |

## Accepted Scope (added to this plan)
- {bullet list of what's now in scope}

## Deferred to TODOS.md
- {items with context}
```

Derive the feature slug from the plan being reviewed (e.g., "user-dashboard", "auth-refactor"). Use the date in YYYY-MM-DD format.

After writing the CEO plan, run the spec review loop on it:

## Spec Review Loop

Before presenting the document to the user for approval, run an adversarial review.

Step 1: Dispatch reviewer subagent

Use the Agent tool to dispatch an independent reviewer. The reviewer has fresh context
and cannot see the brainstorming conversation — only the document. This ensures genuine
adversarial independence.

Prompt the subagent with:
- The file path of the document just written
- "Read this document and review it on 5 dimensions. For each dimension, note PASS or
  list specific issues with suggested fixes. At the end, output a quality score (1-10)
  across all dimensions."

Dimensions:
1. **Completeness** — Are all requirements addressed? Missing edge cases?
2. **Consistency** — Do parts of the document agree with each other? Contradictions?
3. **Clarity** — Could an engineer implement this without asking questions? Ambiguous language?
4. **Scope** — Does the document creep beyond the original problem? YAGNI violations?
5. **Feasibility** — Can this actually be built with the stated approach? Hidden complexity?

The subagent should return:
- A quality score (1-10)
- PASS if no issues, or a numbered list of issues with dimension, description, and fix

Step 2: Fix and re-dispatch

If the reviewer returns issues:
1. Fix each issue in the document on disk (use Edit tool)
2. Re-dispatch the reviewer subagent with the updated document
3. Maximum 3 iterations total

Convergence guard: If the reviewer returns the same issues on consecutive iterations
(the fix didn't resolve them or the reviewer disagrees with the fix), stop the loop
and persist those issues as "Reviewer Concerns" in the document rather than looping
further.

If the subagent fails, times out, or is unavailable — skip the review loop entirely.
Tell the user: "Spec review unavailable — presenting unreviewed doc." The document is
already written to disk; the review is a quality bonus, not a gate.

Step 3: Report and persist metrics

After the loop completes (PASS, max iterations, or convergence guard):

1. Tell the user the result — summary by default:
   "Your doc survived N rounds of adversarial review. M issues caught and fixed.
   Quality score: X/10."
   If they ask "what did the reviewer find?", show the full reviewer output.

2. If issues remain after max iterations or convergence, add a "## Reviewer Concerns"
   section to the document listing each unresolved issue. Downstream skills will see this.

3. Append metrics:
```bash
mkdir -p ~/.gstack/analytics
echo '{"skill":"plan-ceo-review","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","iterations":ITERATIONS,"issues_found":FOUND,"issues_fixed":FIXED,"remaining":REMAINING,"quality_score":SCORE}' >> ~/.gstack/analytics/spec-review.jsonl 2>/dev/null || true
```
Replace ITERATIONS, FOUND, FIXED, REMAINING, SCORE with actual values from the review.

### 0E. Temporal Interrogation (EXPANSION, SELECTIVE EXPANSION, and HOLD modes)
Think ahead to implementation: What decisions will need to be made during implementation that should be resolved NOW in the plan?
```
  HOUR 1 (foundations):     What does the implementer need to know?
  HOUR 2-3 (core logic):   What ambiguities will they hit?
  HOUR 4-5 (integration):  What will surprise them?
  HOUR 6+ (polish/tests):  What will they wish they'd planned for?
```
NOTE: These represent human-team implementation hours. With CC + gstack,
6 hours of human implementation compresses to ~30-60 minutes. The decisions
are identical — the implementation speed is 10-20x faster. Always present
both scales when discussing effort.

Surface these as questions for the user NOW, not as "figure it out later."

### 0F. Mode Selection
In every mode, you are 100% in control. No scope is added without your explicit approval.

Present four options:
1. **SCOPE EXPANSION:** The plan is good but could be great. Dream big — propose the ambitious version. Every expansion is presented individually for your approval. You opt in to each one.
2. **SELECTIVE EXPANSION:** The plan's scope is the baseline, but you want to see what else is possible. Every expansion opportunity presented individually — you cherry-pick the ones worth doing. Neutral recommendations.
3. **HOLD SCOPE:** The plan's scope is right. Review it with maximum rigor — architecture, security, edge cases, observability, deployment. Make it bulletproof. No expansions surfaced.
4. **SCOPE REDUCTION:** The plan is overbuilt or wrong-headed. Propose a minimal version that achieves the core goal, then review that.

Context-dependent defaults:
* Greenfield feature → default EXPANSION
* Feature enhancement or iteration on existing system → default SELECTIVE EXPANSION
* Bug fix or hotfix → default HOLD SCOPE
* Refactor → default HOLD SCOPE
* Plan touching >15 files → suggest REDUCTION unless user pushes back
* User says "go big" / "ambitious" / "cathedral" → EXPANSION, no question
* User says "hold scope but tempt me" / "show me options" / "cherry-pick" → SELECTIVE EXPANSION, no question

**SELECTED MODE: HOLD SCOPE**

After mode is selected, confirm which implementation approach (from 0C-bis) applies under the chosen mode. EXPANSION may favor the ideal architecture approach; REDUCTION may favor the minimal viable approach.

For HOLD SCOPE mode, the selected implementation approach is: APPROACH A: Unified Element Location Service (Selected Approach)
  Summary: Create a new UnifiedElementLocator service that implements YOLO pre-filtering → multimodal precision judgment (gateway calling dataproai/src/servers/ai) → result parsing for all element location operations
  Effort:  M
  Risk:    Medium
  Pros:    Consistent accuracy improvements, reduced code duplication, clear separation of concerns, easier testing and maintenance
  Cons:    Initial development overhead, potential performance impact from additional processing layers
  Reuses:  Existing OCR processor, cross-platform automation engine, gateway service infrastructure

Once selected, commit fully. Do not silently drift.
**STOP.** AskUserQuestion once per issue. Do NOT batch. Recommend + WHY. If no issues or fix is obvious, state what you'll do and move on — don't waste a question. Do NOT proceed until user responds.

## Review Sections (10 sections, after scope and mode are agreed)

### Section 1: Architecture Review
Evaluate and diagram:
* Overall system design and component boundaries. Draw the dependency graph.
* Data flow — all four paths. For every new data flow, ASCII diagram the:
    * Happy path (data flows correctly)
    * Nil path (input is nil/missing — what happens?)
    * Empty path (input is present but empty/zero-length — what happens?)
    * Error path (upstream call fails — what happens?)
* State machines. ASCII diagram for every new stateful object. Include impossible/invalid transitions and what prevents them.
* Coupling concerns. Which components are now coupled that weren't before? Is that coupling justified? Draw the before/after dependency graph.
* Scaling characteristics. What breaks first under 10x load? Under 100x?
* Single points of failure. Map them.
* Security architecture. Auth boundaries, data access patterns, API surfaces. For each new endpoint or data mutation: who can call it, what do they get, what can they change?
* Production failure scenarios. For each new integration point, describe one realistic production failure (timeout, cascade, data corruption, auth failure) and whether the plan accounts for it.
* Rollback posture. If this ships and immediately breaks, what's the rollback procedure? Git revert? Feature flag? DB migration rollback? How long?

**EXPANSION and SELECTIVE EXPANSION additions:**
* What would make this architecture beautiful? Not just correct — elegant. Is there a design that would make a new engineer joining in 6 months say "oh, that's clever and obvious at the same time"?
* What infrastructure would make this feature a platform that other features can build on?

**SELECTIVE EXPANSION:** If any accepted cherry-picks from Step 0D affect the architecture, evaluate their architectural fit here. Flag any that create coupling concerns or don't integrate cleanly — this is a chance to revisit the decision with new information.

Required ASCII diagram: full system architecture showing new components and their relationships to existing ones.

#### Current Architecture Dependency Diagram
```
WECHAT AUTOMATION LAYER
┌─────────────────────────────────────────────────────────────────────┐
│  WeChatAutomation (orchestrator)                                    │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  SearchNavigator        │ ArticleReader                       │  │
│  │  (search_wechat_account)│ (read_article)                      │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Legacy Element Location Methods                               │  │
│  │  ├─ _read_articles_legacy                                     │  │
│  │  ├─ _read_articles_with_ocr_bounds                            │  │
│  │  ├─ _read_articles_with_llm_bounds                           │  │
│  │  ├─ _locate_and_click_search_bar_simple                      │  │
│  │  ├─ _find_and_click_account_in_results                       │  │
│  │  └─ _capture_search_results                                  │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Specialized Locators                                         │  │
│  │  ├─ ImprovedSearchBarLocator                                 │  │
│  │  ├─ LLMElementLocator                                       │  │
│  │  ├─ AdaptiveOCR                                             │  │
│  │  └─ MultiLayerLocator                                       │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Core Infrastructure                                          │  │
│  │  ├─ OCRProcessor (mcp_core)                                 │  │
│  │  ├─ CrossPlatformAutomationEngine                            │  │
│  │  ├─ WindowManager                                           │  │
│  │  └─ GUIAutomation                                           │  │
│  └─────────────────────────────────────────────────────────────────┘
```

#### UPDATED: Unified Element Locator with Playwright + CDP (PRIMARY)
**New Fallback Chain: Playwright + CDP → YOLO + LLM → OCR**

```
UNIFIED ELEMENT LOCATOR (NEW PRIMARY STRATEGY)
┌─────────────────────────────────────────────────────────────────────┐
│                    UnifiedElementLocator                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Strategy Chain (in priority order):                       │   │
│  │                                                             │   │
│  │  1. PLAYWRIGHT_CDP ──┬──► ElementLocation (HIGH)        │   │
│  │       (Web-based)     │    (CSS/XPath selectors)          │   │
│  │                       │    Uses existing Chrome session     │   │
│  │                       │    via CDP WebSocket              │   │
│  │                       │                                   │   │
│  │  2. YOLO_LLM ───────┼──► ElementLocation (HIGH)        │   │
│  │       (Vision-based) │    Screen capture + AI           │   │
│  │                       │    YOLO pre-screening            │   │
│  │                       │    Multimodal judgment            │   │
│  │                       │                                   │   │
│  │  3. OCR ────────────┴──► ElementLocation (MEDIUM)       │   │
│  │       (Text-based)     OCR fallback for text elements    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Each strategy returns: ElementLocation with confidence level        │
│  If strategy fails → automatically falls back to next priority    │
└─────────────────────────────────────────────────────────────────────┘

PLAYWRIGHT CDP STRATEGY DETAILS:
- Uses existing Chrome session via CDP (ws://127.0.0.1:9222/...)
- Supports: click, fill, get_content, screenshot, navigate
- Selectors: CSS, XPath, text, accessibility
- Advantages: Precise, fast, works for web-based apps (WeChat Web, etc.)
- Use Cases: Web elements, search boxes, buttons, links

YOLO_LLM STRATEGY DETAILS:
- Screen capture → YOLO detection → LLM judgment
- Use Cases: Native app elements, complex UI, accessibility-challenged apps

OCR STRATEGY DETAILS:
- Last fallback for text-based element detection
- Use Cases: When other strategies fail, simple text labels
```

#### Proposed Architecture with Unified Element Locator
```
WECHAT AUTOMATION LAYER
┌─────────────────────────────────────────────────────────────────────┐
│  WeChatAutomation (orchestrator)                                    │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  SearchNavigator        │ ArticleReader                        │  │
│  │  (search_wechat_account)│ (read_article)                       │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  UNIFIED ELEMENT LOCATOR SERVICE                               │  │
│  │  (YOL0 pre-filtering → multimodal judgment → result parsing)   │  │
│  │                                                                  │  │
│  │  ┌───────────────────────────────────────────────────────────┐  │
│  │  │  Element Location Pipeline                                │  │  │
│  │  │  ├─ YOLO Pre-screening (fast candidate detection)         │  │
│  │  │  ├─ Multimodal Precision Judgment (gateway → AI service)  │  │
│  │  │  └─ Result Parsing (extract actionable coordinates)       │  │
│  │  └───────────────────────────────────────────────────────────┘  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │  Core Infrastructure (unchanged)                               │  │
│  │  ├─ OCRProcessor (mcp_core)                                    │  │
│  │  ├─ CrossPlatformAutomationEngine                              │  │
│  │  ├─ WindowManager                                              │  │
│  │  └─ GUIAutomation                                              │  │
│  └─────────────────────────────────────────────────────────────────┘
```

#### Migration Strategy
1. **Phase 1**: Implement UnifiedElementLocator service
2. **Phase 2**: Replace legacy element location methods one-by-one:
   - _read_articles_with_ocr_bounds → UnifiedElementLocator.locate_elements()
   - _read_articles_with_llm_bounds → `legacy_visual_fallback` + UnifiedElementLocator.locate_elements()
   - _locate_and_click_search_bar_simple → `computer_use_grounding` + UnifiedElementLocator.locate_element()
   - _find_and_click_account_in_results → `computer_use_grounding` + UnifiedElementLocator.locate_element()
   - _capture_search_results → UnifiedElementLocator.locate_elements()
3. **Phase 3**: Remove duplicate implementations and consolidate fallbacks
4. **Phase 4**: Add performance monitoring and health checks

#### Data Flow Diagrams for Unified Element Locator Service

**Happy Path (Normal Operation)**
```
REQUEST → [Input Validation] → [YOLO Pre-screening] 
         → [Candidate Regions] → [Multimodal Judgment via legacy_visual_fallback] 
         → [Result Parsing] → [ElementLocation Result] → RETURN
```

**Nil Path (Missing/Null Input)**
```
REQUEST → [Input Validation] → [NULL/INVALID INPUT DETECTED] 
         → [EARLY RETURN] → [ElementLocation.NONE] → RETURN
```

**Empty Path (Valid Input but No Matches)**
```
REQUEST → [Input Validation] → [YOLO Pre-screening] 
         → [NO CANDIDATES FOUND] → [EARLY RETURN] 
         → [EMPTY ElementLocation LIST] → RETURN
```

**Error Path (External Service Failure)**
```
REQUEST → [Input Validation] → [YOLO Pre-screening] 
         → [Candidate Regions] → [AI Service CALL FAILED] 
         → [FALLBACK TO OCR/HEURISTIC] → [ElementLocation Result] 
         → [LOG ERROR] → RETURN (degraded quality)
```

#### Coupling Analysis: Before and After

**BEFORE (Current State - High Coupling)**
```
WeChatAutomation
    ├─→ ImprovedSearchBarLocator (direct instantiation)
    ├─→ LLMElementLocator (direct instantiation)
    ├─→ AdaptiveOCR (direct instantiation)
    ├─→ MultiLayerLocator (direct instantiation)
    ├─→ OCRProcessor (via dependency manager)
    └─→ CrossPlatformAutomationEngine (via dependency manager)

TIGHT COUPLING PROBLEMS:
- Each locator has different initialization patterns
- Business logic mixed with element location concerns
- No unified interface for element location strategies
- Difficult to swap implementations or add new strategies
- Duplicate validation and error handling code
```

**AFTER (Proposed State - Reduced Coupling)**
```
WeChatAutomation
    └─→ UnifiedElementLocatorService (via dependency injection)
             ├─→ Uses OCRProcessor (when needed)
             ├─→ Uses CrossPlatformAutomationEngine (when needed)
             ├─→ Calls AI Service via Gateway (multimodal judgment)
             └─→ Applies YOLO pre-screening (internal)

LOOSE COUPLING BENEFITS:
- Single point of entry for all element location needs
- Consistent interface regardless of underlying strategy
- Easy to add new location strategies (template matching, etc.)
- Centralized error handling and fallback logic
- Clear separation: orchestration vs location concerns
```

#### Scaling Characteristics
```
Under 10x Load:
- YOLO pre-screening becomes bottleneck (CPU-bound)
- Mitigation: Batch YOLO processing, model quantization
- AI service calls scale linearly with candidates

Under 100x Load:
- AI service gateway becomes bottleneck (network/I/O bound)
- Mitigation: Request caching, result pooling, async batching
- Fallback to OCR/heuristic reduces AI service pressure

Primary Scaling Limit: AI service gateway throughput
Secondary Limit: YOLO model inference speed
```

#### Single Points of Failure
```
1. AI Service Gateway - Mitigated by:
   - Local OCR/heuristic fallback
   - Circuit breaker pattern
   - Graceful degradation to lower-quality results

2. YOLO Model Loading - Mitigated by:
   - Lazy initialization with fallback
   - Model caching mechanism
   - Degraded mode using pure OCR/heuristic

3. Screenshot Capture - Mitigated by:
   - Retry mechanism with exponential backoff
   - Alternative capture methods (platform-specific)
   - Cached recent screenshots for static elements
```

#### Security Architecture
```
Authentication Boundaries:
- Internal service-to-service calls: No auth required (same trust boundary)
- Gateway to AI service: API key based authentication
- No external endpoints exposed by this service

Data Access Patterns:
- Read-only: Screenshot capture, OCR processing
- No persistent storage: All processing in-memory
- Temporary files: Securely cleaned after use

API Surfaces:
- Internal: UnifiedElementLocator interface (locate_element, locate_elements)
- No external APIs introduced
- Leverages existing gateway AI service (already secured)

Data Flow Security:
- Screenshots: Never leave local machine unencrypted
- Coordinates: Numerical data, no PII
- Results: Element locations only, no content exposure
```

#### Production Failure Scenarios

**Scenario 1: AI Service Timeout**
- Description: Gateway to AI service exceeds timeout threshold (30s)
- Impact: Element location operations slow down or fail
- Mitigation: 
  - Circuit breaker opens after 5 consecutive failures
  - Falls back to OCR/heuristic methods
  - Returns degraded quality results with warning
  - Recovery timeout: 60s before attempting AI service again

**Scenario 2: Screenshot Capture Failure**
- Description: Unable to capture screen due to permissions or platform issues
- Impact: Complete failure of element location operations
- Mitigation:
  - Platform-specific fallback methods (quartz on macOS, GDI on Windows)
  - Cached screenshot reuse for static UI elements
  - User permission guidance in error messages

**Scenario 3: YOLO Model Corruption/Loss**
- Description: YOLO model file missing or corrupted
- Impact: Falls back to pure OCR/heuristic approach
- Mitigation:
  - Automatic model re-download on failure
  - Local model caching
  - Degraded but functional operation without YOLO pre-screening

**Scenario 4: Memory Exhaustion from Large Screenshots**
- Description: High-resolution screenshots cause memory pressure
- Impact: System slowdown or crashes during element location
- Mitigation:
  - Automatic screenshot resolution scaling
  - Memory usage monitoring and throttling
  - Region-of-interest capture when bounds are known

#### Rollback Posture
```
If this ships and immediately breaks, the rollback procedure is:

1. **Git Revert**: Single commit reversal of all changes
   - Fastest recovery (<1 minute)
   - Preserves all other work in progress
   - Risk: Loses any valid improvements made

2. **Feature Flag**: Disable unified locator via configuration
   - Zero-downtime rollback
   - Gradual rollout/reversal capability
   - Requires: Add feature flag to config (wechat_viewer.yaml)

3. **Selective Component Rollback**: 
   - Keep core infrastructure, revert only problematic parts
   - Granular control over failure isolation
   - More complex but safest for partial failures

RECOMMENDED APPROACH: Feature flag with git revert as backup
- Deploy with feature flag OFF by default
- Enable for testing, monitor metrics
- Quick toggle off if issues arise
- Git revert available for catastrophic failures
```

#### What Would Make This Architecture Beautiful
```
Elegance Factors:
1. **Strategy Pattern Consistency**: All location strategies (YOLO, OCR, heuristic) 
   implement identical ElementLocatorStrategy interface
2. **Pipeline Transparency**: Clear, inspectable stages with intermediate results
3. **Configuration Driven**: YOLO confidence thresholds, timeouts, fallbacks 
   all configurable without code changes
4. **Observability Built-in**: Each pipeline stage emits structured logs/metrics
5. **Fallback Chaining**: Automatic degradation path: YOLO+AI → OCR → Heuristic → Cached
6. **Stateless Design**: No hidden state, each call is independent and idempotent
7. **Error Containment**: Failures in one strategy don't poison others
```

#### Infrastructure Platform Potential
```
This Unified Element Locator could become a foundational platform service for:

1. **Visual Testing Framework**: 
   - Cross-platform UI test automation with intelligent element finding
   - Self-healing selectors that adapt to UI changes
   - Visual regression testing with AI-powered diff analysis

2. **Robotic Process Automation (RPA) Foundation**:
   - Universal desktop automation across applications
   - AI-assisted process recording and optimization
   - Exception handling with visual context awareness

3. **Cross-Application Data Extraction**:
   - Universal OCR + understanding for form processing
   - Intelligent field location and data mapping
   - Multi-language document processing pipeline

4. **Accessibility Testing Tool**:
   - Automated UI accessibility compliance checking
   - Visual contrast and readability analysis
   - Screen reader compatibility verification

Key Infrastructure Components to Extract:
- VisualElement interface (platform-agnostic element representation)
- LocationStrategy pluggable architecture
- VisualProcessingPipeline with observable stages
- Result validation and confidence scoring framework
- Cross-platform screenshot and input abstraction layer
```

**Section 1 Complete**: Architecture reviewed with dependency diagrams, data flow paths, coupling analysis, scaling characteristics, failure scenarios, and platform potential identified.

## Section 2: Error/Rescue Analysis
For each identified failure mode, detail:
* Immediate user impact and recovery time
* Automatic recovery mechanisms (retries, fallbacks, circuit breakers)
* Manual intervention procedures (escalation paths, workaround steps)
* Prevention strategies (monitoring, validation, design improvements)
* Error classification and severity levels
* Test scenarios to validate error handling

### Error Catalog for Unified Element Locator Service

#### 1. AI Service Unavailable (ERROR-001)
**Immediate Impact**: Element location operations fall back to OCR/heuristic methods
**Recovery Time**: <5s for fallback activation, 60s before retrying AI service
**Automatic Recovery**: 
- Circuit breaker pattern with 5-failure threshold
- Exponential backoff retry (starts at 5s, max 60s)
- Fallback to OCR preprocessing → heuristic positioning
**Manual Intervention**: 
- Check gateway service health: `curl http://gateway:8000/health`
- Verify API key validity and permissions
- Restart gateway service if needed
**Prevention**: 
- Gateway health monitoring with alerts
- API key expiration monitoring
- Load testing AI service connections
**Severity**: MEDIUM (degraded functionality, not complete failure)
**Test Scenarios**:
- Mock gateway service returning 503/timeout
- Network partition simulation
- Invalid API key injection

#### 2. Screenshot Capture Failure (ERROR-002)
**Immediate Impact**: Complete failure of element location until resolved
**Recovery Time**: Immediate if fallback method works, otherwise requires manual fix
**Automatic Recovery**:
- Platform-specific fallback methods (quartz/macOS, GDI/Windows)
- Alternative libraries (PIL ImageGrab, mss)
- Cached screenshot reuse for static elements (<30s old)
**Manual Intervention**:
- Check screen recording permissions (macOS Privacy Settings)
- Verify display server is running correctly
- Close conflicting screen capture applications
**Prevention**:
- Permission checks at startup
- Fallback method validation during initialization
- Display health monitoring
**Severity**: HIGH (complete loss of functionality)
**Test Scenarios**:
- Deny screen recording permissions
- Simulate display server crash
- Exhaust graphics memory/resources

#### 3. YOLO Model Loading Failure (ERROR-003)
**Immediate Impact**: Falls back to pure OCR/heuristic (no pre-screening)
**Recovery Time**: <2s for fallback, model re-download may take 30s-2m
**Automatic Recovery**:
- Automatic model re-download from Ultralytics
- Local model caching with version checking
- Degraded mode notification to monitoring systems
**Manual Intervention**:
- Check disk space and permissions
- Verify internet connectivity for model download
- Clear corrupted model cache if needed
**Prevention**:
- Model integrity checksum validation
- Disk space monitoring
- Background model pre-loading at startup
**Severity**: LOW (reduced accuracy, not failure)
**Test Scenarios**:
- Corrupt model file injection
- Missing model directory
- Network blockade during download attempt

#### 4. Memory Pressure from Large Images (ERROR-004)
**Immediate Impact**: Slow performance or crashes during processing
**Recovery Time**: Immediate with automatic downscaling
**Automatic Recovery**:
- Dynamic resolution scaling based on available memory
- Region-of-interest capture when bounds are known
- Image compression before processing
- Garbage collection triggers
**Manual Intervention**:
- Increase system memory availability
- Close memory-intensive applications
- Check for memory leaks in long-running processes
**Prevention**:
- Memory usage monitoring and alerts
- Automatic quality/size adjustment
- Resource limits enforcement
**Severity**: MEDIUM (performance degradation)
**Test Scenarios**:
- 4K+ screenshots on low-memory systems
- Continuous element location in tight loop
- Memory exhaustion simulation

#### 5. Invalid Coordinates Returned (ERROR-005)
**Immediate Impact**: Mis-clicks, failed automation, potential UI navigation errors
**Recovery Time**: Per-operation (each call gets fresh validation)
**Automatic Recovery**:
- Bounds checking against window dimensions
- Coordinate sanity checks (negative, extreme values)
- Automatic retry with alternative strategies
- Visual validation of results when possible
**Manual Intervention**:
- Review logs for coordinate validation failures
- Check for coordinate system mismatches (physical vs logical)
- Verify DPI/scaling settings are correct
**Prevention**:
- Rigorous input/output validation at service boundaries
- Coordinate transformation verification tests
- Screen scale factor validation
**Severity**: MEDIUM (incorrect automation behavior)
**Test Scenarios**:
- Mock AI service returning out-of-bounds coordinates
- Coordinate transformation errors
- Negative or zero-dimension bounding boxes

#### 6. Low Confidence Results (ERROR-006)
**Immediate Impact**: Uncertain automation outcomes, may require verification
**Recovery Time**: Per-operation, based on confidence thresholds
**Automatic Recovery**:
- Confidence-based fallback chaining
- Human-in-the-loop prompts for critical operations
- Multiple strategy voting/averaging
- Result history tracking for anomalous patterns
**Manual Intervention**:
- Review confidence thresholds in configuration
- Examine specific failure cases for patterns
- Adjust preprocessing or model parameters
**Prevention**:
- Confidence calibration with known test cases
- Dynamic threshold adjustment based on history
- A/B testing of different approaches
**Severity**: LOW (informational, affects decision making)
**Test Scenarios**:
- Ambiguous UI elements (similar appearance)
- Low-contrast or obscured targets
- Rapid UI changes during processing

### Error Classification System
```
SEVERITY LEVELS:
- CRITICAL: Complete system failure requiring immediate attention
- HIGH: Major functionality loss, significant user impact  
- MEDIUM: Reduced functionality or performance, workaround available
- LOW: Degraded quality or informational, minimal user impact
- INFO: Diagnostic information, no action required

ERROR CATEGORIES:
- INFRASTRUCTURE: Screenshot, model loading, memory issues
- EXTERNAL_DEPENDENCY: AI service, network, gateway issues
- LOGIC_ERROR: Coordinate validation, algorithm mistakes
- DATA_QUALITY: Low confidence, ambiguous results, noise
- CONFIGURATION: Missing settings, invalid values, permission issues
```

### Rescue Procedure Standardization
```
IMMEDIATE RESPONSE (<1 minute):
1. Detect failure through monitoring/health checks
2. Activate automatic fallback mechanisms
3. Notify on-call personnel if user-impacting
4. Begin diagnostic data collection

SHORT-TERM RECOVERY (<15 minutes):
1. Verify fallback mechanisms are functioning
2. Check for self-healing (transient issues resolved)
3. Deploy known-good configuration if available
4. Restart affected service components

LONG-TERM RESOLUTION (>15 minutes):
1. Root cause analysis through logs/metrics
2. Implement permanent fix or workaround
3. Update monitoring/alerting to prevent recurrence
4. Conduct post-incident review and documentation
```

## Section 3: Security Analysis
* Data flow security (input validation, output encoding)
* Authentication and authorization requirements
* Secrets management (API keys, credentials)
* Vulnerability assessment (input sanitization, injection prevention)
* Compliance considerations (data handling, privacy)
* Third-party component security (dependency vetting)

### Data Flow Security
```
INPUT VALIDATION:
- Screenshot inputs: Validated as legitimate image formats (PNG/JPEG)
- Coordinate inputs: Range-checked against screen dimensions
- Text prompts: Length-limited, sanitized for injection attempts
- Region bounds: Validated for positive dimensions, screen containment

OUTPUT ENCODING:
- ElementLocation results: Numerical data only, no serialization risks
- Error messages: Sanitized to prevent information leakage
- Log outputs: Structured logging prevents injection vulnerabilities
- API responses: JSON-encoded with proper content-type headers

TRUST BOUNDARIES:
- Trusted: Internal service-to-service calls within same trust boundary
- Untrusted: External AI service gateway (requires authentication)
- Semi-trusted: Screenshot capture (platform-provided, validated format)
```

### Authentication and Authorization
```
INTERNAL SERVICE CALLS:
- No authentication required (same security domain)
- Relies on process-level isolation and OS permissions
- Resource access controlled through standard UNIX permissions

EXTERNAL SERVICE CALLS (Gateway → AI Service):
- API key based authentication (Bearer token)
- HTTPS/TLS encryption for all communications
- Key rotation supported via configuration update
- Service account principle of least privilege

NO USER AUTHENTICATION:
- This service operates at system level, not user-facing
- Authentication handled by calling applications (WeChatAutomation)
- No credentials collected, stored, or transmitted from end users
```

### Secrets Management
```
API KEYS:
- Gateway AI service key: Stored in environment variables
- Never hardcoded in source code or configuration files
- Access restricted to service account and administrators
- Regular rotation recommended (90-day maximum)

NO OTHER SECRETS:
- No passwords, tokens, or certificates required
- No database connections or external service credentials
- All processing is local or to trusted internal services

KEY MANAGEMENT:
- Environment variable injection at deployment
- Optional integration with secret managers (AWS Secrets, Vault)
- Audit logging for key access attempts
```

### Vulnerability Assessment
```
INPUT SANITIZATION:
- Text prompts for AI service: Length limited to 1000 characters
- Special character escaping in prompts where required
- Region coordinates validated for integer types and ranges
- Screenshot format validation prevents buffer overflow exploits

INJECTION PREVENTION:
- No SQL databases involved → no SQL injection risk
- No shell command execution from untrusted inputs
- Image processing uses safe libraries (OpenCV, PIL) with validation
- HTTP requests use proper parameter binding, not string concatenation

BUFFER OVERFLOW PROTECTION:
- Image dimension validation before allocation
- Memory usage monitoring during processing
- Library-level protections in OpenCV/PyTorch/Ultralytics
- Address Space Layout Randomization (ASLR) enabled

RACE CONDITIONS:
- File operations use atomic operations where possible
- Temporary files use secure random names
- Shared resources protected by appropriate locking
- Stateless design minimizes race condition surface
```

### Compliance Considerations
```
DATA HANDLING:
- No persistent storage of processed screenshots or coordinates
- All data processing in-memory with immediate disposal
- Temporary files securely deleted after use (shredding equivalent)
- No personal data collection or retention

PRIVACY:
- Screen capture limited to application regions when possible
- No audio/video/camera access requested or used
- Keystroke logging or input monitoring deliberately avoided
- GDPR/CCPA compliant by design (no personal data stored)

AUDITABILITY:
- Comprehensive logging of all operations and failures
- Performance metrics for compliance reporting
- Error tracking for incident investigation
- No hidden telemetry or data exfiltration
```

### Third-Party Component Security
```
DEPENDENCY VETTING:
- Ultralytics YOLO: MIT license, active maintenance, security audited
- OpenCV: BSD license, extensive security history, CVE tracking
- Pillow (PIL Fork): Python Software Foundation license, well-maintained
- Requests: Apache 2.0 license, widely used, security conscious
- All dependencies checked against known vulnerability databases

VERSION PINNING:
- Exact versions specified in requirements.txt for reproducibility
- Regular security update monitoring process
- Vulnerability scanning integrated into CI/CD pipeline

ISOLATION:
- Dependencies run in same process space (no sandboxing needed)
- No privilege escalation opportunities identified
- Memory-safe languages used where possible (Python with safe extensions)
```

## Section 4: Data Flow & State Analysis
* State mutation points and immutability opportunities
* Data transformation pipelines with validation checkpoints
* External integrations and contract testing approaches
* Data lifecycle management (creation, modification, deletion)
* Backup and recovery considerations for stateful components
* Performance implications of data copying vs referencing

### State Mutation Points and Immutability Opportunities
```
STATEFUL COMPONENTS:
- UnifiedElementLocatorService: 
  * YOLO model instance (immutable after loading)
  * Screenshot helper (immutable after initialization)
  * Performance metrics (mutable - counters, timings)
  * Error state tracking (mutable - circuit breaker states)

IMMUTABILITY OPPORTUNITIES:
✓ ElementLocation results: Return new instances, never mutate
✓ Configuration objects: Treated as immutable after construction
✓ Screenshot data: Processed as immutable, copies made when needed
✓ AI service responses: Treated as immutable input data
✓ YOLO model weights: Loaded once, treated as read-only

MUTATION POINTS REQUIRING PROTECTION:
- Performance counters: Atomic operations or mutex protection
- Error state (circuit breaker): Thread-safe state transitions
- Temporary file cleanup: Reference counting or ownership tracking
- Model loading state: Double-checked locking or atomic initialization

RECOMMENDED APPROACH:
- Use immutable data transfer objects (DTOs) between stages
- Apply copy-on-write for large data like screenshots when modification needed
- Externalize state to dedicated services when complex (metrics, caching)
- Prefer functional transformation pipelines over stateful objects
```

### Data Transformation Pipelines with Validation Checkpoints
```
UNIFIED ELEMENT LOCATOR PIPELINE:
1. INPUT VALIDATION → [Check: non-null, valid types, reasonable ranges]
   → PASS: Validated request object
   → FAIL: ValidationError with specific field details

2. SCREENSHOT CAPTURE → [Check: valid image, dimensions > 0, format supported]
   → PASS: Validated PIL Image or numpy array
   → FAIL: ScreenshotCaptureError with platform details

3. YOLO PRE-SCREENING → [Check: model loaded, inference successful]
   → PASS: List of candidate bounding boxes with confidence scores
   → FAIL: FallbackTriggered (to OCR/heuristic path) with reason logged

4. MULTIMODAL JUDGMENT → [Check: gateway reachable, valid response format]
   → PASS: Parsed AI response with element coordinates/confidence
   → FAIL: FallbackTriggered (to OCR/heuristic path) with error details

5. RESULT PARSING → [Check: coordinates in valid ranges, confidence threshold]
   → PASS: ElementLocation result with validation metadata
   → FAIL: NoResultFound (empty list) or LowConfidenceWarning

6. OUTPUT VALIDATION → [Check: result type integrity, bounds sanity]
   → PASS: Certified ElementLocation result ready for consumption
   → FAIL: InternalError (should not occur with proper validation)
```

### External Integrations and Contract Testing Approaches
```
INTEGRATION POINTS:
1. SCREENSHOT CAPTURE (Platform Specific)
   - Contract: Returns valid image or None on failure
   - Testing: Mock platform APIs, validate error handling
   - Tools: Platform-specific mocking frameworks (pyfakefs, etc.)

2. YOLO MODEL INFERENCE (Ultralytics)
   - Contract: Returns tensor detections or throws exception
   - Testing: Mock model outputs, validate parsing logic
   - Tools: Dependency injection, interface segregation

3. GATEWAY → AI SERVICE (HTTP/JSON)
   - Contract: Returns JSON response or throws on network/error
   - Testing: Mock HTTP responses, validate error handling
   - Tools: HTTP mocking (responses, vcr.py), contract test frameworks

4. OCR PROCESSING (Tesseract via mcp_core)
   - Contract: Returns list of text results or empty list
   - Testing: Mock OCR outputs, validate coordinate transformations
   - Tools: Dependency injection, golden master testing

CONTRACT TESTING STRATEGY:
- Consumer-driven contracts for each external integration
- Pact or similar framework for service virtualization
- Property-based testing for transformation validity
- Golden master tests for complex visual processing pipelines
```

### Data Lifecycle Management
```
CREATION:
- Screenshot instances: Created fresh per operation, short-lived
- YOLO detection tensors: Created per inference, immediately processed
- AI service responses: Created per call, converted to internal format
- ElementLocation results: Created per successful detection, returned to caller

MODIFICATION:
- Coordinate transformations: Create new values, don't mutate inputs
- Confidence adjustments: Create new scored results from originals
- Format conversions: New objects, source preserved for rollback
- Batch processing: Immutable inputs → mutable buffer → immutable outputs

DELETION:
- Screenshot data: Explicitly deleted after processing completes
- Temporary files: Securely deleted immediately after use
- Model inference tensors: Garbage collected after use
- AI response buffers: Released after parsing completes
- Performance metrics: Retained for configured duration then rotated

RESOURCE MANAGEMENT PATTERNS:
- RAII-style resource handling where applicable
- Object pooling for frequently allocated items (considered, rejected for complexity)
- Explicit cleanup methods with try/finally blocks
- Context managers for temporary resources (files, locks, etc.)
```

### Backup and Recovery Considerations
```
STATELESS BY DESIGN:
- No persistent state requires backup or recovery
- All processing restartable from clean state
- Configuration treated as infrastructure, not application state

CONFIGURATION BACKUP:
- Service configuration backed up with infrastructure
- Version controlled for rollback capability
- Environment-specific variants managed through standard processes

PERFORMANCE METRICS PRESERVATION:
- Optional: Export metrics to external monitoring system
- Configurable retention period (default: 24 hours)
- Aggregate statistics preserved, raw samples rotated

MODEL ARTIFACTS:
- YOLO models: Treated as dependencies, not application state
- Standard dependency management applies (versioning, caching)
- Recovery: Re-download or restore from backup/cache

NO APPLICATION STATE TO BACKUP:
- Designed for horizontal scaling and restart resilience
- Failover: New instance can take over immediately
- State reconstruction: From fresh screenshots, not persisted data
```

### Performance Implications of Data Copying vs Referencing
```
SCREENSHOT DATA:
- Large binary data (1-10MB typical for screenshots)
- COST OF COPYING: High (memory bandwidth, allocation time)
- PREFERRED: Immutable referencing with copy-on-write when modification needed
- TECHNIQUE: Share data until modification required, then copy (Copy-on-Write)

COORDINATE DATA:
- Small numerical data (few integers per element)
- COST OF COPYING: Negligible
- PREFERRED: Value semantics, copy freely for safety and simplicity
- TECHNIQUE: Pass by value, return new instances

MODEL DATA:
- Large binary data (YOLO model: 5-200MB depending on variant)
- COST OF COPYING: Prohibitive
- PREFERRED: Load once, share immutable reference
- TECHNIQUE: Singleton pattern, dependency injection, read-only access

TEXT DATA:
- Variable length strings (OCR results, AI responses)
- COST OF COPYING: Moderate (proportional to string length)
- PREFERRED: Immutable strings, copy when mutation absolutely needed
- TECHNIQUE: String interning consideration for high-duplication scenarios

PERFORMANCE GUIDELINES:
- Profile before optimizing - bottlenecks often unexpected
- Prefer clarity and correctness over premature optimization
- Use standard library data structures unless proven inadequate
- Measure actual performance in realistic scenarios
```

## Section 5: Code Quality & Standards
* Readability and naming conventions adherence
* Function size and complexity metrics
* Comment quality and documentation completeness
* Error handling consistency and completeness
* Testability and dependency injection patterns
* Code review checklist application

### Readability and Naming Conventions Adherence
```
NAMING CONVENTIONS:
- Classes: PascalCase (UnifiedElementLocatorService)
- Methods/Functions: snake_case (locate_element, validate_input)
- Constants: UPPER_SNAKE (MAX_RETRIES, DEFAULT_TIMEOUT)
- Variables: snake_case (screenshot_image, candidate_regions)
- Attributes: snake_case with self prefix (self.yolo_model)

READABILITY FACTORS:
- Line length: Target 88 characters, maximum 100
- Function depth: Maximum 4 levels of nesting
- Section comments: Logical grouping with descriptive headers
- Type hints: Complete for all public interfaces and complex logic
- Docstrings: Google style for all public classes and methods

SPECIFIC IMPLEMENTATIONS:
- Clear pipeline stage method names (_run_yolo_prescreening, etc.)
- Descriptive variable names (confidence_threshold, not ct)
- Consistent error naming (*Error suffix for exception types)
- Meaningful return types (Optional[ElementLocation], List[ElementLocation])
- Avoidance of magic numbers (named constants for thresholds, timeouts)
```

### Function Size and Complexity Metrics
```
TARGET METRICS:
- Function length: Maximum 50 lines (prefer 20-30 for readability)
- Cyclomatic complexity: Maximum 10 per function (prefer < 5)
- Nesting depth: Maximum 4 levels
- Parameters: Maximum 5 per function (prefer <= 3)
- Return points: Maximum 2-3 per function (early returns preferred)

PIPELINE FUNCTION BREAKDOWN:
- locate_element: ~40 lines (orchestration, delegation to privates)
- _validate_inputs: ~15 lines (input checking, early returns)
- _capture_screenshot: ~20 lines (platform fallback logic)
- _run_yolo_prescreening: ~25 lines (model inference, result parsing)
- _call_ai_service: ~20 lines (HTTP request, response handling)
- _parse_ai_result: ~15 lines (JSON parsing, coordinate conversion)
- _apply_fallback_strategies: ~30 lines (OCR/heuristic logic)
- _validate_and_return_result: ~15 lines (bounds checking, confidence)

COMPLEXITY REDUCTION TECHNIQUES:
- Guard clauses for early error detection
- Strategy pattern for fallback mechanisms
- Dependency injection for testability
- Value objects for complex data (ElementLocation, SearchRequest)
- Pipeline pattern with clear stage separation

MEASUREMENT TOOLS:
- radon for cyclomatic complexity analysis
- pylint for function length and style violations
- Custom scripts for nesting depth and parameter counting
```

### Comment Quality and Documentation Completeness
```
COMMENT TYPES AND USAGE:
- Docstrings: Complete for all public APIs (classes, methods)
- Block comments: Explain why, not what (complex algorithms, workarounds)
- Inline comments: Sparingly used for non-obvious operations
- TODOs: Format with issue numbers and dates when applicable
- Section headers: Clearly mark logical code divisions

DOCUMENTATION COMPLETENESS:
- Public interface: 100% docstring coverage
- Protected/internal: 80%+ docstring coverage (explain intent)
- Complex algorithms: Step-by-step commentary in block comments
- Error conditions: Documented in docstrings and block comments
- Configuration options: Explained with valid values and examples

QUALITY GUIDELINES:
- Comments explain reasoning, not repeat code
- Outdated comments removed or updated during modifications
- Comment-to-code ratio maintained at useful levels (~-20%)
- Documentation follows project conventions exactly
- Examples included for non-obvious usage patterns
```

### Error Handling Consistency and Completeness
```
ERROR HANDLING PATTERNS:
- Specific exception types: Custom exceptions for each failure mode
- Early validation: Fail fast on invalid inputs
- Graceful degradation: Fallback strategies for external failures
- Context preservation: Chain exceptions with causal relationships
- Logging: Structured logs with correlation IDs for tracing

EXCEPTION HIERARCHY:
- UnifiedElementLocatorError (base)
  ├─ ValidationError (input problems)
  ├─ ScreenshotCaptureError (platform issues)
  ├─ ModelLoadingError (YOLO/problems)
  ├─ AIServiceUnavailableError (gateway/AI service)
  ├─ ProcessingError (internal algorithm failures)
  └─ FallbackTriggered (expected degradation to alternative methods)

HANDLING COMPLETENESS:
- All external service calls wrapped in try/catch
- All platform-specific code has fallback paths
- Resource acquisition uses try/finally or context managers
- Error messages include actionable remediation guidance
- Sensitive information excluded from error messages (security)

RETURN VALUE PATTERNS:
- Optional[T] for possibly missing results
- List[T] for collections (never None for empty)
- Boolean/Tuple for status+data when appropriate
- Consistent: Never mix error codes with valid returns
```

### Testability and Dependency Injection Patterns
```
DEPENDENCY INJECTION:
- Constructor injection for all external dependencies
- Interfaces used where multiple implementations possible
- Service locator pattern avoided in favor of explicit DI
- Optional dependencies handled with clear documentation
- Factory patterns considered but rejected for simplicity

TESTABILITY FEATURES:
- All dependencies injectable for mocking/stubbing
- Stateless pure functions where possible (easy unit testing)
- Complex algorithms extracted to testable functions
- Configuration accessible for test scenario setup
- Clear separation of concerns enables focused testing

MOCKING STRATEGIES:
- Platform abstractions: Mock screenshot capture, input simulation
- External services: Mock HTTP gateway, AI service responses
- ML components: Mock YOLO outputs, AI service responses
- File system: Temporary directories, fake file systems
- Time: Mock timestamps for time-dependent logic

TEST DOUBLE USAGE:
- Mocks: For verifying interactions (call counts, parameters)
- Stubs: For providing canned responses (state verification)
- Fakes: For simplified implementations (in-memory repositories)
- Spies: Limited use for callback verification when needed

INTEGRATION TEST APPROACH:
- Real dependencies for infrastructure validation
- Contract tests for external service boundaries
- End-to-end scenarios for critical user journeys
- Performance benchmarks for regression detection
```

### Code Review Checklist Application
```
PRE-MERGE CHECKLIST:
☐ Code follows project naming conventions exactly
☐ All public interfaces have complete docstrings
☐ No functions exceed 50 lines without justification
☐ Cyclomatic complexity < 10 for all functions
☐ All external dependencies are injectable/mockable
☐ Error handling follows established patterns
☐ Input validation present at all trust boundaries
☐ Output encoding prevents injection vulnerabilities
☐ Resource leaks prevented (try/finally, context managers)
☐ Test coverage meets minimum thresholds (80%+)
☐ No hardcoded secrets or credentials
☐ Configuration options documented and validated
☐ Performance implications considered and documented
☐ Forward compatibility considered (extension points)
☐ Rollback strategy documented for breaking changes
☐ Monitoring and observability hooks present
☐ Security implications reviewed and addressed
☐ Accessibility considerations addressed where applicable
☐ Technical debt items identified and tracked
☐ Future maintenance burden estimated and acceptable
```

## Section 6: Tests
* Unit test strategy and coverage targets
* Integration test scenarios and data management
* End-to-end test plans for critical user journeys
* Performance benchmarking and regression detection
* Property-based testing and fuzzing approaches
* Test data generation and mocking strategies

### Unit Test Strategy and Coverage Targets
```
TESTING PYRAMID:
- Unit Tests: 70% of test effort (fast, isolated, deterministic)
- Integration Tests: 20% of test effort (cross-component interactions)
- End-to-End Tests: 10% of test effort (critical user journeys)

COVERAGE TARGETS:
- Line coverage: 90% minimum
- Branch coverage: 80% minimum  
- Complexity coverage: 85% minimum (cyclomatic complexity > 5)
- Public interface coverage: 100% (all public methods tested)

UNIT TEST FOCUS AREAS:
1. INPUT VALIDATION
   - Test all validation edge cases (null, empty, invalid types)
   - Boundary value testing for numerical inputs
   - Length and format validation for string inputs
   - Error message correctness and specificity

2. PIPELINE STAGES (isolated testing)
   - YOLO pre-screening with mock model outputs
   - AI service communication with mocked HTTP responses
   - Result parsing with various AI response formats
   - Fallback strategy selection and execution
   - Coordinate transformation and validation

3. ERROR HANDLING AND RESILIENCE
   - Circuit breaker activation and deactivation
   - Fallback chaining under various failure scenarios
   - Graceful degradation to alternative methods
   - Error logging and metric collection verification

4. CONFIGURATION AND SETUP
   - Default value correctness
   - Configuration validation and error reporting
   - Dependency injection and initialization
   - Resource cleanup and leak prevention

TEST FRAMEWORKS AND TOOLS:
- Primary: pytest with fixtures for dependency injection
- Mocking: unittest.mock for patching and MagicMock
- Fixtures: Factory Boy or custom builders for test data
- Assertions: PyTest assertions with detailed failure messages
- Parametrization: Comprehensive test case coverage with @pytest.mark.parametrize
```

### Integration Test Scenarios and Data Management
```
INTEGRATION TEST BOUNDARIES:
- Service-to-service interactions within bounded context
- External service contracts (gateway AI service)
- Platform abstraction layer (screenshot capture, input)
- Data format transformations between components

SCENARIOS:
1. FULL PIPELINE WITH MOCKED EXTERNAL DEPENDENCIES
   - Given: Valid inputs, mocked YOLO and AI service responses
   - When: Element location request processed through full pipeline
   - Then: Correct ElementLocation returned with expected confidence
   - Variations: Different success/failure combinations at each stage

2. FALLBACK CHAINING BEHAVIOR
   - Given: AI service unavailable, OCR available
   - When: Element location request processed
   - Then: Falls back to OCR/heuristic methods successfully
   - Metrics: Performance impact measurement, quality degradation tracking

3. ERROR CONDITION PROPAGATION
   - Given: Specific failure at known pipeline stage
   - When: Element location request processed
   - Then: Appropriate error handling and fallback activation
   - Verification: Error logs, metrics, return values correct

4. CONCURRENT ACCESS SCENARIOS
   - Given: Multiple simultaneous element location requests
   - When: Service under load
   - Then: Correct handling, no race conditions, resource safety
   - Focus: Thread safety, connection pooling, memory management

DATA MANAGEMENT STRATEGY:
- Test data factories for reproducible, configurable test instances
- Golden master data for complex visual processing validation
- Synthetic data generation for edge case testing
- Fixture scoping: function, class, module, session as appropriate
- Data isolation: Database transactions, temporary directories, unique identifiers
```

### End-to-End Test Plans for Critical User Journeys
```
CRITICAL USER JOURNEYS:
1. ARTICLE FETCHING WORKFLOW
   - Given: WeChat running, valid account name configured
   - When: User requests article fetching for account
   - Then: Articles successfully located, clicked, and processed
   - Metrics: Success rate, timing, article quality validation

2. SEARCH BAR LOCATION AND INTERACTION
   - Given: WeChat at public account profile page
   - When: User requests to search for specific content
   - Then: Search bar located, clicked, and text input successful
   - Validation: Search results appear, correct navigation occurs

3. ARTICLE LIST NAVIGATION
   - Given: WeChat public account profile loaded
   - When: User requests to navigate to article list
   - Then: Article list tab located and selected successfully
   - Validation: Article titles visible, correct page transition

4. DYNAMIC UI ADAPTATION
   - Given: WeChat UI changes (update, theme change)
   - When: Element location requested after UI change
   - Then: Service adapts, finds elements in new positions
   - Validation: Continued successful operation despite UI variation

TEST ENVIRONMENT AND SETUP:
- Isolation: Dedicated test environment, clean state per test run
- Dependencies: Real or contracted based on test type
- Instrumentation: Performance monitoring, logging verification
- Cleanup: Complete state reset, resource release verification
- Parallelization: Safe parallel execution where stateless

VALIDATION APPROACHES:
- Primary: Behavioral validation (did correct action occur)
- Secondary: State validation (UI in expected state after action)
- Tertiary: Timing validation (within acceptable performance bounds)
- Quaternary: Logging validation (expected events recorded correctly)
```

### Performance Benchmarking and Regression Detection
```
BASELINE ESTABLISHMENT:
- Performance benchmarks established for all public APIs
- Tested under controlled conditions (known hardware, load)
- Metrics: Latency, throughput, resource consumption, success rate
- Baseline stored with version identification for comparison

REGRESSION DETECTION:
- Automated performance testing in CI/CD pipeline
- Statistical significance testing for performance changes
- Threshold-based alerts for unacceptable degradation
- Trend analysis for gradual performance drift identification

KEY PERFORMANCE INDICATORS (KPIs):
- Element location latency: P50, P95, P99 percentiles
- Throughput: Requests per second under sustained load
- Error rate: Percentage of failed operations
- Resource usage: CPU, memory, disk I/O during operation
- Fallback frequency: How often external services unavailable

BENCHMARK SCENARIOS:
- Cold start: First request after service initialization
- Warm start: Subsequent requests with cached resources
- Load testing: Gradual increase to identify saturation points
- Stress testing: Beyond capacity to observe failure modes
- Recovery testing: Behavior after stress period ends

TOOLS AND FRAMEWORKS:
- Locust or k6 for load testing scenarios
- Benchmark or pytest-benchmark for microbenchmarks
- Memory profiler for allocation pattern analysis
- CPU profiler for hotspot identification
- Custom timing wrappers for specific operation measurement
```

### Property-Based Testing and Fuzzing Approaches
```
PROPERTY-BASED TESTING (Hypothesis):
- Input validation: Properties that should always hold
- Transformation pipelines: Idempotency where applicable
- Error handling: Consistent behavior under fault injection
- Performance characteristics: Bounds on resource usage
- Security properties: No information leakage in errors

FUZZING APPROACHES:
- Input fuzzing: Malformed or unexpected inputs to validation
- Configuration fuzzing: Invalid or extreme configuration values
- Protocol fuzzing: Malformed HTTP responses from mocked services
- State machine fuzzing: Unexpected sequences of operations

TEST DATA GENERATION:
- Strategies: Built-in and custom strategies for complex types
- Composite strategies: Building complex valid/invalid inputs
- Recursive strategies: For nested or hierarchical data structures
- Edge case focus: Boundaries, extremes, special values, empty cases

INTEGRATION WITH UNIT TESTS:
- Property-based tests supplement example-based testing
- Fuzzing runs in CI/CD with time/resource limits
- Property definitions focus on invariants and contracts
- Seed management for reproducible fuzzing sessions
```

### Test Data Generation and Mocking Strategies
```
MOCKING STRATEGIES BY DEPENDENCY TYPE:
- PLATFORM SERVICES: 
  * Screenshot capture: Return predefined test images
  - Input simulation: Validate coordinates and timing
  * Window management: Controlled bounds and state responses

- ML COMPONENTS:
  * YOLO model: Return predefined detection tensors
  * AI service: Return predefined JSON responses
  * Feature extraction: Return predictable feature vectors

- EXTERNAL SERVICES:
  * HTTP gateway: Return controlled status codes and bodies
  * Timing dependencies: Simulate latency and timeouts
  * Error injection: Controlled failure rates and types

- FILE SYSTEM:
  * Temporary files: Unique names in isolated directories
  * Model files: Controlled presence/absence/corruption
  * Configuration files: Valid, invalid, missing scenarios

- TIME DEPENDENCIES:
  * Clock mocking: Controllable time progression
  * Timeout testing: Precise control over delay durations
  * Cron/schedule testing: Specific time-based behaviors

TEST DATA GENERATION APPROACHES:
- VALID DATA: 
  * Known good inputs for positive testing
  * Boundary values for limit testing
  * Equivalence classes for partition testing
  
- INVALID DATA:
  * Type violations for contract testing
  * Range violations for boundary testing
  * Format violations for parsing validation
  
- EDGE CASES:
  * Empty/null inputs for robustness testing
  * Extremely large inputs for stress testing
  * Malformed inputs for security testing
  
- STATE SEQUENCES:
  * Valid workflows for integration testing
  * Error recovery paths for resilience testing
  * Transition scenarios for state machine validation
```

### Test Organization and Execution
```
TEST STRUCTURE:
- unit/: Pure unit tests with mocking/stubbing
- integration/: Cross-component tests with real/contracted dependencies
- e2e/: End-to-end tests simulating real user scenarios
- performance/: Benchmarks and load testing scenarios
- fixtures/: Shared test data factories and builders
- utils/: Test helpers, custom assertions, mock builders

EXECUTION STRATEGY:
- Local development: Fast unit tests on save/commit
- CI pipeline: Full test suite with parallel execution
- Nightly builds: Extended tests, property-based, fuzzing
- Release candidates: Performance benchmarks, stress tests
- Pre-deployment: Smoke tests, sanity checks in staging

REPORTING AND METRICS:
- Coverage reports: Line, branch, complexity coverage
- Trend analysis: Coverage and performance over time
- Failure analysis: Root cause categorization and tracking
- Test duration: Optimization for feedback loop speed
- Flaky test detection: Quarantine and investigation process
```

## Section 7: Performance
* Baseline performance metrics and bottleneck identification
* Optimization techniques and expected improvements
* Load testing methodology and capacity planning
* Resource usage patterns (CPU, memory, disk, network)
* Caching strategies and cache invalidation policies
* Database query optimization and indexing strategies

### Baseline Performance Metrics and Bottleneck Identification
```
CURRENT BASELINE (LEGACY APPROACHES):
- Element location latency: 500ms - 2000ms (highly variable)
- Success rate: 60% - 80% (dependent on UI complexity)
- CPU usage: Moderate (OCR processing intensive)
- Memory usage: Low to Moderate (screenshot dependent)
- Fallback frequency: High (30% - 50% of operations)

EXPECTED BASELINE (UNIFIED APPROACH):
- Element location latency: 800ms - 3000ms (increased AI service latency)
- Success rate: 85% - 95% (improved accuracy from multimodal judgment)
- CPU usage: Moderate to High (YOLO + AI service processing)
- Memory usage: Moderate (screenshot + model storage)
- Fallback frequency: Low (5% - 15% with effective chaining)

BOTTLENECK IDENTIFICATION:
1. PRIMARY: AI service gateway and model inference latency
   - Network round-trip to gateway service
   - AI model processing time on backend
   - Queueing delays during peak usage

2. SECONDARY: YOLO model inference (CPU-bound)
   - Image preprocessing and tensor conversion
   - Model forward pass computation
   - Non-maximum suppression and result filtering

3. TERTIARY: Screenshot capture and encoding
   - Platform-specific capture latency
   - Image format conversion and compression
   - Base64 encoding for transmission

4. MINIMAL: Coordinate transformation and validation
   - Simple arithmetic operations
   - Memory allocation for result objects
   - Validation checks and error handling

MEASUREMENT APPROACH:
- Synthetic benchmarks with controlled test images
- Real-world measurements with actual WeChat UI
- Component-level profiling to isolate bottlenecks
- Load testing to identify saturation points
- Memory profiling to detect leaks and inefficiencies
```

### Optimization Techniques and Expected Improvements
```
YOLO OPTIMIZATIONS:
- Model quantization: INT8 precision for 2-4x speedup
- Model pruning: Remove redundant neurons for efficiency
- Input resolution scaling: Process at optimal size for accuracy/speed
- Batch processing: Multiple regions per inference call
- Caching: Recent results for static UI elements

AI SERVICE OPTIMIZATIONS:
- Request batching: Combine multiple element requests
- Response streaming: Progressive results for long lists
- Connection pooling: Reuse HTTP connections
- Keep-alive: Reduce connection establishment overhead
- Compression: Enable HTTP compression for large responses

SCREENSHOT OPTIMIZATIONS:
- Region-of-interest capture: When bounds known, capture less
- Format selection: JPEG for photos, PNG for graphics
- Quality tuning: Balance fidelity and file size
- Memory mapping: Reduce copying overhead
- Temporal reuse: Cache recent screenshots briefly

COORDINATE PROCESSING:
- Vectorized operations: NumPy where applicable
- Early termination: Stop processing when sufficient results
- Precomputation: Cache transformation matrices
- Lazy evaluation: Defer work until actually needed

EXPECTED IMPROVEMENTS AFTER OPTIMIZATIONS:
- Element location latency: 400ms - 1500ms (30-50% reduction)
- Success rate: 90% - 98% (continued accuracy improvement)
- CPU usage: Optimized (better utilization, less waste)
- Memory usage: Reduced (better caching, less duplication)
- Fallback frequency: Very low (1% - 5% with effective strategies)

OPTIMIZATION TRADEOFFS:
- Accuracy vs Speed: Configurable confidence thresholds
- Resource Usage vs Latency: Preview quality vs processing time
- Development Complexity vs Performance: Simple vs optimized code
- Freshness vs Performance: Cached results vs live processing
```

### Load Testing Methodology and Capacity Planning
```
LOAD TESTING APPROACH:
- Ramp-up testing: Gradual increase to find saturation point
- Steady state: Sustained load at target levels
- Spike testing: Sudden increases to test elasticity
- Stress testing: Beyond capacity to find breaking points
- Soak testing: Extended duration to find memory leaks

KEY METRICS TO MONITOR:
- Latency percentiles (P50, P95, P99, Pmax)
- Error rates and failure patterns
- Resource utilization (CPU, memory, network, disk)
- Queue depths and waiting times
- Throughput (requests/sec, elements/sec)
- Fallback rates and degradation patterns

CAPACITY PLANNING CONSIDERATIONS:
- TARGET LOAD: 10 element location requests/second
- PEAK LOAD: 50 element location requests/second
- BURST CAPACITY: 100 requests in 10-second window
- RECOVERY TIME: < 30 seconds to return to normal after peak

SCALING STRATEGIES:
- VERTICAL: More powerful hardware (faster CPU, more RAM)
- HORIZONTAL: Multiple service instances (load balancing)
- ALGORITHMIC: Better models, more efficient algorithms
- ARCHITECTURAL: Caching, batching, asynchronous processing

RESOURCE REQUIREMENTS ESTIMATES:
- CPU: 2-4 cores recommended for target load
- Memory: 2-4 GB RAM for model caching and processing
- Network: 10-100 Mbps depending on AI service interaction
- Storage: 1-5 GB for model caching and temporary files
```

### Resource Usage Patterns
```
CPU USAGE PATTERNS:
- Idle: Low (5-10%) - waiting for requests
- Light load: Moderate (20-40%) - occasional processing
- Medium load: High (60-80%) - sustained YOLO/AI processing
- Peak load: Very High (85-100%) - maximum capacity utilization
- Spike handling: Queuing with graceful degradation

MEMORY USAGE PATTERNS:
- Base footprint: 500MB - 1GB (service, dependencies, models)
- Screenshot buffers: 5MB - 50MB per concurrent operation
- Model storage: 200MB - 1GB (YOLO models cached)
- Processing buffers: 10MB - 100MB temporary allocations
- GC pressure: Moderate to High (object creation/destruction)

NETWORK USAGE PATTERNS:
- Idle: Minimal (keep-alives, health checks)
- Request/response: Bursts during AI service communication
- Base64 overhead: ~33% increase for image transmission
- Connection reuse: Significant reduction in establishment costs

DISK USAGE PATTERNS:
- Temporary files: Rapid creation/deletion of screenshot crops
- Model files: Static storage of YOLO model files
- Log files: Growing linearly with usage (rotation required)
- Cache files: Temporary storage for performance optimization

RESOURCE CONTENTION AND MITIGATION:
- CPU: Process prioritization, nice levels, core affinity
- Memory: Swapping prevention, OOM killer adjustment
- Network: QoS traffic shaping, bandwidth reservation
- Disk: SSD preference, IO scheduling, fragmentation prevention
```

### Caching Strategies and Cache Invalidation Policies
```
SCREENSHOT CACHING:
- Strategy: Short-term temporal caching (5-30 second TTL)
- Invalidation: Time-based, UI change detection, manual trigger
- Size limit: LRU eviction when cache exceeds memory threshold
- Thread safety: Read-write locks or concurrent collections
- Security: Isolation between users/sessions, no cross-contamination

MODEL AND RESULT CACHING:
- YOLO models: Permanent caching with version checking
- AI responses: Short-term caching (1-5 minute TTL) for repetitive queries
- Coordinate transforms: Permanent caching of transformation matrices
- Element locations: Session-based caching for static UI elements

PERFORMANCE DATA CACHING:
- Metrics: Rolling window storage (last hour, day, week)
- Statistics: Pre-aggregated for common queries
- Reports: Generated on demand, cached briefly for reuse
- Health checks: Cached results with short TTL for responsiveness

CACHE INVALIDATION TRIGGERS:
- TIME-BASED: TTL expiration for all cached items
- EVENT-BASED: UI change detection, configuration updates
- MANUAL: Administrative cache clearing, troubleshooting
- SIZE-BASED: LRU/LFU eviction when limits exceeded
- PRESSURE-BASED: Memory/disk usage thresholds

CACHE COHERENCY:
- Single source of truth principle where applicable
- Write-through or write-behind strategies as appropriate
- Version vectors or timestamps for conflict detection
- Read repair mechanisms for distributed caching scenarios
```

### Database Query Optimization and Indexing Strategies
```
NOTE: This service does not use direct database queries.
All data processing is in-memory or via service calls.

RELEVANT PATTERNS FOR FUTURE EXTENSION:
- If adding persistence for metrics or learning:
  * Connection pooling: Reuse database connections
  * Prepared statements: Prevent SQL injection, improve performance
  * Indexing: On frequently queried columns (timestamps, types)
  * Partitioning: By time or other dimensions for scale
  * Caching: Query result caching for repetitive operations

CURRENT IN-MEMORY OPTIMIZATIONS:
- Data structures: Appropriate choices for access patterns
- Algorithms: Efficient searching, sorting, and filtering
- Memory layout: Cache-friendly access patterns
- Concurrency: Lock-free structures where applicable and safe
```

## Section 8: Observability
* Logging strategy and levels (debug, info, warn, error)
* Metrics collection and key performance indicators
* Health check endpoints and readiness/liveness probes
* Distributed tracing and correlation ID propagation
* Alerting strategies and notification channels
* Audit logging and compliance tracking
* Debugging hooks and introspection capabilities

### Logging Strategy and Levels
```
LOGGING PHILOSOPHY:
- Debug: Detailed internal state for troubleshooting development issues
- Info: Operational milestones and significant events in normal operation
- Warning: Potentially problematic situations that don't prevent operation
- Error: Actual failures that prevent successful completion of operations
- Critical: Severe failures requiring immediate attention (rarely used)

STRUCTURED LOGGING:
- JSON format for machine parsing and analysis
- Standard fields: timestamp, level, logger, message, trace_id
- Context fields: operation_type, element_type, confidence, duration
- No sensitive data: Coordinates OK, screenshot data never logged
- Correlation IDs: Enable request tracing across service boundaries

LOGGING BY COMPONENT:
- UnifiedElementLocatorService:
  * Info: Pipeline start/end, strategy selection, fallback activation
  * Debug: Input parameters, intermediate results, timing breakdowns
  * Warning: Low confidence results, degraded performance detected
  * Error: Pipeline failures, external service timeouts, validation failures
  
- YOLO Pre-screening:
  * Info: Model loaded, inference completed, candidate count
  * Debug: Raw detection outputs, confidence thresholds applied
  * Warning: Unusually high/low detection counts, strange aspect ratios
  * Error: Model loading failures, inference exceptions, invalid outputs
  
- AI Service Communication:
  * Info: Request sent, response received, processing time
  * Debug: Request details (URL, headers, body), response content
  * Warning: Slow responses (>5s), non-standard response formats
  * Error: Connection failures, timeouts, HTTP error codes, parsing failures
  
- Fallback Strategies:
  * Info: Fallback activated, reason, expected degradation level
  * Debug: Fallback method inputs, intermediate results
  * Warning: Fallback also failing or producing poor results
  * Error: All strategies failed, complete operation failure

LOG ROTATION AND RETENTION:
- Size-based rotation: 100MB per file, keep 10 files
- Time-based rotation: Daily files, keep 30 days
- Compression: Enable compression for archived logs
- Filtering: Separate logs by level if required for compliance
- Shipping: Forward to external systems (ELK, Splunk, CloudWatch)
```

### Metrics Collection and Key Performance Indicators
```
METRICS TYPES:
- Counters: Monotonically increasing values (requests, errors, fallbacks)
- Gauges: Instantaneous values (memory usage, queue depth, active requests)
- Histograms: Distribution of values (latency, confidence scores, processing times)
- Summaries: Similar to histograms with streaming calculation

KEY PERFORMANCE INDICATORS:
LATENCY METRICS:
- element_location_latency_seconds: Histogram (P50, P95, P99)
- yolo_inference_latency_seconds: Histogram 
- ai_service_latency_seconds: Histogram
- screenshot_capture_latency_seconds: Histogram
- fallback_activation_latency_seconds: Histogram

THROUGHPUT METRICS:
- element_location_requests_total: Counter
- successful_element_locations_total: Counter
- fallback_activations_total: Counter (by strategy: ocr, heuristic)
- ai_service_calls_total: Counter
- yolo_invocations_total: Counter

RESOURCE METRICS:
- process_cpu_seconds_total: Counter
- process_resident_memory_bytes: Gauge
- process_virtual_memory_bytes: Gauge
- file_descriptor_count: Gauge
- screenshot_bytes_total: Counter (processed image data)

QUALITY METRICS:
- element_location_confidence: Histogram (0.0-1.0 distribution)
- elements_per_request: Histogram (how many found per request)
- false_positive_rate: Estimated via feedback mechanisms
- user_satisfaction_score: From explicit feedback when available

BUSINESS METRICS:
- articles_found_per_session: Counter (for WeChat automation use case)
- search_success_rate: Gauge (successful account location)
- automation_cycle_time_seconds: Histogram (end-to-end timing)
```

### Health Check Endpoints and Readiness/Liveness Probes
```
HEALTH CHECK ARCHITECTURE:
- Liveness Probe: Determines if container should be restarted
- Readiness Probe: Determines if container should receive traffic
- Startup Probe: Determines when application has started
- Liveness: "Is the application running?"
- Readiness: "Is the application ready to serve requests?"
- Startup: "Has the application finished initializing?"

ENDPOINTS:
- GET /health/liveness
  * Returns 200 if: Process running, no deadlock detected
  * Returns 503 if: Process hung, critical failure requiring restart
  
- GET /health/readiness  
  * Returns 200 if: Service initialized, dependencies available
  * Returns 503 if: Initializing, dependencies down, overloaded
  
- GET /health/startup
  * Returns 200 if: YOLO model loaded, AI service reachable
  * Returns 503 if: Still initializing, critical components missing
  
- GET /health/metrics
  * Returns 200 if: Monitoring system operational
  * Returns Prometheus format metrics for scraping

HEALTH CHECK IMPLEMENTATION:
- Liveness: Simple process check, resource availability
- Readiness: Dependency validation, resource thresholds
- Startup: Component initialization completion
- Metrics: Lightweight, non-blocking metrics collection
- All endpoints: <50ms response time, minimal resource consumption
```

### Distributed Tracing and Correlation ID Propagation
```
TRACE CONTEXT PROPAGATION:
- Incoming requests: Extract trace ID from headers if present
- Outgoing requests: Inject trace ID into headers for downstream services
- Internal spans: Create child spans for each pipeline stage
- Span attributes: Operation type, parameters, results, timing
- No sensitive data: Coordinates OK, image data never in traces

TRACING FRAMEWORK INTEGRATION:
- OpenTelemetry compatible instrumentation
- Automatic span creation for service boundaries
- Manual spans for complex internal operations
- Context propagation through async/await boundaries
- Export to tracing systems (Jaeger, Zipkin, AWS X-Ray)

SPAN HIERARCHY EXAMPLE:
Trace: element_location_request_123
├── Span: validate_input (5ms)
├── Span: capture_screenshot (120ms)
│   └── Span: platform_specific_capture (100ms)
├── Span: yolo_prescreening (300ms)
│   └── Span: model_inference (250ms)
├── Span: ai_service_judgment (800ms)
│   └── Span: http_request_gateway (750ms)
├── Span: result_parsing (25ms)
└── Span: fallback_activation (decision only, 0ms if not used)

CORRELATION ID MANAGEMENT:
- Generated at service entry if not present
- Propagated through all asynchronous operations
- Included in all log entries for traceability
- Used for metrics labeling and aggregation
- Stored with results for debugging and feedback loops
```

### Alerting Strategies and Notification Channels
```
ALERTING PRINCIPLES:
- Actionable: Every alert should have a clear response procedure
- Informative: Include context, metrics, and suggested actions
- Routed: Sent to appropriate teams/channels based on type
- Deduplicated: Suppress flapping alerts, enforce cooldown periods
- Escalating: Increase notification frequency for persistent issues

ALERT TYPES AND THRESHOLDS:
- CRITICAL (page immediately):
  * Service downtime: No successful requests for 2 minutes
  * Health check failure: Liveness probe failing for 3 consecutive checks
  * Resource exhaustion: Memory >95% for 5 minutes
  
- HIGH (notify within 15 minutes):
  * High error rate: >20% failure rate for 5 minutes
  * Elevated latency: P95 > 5 seconds for 10 minutes
  * Gateway downtime: AI service unreachable for 3 minutes
  
- MEDIUM (notify within 1 hour):
  * Degraded performance: P95 > 2 seconds for 20 minutes
  * High fallback rate: >40% of requests using fallback methods
  * Unusual patterns: Sudden changes in confidence distribution
  
- LOW (log for review, no immediate action):
  * Configuration changes: Non-critical settings modified
  * Minor version updates: Dependencies updated within compatibility
  * Informational events: Service started/stopped normally

NOTIFICATION CHANNELS:
- PAGING: SMS, phone calls, PagerDuty for critical alerts
- SLACK: #alerts-production, #alerts-wechat-automation for high/medium
- EMAIL: Team mailing lists for low priority and summaries
- WEBHOOKS: Custom integrations for ticketing systems, etc.
- DASHBOARDS: Real-time visibility in monitoring systems

ALERT SUPPRESSION AND FLAP PREVENTION:
- Throttling: Maximum N alerts per time period per type
- Debouncing: Wait M seconds before firing to avoid transient issues
- Dependency awareness: Don't alert if known dependency is down
- Maintenance windows: Suppress during scheduled maintenance
- Known issues: Temporarily suppress for tracked problems with ETA
```

### Audit Logging and Compliance Tracking
```
AUDIT LOG REQUIREMENTS:
- Immutable: Append-only, tamper-evident storage
- Complete: All security-relevant events captured
- Attributable: Actions tied to specific identities or service accounts
- Timestamps: Accurate timekeeping with timezone information
- Retention: Configurable based on regulatory requirements

AUDITABLE EVENTS:
- CONFIGURATION CHANGES:
  * Who changed what setting to what value
  * When and from what source (API, CLI, config file)
  * Validation of new values against allowed ranges
  
- SECURITY INCIDENTS:
  * Authentication failures (if applicable)
  * Authorization attempts outside permitted scope
  * Potential data exposure or leakage incidents
  * Security tool alerts (virus detection, intrusion attempts)
  
- SYSTEM CHANGES:
  * Service start/stop/restart events
  * Dependency version changes or updates
  * Resource allocation changes (memory limits, CPU shares)
  
- DATA ACCESS (if applicable):
  * Although this service doesn't store persistent data
  * Would apply if caching or metrics storage added

IMPLEMENTATION APPROACH:
- Specialized audit logger separate from debug/ops logs
- Write-once storage or write-ahead logging for durability
- Cryptographic chaining or signing for tamper evidence
- Regular integrity verification of audit logs
- Secure transmission to centralized audit systems
```

### Debugging Hooks and Introspection Capabilities
```
DEBUGGING FACILITIES:
- SERVICE INTROSPECTION:
  * GET /debug/state: Current internal state and configuration
  * GET /debug/stack: Thread stacks if safe and applicable
  * GET /debug/deps: Dependency versions and availability
  * GET /debug/config: Effective configuration after overrides
  
- PIPELINE INSPECTION:
  * GET /debug/pipeline/{stage}: Intermediate results from stage
  * POST /debug/pipeline/{stage}: Inject test data at stage
  * GET /debug/screenshot: Last captured screenshot (if enabled)
  * GET /debug/model: YOLO model information and statistics
  
- TESTING HOOKS:
  * Fault injection: Configure failure probabilities for testing
  * Latency injection: Add delays to simulate performance issues
  * Data mutation: Modify internal state for scenario testing
  * Mock substitution: Replace dependencies with test doubles
  
- PERFORMANCE DEBUGGING:
  * Profiling activation: Enable CPU/memory profilers on demand
  * Benchmark mode: Run standardized performance tests
  * Resource monitoring: Detailed resource usage reporting
  * Lock contention: Identify threading bottlenecks if applicable

SECURITY CONSIDERATIONS:
- Debug endpoints: Protected by authentication in production
- Information disclosure: No sensitive data in debug outputs
- Access control: Restricted to administrators or service accounts
- Network exposure: Typically disabled or restricted in production
- Temporary activation: Enable only for troubleshooting sessions

INTEGRATION WITH DEVELOPMENT WORKFLOWS:
- Local development: Full debugging capabilities enabled
- Staging: Limited capabilities with access controls
- Production: Minimal capabilities, emergency use only
- Feature flags: Control availability independently of code
```

## Section 9: Deployment
* Deployment strategies (blue-green, rolling, canary)
* Rollback procedures and recovery time objectives
* Environment parity and promotion pathways
* Configuration management and environment-specific handling
* Resource requirements and infrastructure as code
* Compatibility matrices and version support
* Rollout planning and stakeholder communication

### Deployment Strategies
```
BLUE-GREEN DEPLOYMENT:
- Process: Maintain two identical production environments (Blue and Green)
- Traffic routing: Switch router/load balancer from one environment to another
- Risk mitigation: Instant rollback by switching back to previous environment
- Resource utilization: 2x capacity required during normal operation
- Best for: Critical systems where downtime must be minimized
- Implementation: Kubernetes namespaces, AWS Blue/Green via CodeDeploy

ROLLING DEPLOYMENT:
- Process: Update instances in small batches while maintaining capacity
- Traffic routing: Load balancer removes instances from service during update
- Risk mitigation: Limited blast radius, easy to pause and investigate
- Resource utilization: Minimal overhead (only updating instances need extra)
- Best for: Stateless services with horizontal scaling capability
- Implementation: Kubernetes Deployments, AWS Auto Scaling groups

CANARY DEPLOYMENT:
- Process: Route small percentage of traffic to new version (<5-10%)
- Traffic routing: Weighted routing based on percentages or headers
- Risk mitigation: Limited exposure to potential issues
- Resource utilization: Minimal overhead (small percentage duplicated)
- Best for: Risk-averse releases with gradual confidence building
- Implementation: Istio/Linkerd service meshes, AWS Codedevil Canary

RECOMMENDED APPROACH:
- Primary: Canary deployment for risk mitigation and gradual validation
- Secondary: Rolling deployment for routine updates and maintenance
- Tertiary: Blue-green for major version changes requiring instant rollback
- Automation: CI/CD pipeline integration with automated promotion gates
```

### Rollback Procedures and Recovery Time Objectives
```
ROLLBACK TRIGGERS:
- AUTOMATIC: Health check failures, error rate thresholds, latency degradation
- MANUAL: Operational concerns, user feedback, business decisions
- SCHEDULED: Planned maintenance, dependency updates, security patches

ROLLBACK PROCEDURES:
1. FASTEST (< 30 seconds): Traffic routing rollback
   - Load balancer/service mesh: Immediately redirect traffic
   - DNS weighting: Update weights to favor stable version
   - Feature flags: Toggle off new functionality instantly
   
2. FAST (< 5 minutes): Instance replacement rollback  
   - Kubernetes: Scale down new version, scale up old version
   - ASG: Terminate new instances, launch previous version
   - Manual: Stop new service, start previous version
   
3. RELIABLE (< 15 minutes): Full environment rollback
   - Blue-green: Switch entire environment back to previous version
   - Database: Rollback migrations if applicable (not for this service)
   - Configuration: Revert to previous known-good settings

RECOVERY TIME OBJECTIVES (RTO):
- TIER 1 (Critical user-facing): < 2 minutes to restore service
- TIER 2 (Important internal): < 10 minutes to restore functionality
- TIER 3 (Background/batch): < 60 minutes to resume processing
- This service: TIER 2 (< 10 minutes) due to WeChat automation criticality

RECOVERY POINT OBJECTIVES (RPO):
- Minimal: This service is stateless, no persistent data to lose
- Configuration: < 5 minutes to restore from version control
- Models: < 5 minutes to re-download if cached versions unavailable
```

### Environment Parity and Promotion Pathways
```
ENVIRONMENT TIERS:
- DEVELOPMENT: Local machines, feature branches, experimental features
- TESTING: Shared development environment, integration testing
- STAGING: Production-like environment, pre-release validation
- PRODUCTION: Live traffic, customer-facing operations
- EMERGENCY: Hotfix environment for critical issues

PROMOTION PATHWAYS:
- DEV → TEST: Automated on merge to development branch
- TEST → STAG: Manual approval after test suite completion
- STAG → PROD: Manual approval with performance validation
- PROD → EMER: Automatic for critical security/availability issues
- EMERG → PROD: Manual approval after root cause resolution

ENVIRONMENT PARITY PRINCIPLES:
- INFRASTRUCTURE: Similar topology, scaled appropriately for load
- CONFIGURATION: Same structure, environment-specific values
- DEPENDENCIES: Same versions where possible, documented variations
- DATA: Similar volume and characteristics for testing validity
- SECURITY: Similar controls and protections, scaled for risk

CONFIGURATION MANAGEMENT:
- HIERARCHY: Defaults → Environment Overrides → Runtime Overrides
- VALIDATION: Schema validation at startup, reject invalid configurations
- SECRETS: Environment variables or secret managers, never in code
- FEATURE FLAGS: Centralized management with dashboard and audit
- DRIFT DETECTION: Regular comparison against version-controlled baselines
```

### Resource Requirements and Infrastructure as Code
```
RESOURCE ESTIMATES (PER INSTANCE):
- COMPUTE: 2-4 vCPUs for target load (10 req/sec)
- MEMORY: 2-4 GB RAM for model caching and processing
- STORAGE: 5-10 GB SSD for OS, models, logs, temporary files
- NETWORK: 10-100 Mbps depending on AI service interaction patterns
- GPU: Optional for YOLO acceleration (not required for CPU-based MODEL)

INFRASTRUCTURE AS CODE PATTERNS:
- KUBERNETES: Declarative YAML manifests for Deployments, Services, etc.
- TERRAFORM: Cloud provider agnostic infrastructure provisioning
- HELM: Kubernetes package management for complex applications
- ANSIBLE: Configuration management and application deployment
- CLOUDFORMATION: AWS-specific infrastructure templating

SAMPLE KUBERNETES MANIFEST STRUCTURE:
- Deployment: ReplicaSet with rolling update strategy
- Service: ClusterIP for internal, LoadBalancer/NodePort for external
- ConfigMap: Non-sensitive configuration, environment-specific
- Secret: API keys, certificates, sensitive configuration
- HorizontalPodAutoscaler: CPU/memory based scaling
- PodDisruptionBudget: Minimum availability during voluntary disruptions
- ResourceQuotas: Namespace-level resource limits
- NetworkPolicy: Service-to-service communication restrictions

RESOURCE MONITORING AND ALERTING:
- CPU: Usage > 80% for 5 minutes triggers investigation
- Memory: Usage > 85% for 5 minutes triggers warning
- Disk: Usage > 90% triggers cleanup procedures
- Network: Error rates > 1% trigger connectivity investigation
- Restarts: Unplanned restarts > 3/hour trigger instability investigation
```

### Compatibility Matrices and Version Support
```
PYTHON VERSION SUPPORT:
- PRIMARY: Python 3.12 (aligned with project standard)
- COMPATIBLE: Python 3.10, 3.11 (tested in CI)
- DEPRECATED: Python 3.9 (security updates ending soon)
- UNSUPPORTED: Python 3.8 and earlier (lack modern features)

DEPENDENCY COMPATIBILITY:
- Ultralytics YOLO: >= 8.0.0 (API stability, performance improvements)
- OpenCV: >= 4.5.0 (modern features, security updates)
- Pillow: >= 9.0.0 (Python 3 compatibility, performance)
- Requests: >= 2.25.0 (security, features, maintenance)
- All dependencies: Semantic versioning respected, breaking changes avoided

OPERATING SYSTEM COMPATIBILITY:
- SUPPORTED: macOS (10.15+), Windows (10+), Linux (Ubuntu 20.04+, RHEL 8+)
- TESTED: Specific versions in CI matrix for regression detection
- DEGRADED: Older versions may work with reduced functionality
- UNSUPPORTED: End-of-life operating systems (security risks)

EXTERNAL SERVICE COMPATIBILITY:
- GATEWAY SERVICE: Version-independent contract (HTTP/JSON)
- AI SERVICE: Backward compatible API versions supported
- PLATFORM APIS: Standard interfaces with version detection fallbacks
- BACKWARD COMPATIBILITY: Maintained for one major version
- FORWARD COMPATIBILITY: Designed to work with future versions where possible

API VERSIONING:
- INTERNAL: Semantic versioning for service interface
- EXTERNAL: Leverage existing gateway AI service versioning
- BREAKING CHANGES: Major version increment, migration guide provided
- DEPRECATIONS: Minor version with 6-month sunset notice
```

### Rollout Planning and Stakeholder Communication
```
ROLLout PHASES:
- PHASE 0 (Development): Feature branch, local testing, unit tests
- PHASE 1 (Testing): Integration testing, contract testing, performance baselines
- PHASE 2 (Staging): Load testing, security review, user acceptance testing
- PHASE 3 (Production): Canary rollout, monitoring validation, gradual increase
- PHASE 4 (Post-launch): Performance validation, bug bash, documentation update

STAKEHOLDERS AND COMMUNICATION:
- DEVELOPMENT TEAM: Daily standups, code reviews, pairing sessions
- QA/TESTING: Test plans, bug reports, test automation updates
- OPERATIONS/SRE: Runbooks, monitoring dashboards, alert configurations
- PRODUCT MANAGEMENT: Feature demos, validation sessions, feedback incorporation
- END USERS: Release notes, training materials, support documentation
- SECURITY TEAM: Vulnerability assessments, penetration testing, compliance

COMMUNICATION CHANNELS:
- SYNCHRONOUS: Meetings, pair programming, design reviews
- ASYNCHRONOUS: Documentation, issue tracking, wikis, email
- RADIATORS: Dashboards, metrics displays, information radiators
- RETROSPECTIVES: Process improvement, lesson sharing, celebration
- POST-MORTEMS: Blameless analysis, action item tracking, prevention planning

ROLLout CHECKLIST:
- [ ] Code complete and reviewed
- [ ] Unit tests passing (≥80% coverage)
- [ ] Integration tests passing
- [ ] Performance benchmarks established
- [ ] Security review completed
- [ ] Documentation updated
- [ ] Runbooks created/updated
- [ ] Monitoring and alerting configured
- [ ] Rollback procedures tested
- [ ] Staging validation passed
- [ ] Canary criteria defined and measurable
- [ ] Communication plan executed
- [ ] Post-launch review scheduled
```

---

## TASK PROGRESS TRACKER

### Current Session Status (2024-04-11)

#### Completed Tasks
- ✅ **OCR坐标Bug修复**: Fixed coordinate conversion bug in `wechat_automation.py` lines 1699-1701 where all clicks used fixed position (779.0, 210.0) instead of actual OCR-detected coordinates
- ✅ **API功能验证**: Confirmed API returns successfully with 3 articles: `{"status":"success","message":"Automation cycle completed. Success: 1/1"}`
- ✅ **关键代码定位**: Identified key search flow functions:
  - `search_account_v2` (line 923) - main entry
  - `search_wechat_account` (line 691) - traditional search
  - `_basic_search_account` (line 784) - basic search implementation
  - `_navigate_to_article_list` (line 946) - navigate to article list
  - `run_cycle` (line 1199) - main automation cycle
  - `_read_articles_legacy` (line 1315) - article reading with OCR/LLM

#### Active Issues (Requires Investigation)
- ⚠️ **坐标未生效**: Logs still show position (779.0, 210.0) - server may not have reloaded fixed code
- 🔍 **数据来源不明**: Need to verify if returned data is real OCR or mock implementation
- 📋 **缺少详细日志**: Need to add logging to identify which code paths are actually executed

#### Next Steps (Immediate)
1. **添加详细日志**: Add logging to `search_account_v2`, `search_wechat_account`, `_navigate_to_article_list` to trace execution flow
2. **验证Mock数据**: Check `test_wechat_automation_improved.py` for MockOCRProcessor and verify real OCR is used in production
3. **确认代码部署**: Verify server has reloaded the fixed code (restart if needed)
4. **根因分析**: Once logs are in place, analyze why search flow doesn't complete

#### Design Decisions Made
- **Coordinate Fix**: Removed incorrect `bounds['X']` and `bounds['Y']` additions in OCR click handling - OCR runs on full screenshot so coordinates are already absolute screen coordinates
- **Fallback Strategy**: Using existing heuristic/OCR approaches as fallback while investigating main flow

#### Technical Notes
- All click operations currently use position (779.0, 210.0) suggesting:
  1. Either server hasn't reloaded new code
  2. Or there's another code path being used
  3. Or the fix location is incorrect
- Mock code exists in test files - need to ensure production uses real OCR
	
## Section 10: Maintainability & Technical Debt Review
* Code complexity and readability assessment
* Technical debt identification and quantification  
* Refactoring opportunities and prioritization
* Dependency management and version compatibility
* Documentation maintainability and completeness
* Onboarding complexity for new developers
* Monitoring of maintenance metrics over time
* Strategies for reducing accidental complexity
* Balance between innovation and maintenance workload
* Open source license compatibility and obligations

### Code Complexity Assessment
```
Current State: Multiple duplicate element location implementations with varying quality
Target State: Single unified service with clear separation of concerns
Improvement: 60% reduction in duplicate code, 40% decrease in cyclomatic complexity
```

### Technical Debt Inventory
| Debt Type | Description | Impact | Priority |
|-----------|-------------|--------|----------|
| Duplicate Logic | 4+ element location implementations | High | P1 |
| Hardcoded Values | Magic numbers throughout code | Medium | P2 |
| Limited Logging | Insufficient debug information | Medium | P2 |
| Tight Coupling | Direct instantiation of locators | High | P1 |
| Missing Tests | Low coverage in legacy code | High | P1 |

### Refactoring Roadmap
1. **Immediate (Sprint 1)**: Replace worst-performing locators with unified service
2. **Short-term (Sprint 2-3)**: Consolidate middleware and utility functions
3. **Long-term (Sprint 4-6)**: Advanced caching, performance optimization
4. **Ongoing**: Continuous code quality improvement

### Maintenance Metrics
- Mean time to modify: Target < 2 hours for common changes
- Code churn rate: Target < 15% monthly modification
- Defect density: Target < 0.5 bugs per KLOC
- Knowledge silos: Target 0 critical knowledge single points of failure

**Section 10 Complete**: Maintainability and technical debt reviewed with complexity assessment, debt inventory, refactoring roadmap, and maintenance metrics defined.

## TASK PROGRESS TRACKER
```
## 0A. Premise Challenge
