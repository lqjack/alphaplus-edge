# NOT IN SCOPE

The following items are explicitly excluded from this refactoring effort:

## Excluded Features
1. **Self-healing locators with continuous learning** - While mentioned as delight opportunities and platform potential, the implementation of machine learning models that adapt based on successful interactions is deferred to future work.

2. **Cross-application portability framework** - The abstraction layer that would allow this service to work with applications beyond WeChat is not implemented in this refactor.

3. **Visual regression testing capabilities** - The AI-powered diff analysis for detecting UI changes is excluded.

4. **Multi-language document processing pipeline** - Extension beyond Chinese/English OCR support is deferred.

5. **Accessibility testing tool features** - Automated UI accessibility compliance checking and related features are not included.

6. **Advanced caching strategies** - While basic caching is mentioned, sophisticated predictive caching based on user behavior patterns is deferred.

7. **Enterprise-scale horizontal scaling** - The service is designed for single-instance operation; clustering and load balancing implementations are excluded.

8. **Custom model training capabilities** - The ability to train or fine-tune YOLO models for specific UI elements is not included.

9. **Real-time collaborative debugging** - Shared debugging sessions and remote introspection capabilities are excluded.

10. **Performance prediction and auto-scaling** - Predictive resource allocation based on historical usage patterns is deferred.

## Excluded Technical Debt Items
1. **Legacy locator removal in other modules** - While wechat_automation.py is refactored, similar cleanup in other server modules is outside scope.

2. **Comprehensive API documentation generation** - Auto-generated API docs from docstrings are not implemented.

3. **Advanced telemetry and tracing** - Beyond basic logging and metrics, distributed tracing implementations are excluded.

4. **Chaos engineering integration** - Automated failure injection and resilience testing are not included.

5. **Compliance automation tools** - Automated GDPR/CCPA compliance checking and reporting are excluded.

## Excluded Infrastructure Components
1. **Service mesh integration** - Advanced traffic management and observability features are deferred.

2. **Custom dashboard implementations** - While metrics are mentioned, specific visualization tools are not built.

3. **Automated remediation systems** - Self-healing infrastructure that responds to alerts is excluded.

4. **Blue/Green deployment automation** - While recommended, the actual implementation of blue-green deployment pipelines is excluded.

## Current Debugging Scope Clarification

### In Scope (Current Investigation)
The following are being actively investigated but remain in-scope:

1. **Coordinate Bug Fix**: Fix OCR coordinate conversion bug where all clicks use fixed position (779.0, 210.0)
   - **Status**: Fixed in code (wechat_automation.py lines 1699-1701)
   - **Next**: Verify server deployed with fix

2. **Execution Flow Logging**: Add detailed logging to trace search flow completion
   - **Status**: Pending - need to trace search_account_v2, search_wechat_account, _navigate_to_article_list
   - **Next**: Add logging to key functions

3. **Mock vs Real Verification**: Verify production uses real OCR (not mock data)
   - **Status**: Need to audit MockOCRProcessor leakage
   - **Next**: Check wechat_automation.py imports

4. **Code Deployment**: Verify server reloads fixed code correctly
   - **Status**: Need to verify
   - **Next**: Confirm deployment

### Root Cause Analysis (In Progress)

**Symptom**: All clicks use fixed position (779.0, 210.0)

**Likely Causes**:
1. Coordinate transformation bug (FIXED) - was using wrong coordinates in OCR result
2. Mock data being used in production (NEED VERIFICATION)
3. Server not reloaded with fix (NEED VERIFICATION)
4. Fallback to hardcoded coordinates on any error (NEED INVESTIGATION)

**Key Functions to Audit**:
- `search_account_v2` (line 923)
- `search_wechat_account` (line 691)
- `_navigate_to_article_list` (line 946)
- `run_cycle` (line 1199)

### Explicitly Out of Scope (Current Session)

1. **UnifiedElementLocator Service Implementation** - Full service implementation paused during debugging
2. **New Strategy Pattern Architecture** - Deferred until current bugs are resolved
3. **YOLO Integration** - On hold until basic coordinate issue is fixed
4. **Pipeline Refactoring** - Deferred to future phase

These items represent potential future enhancements that would build upon the foundation established by this refactoring but are not required to achieve the core goal of improving element location accuracy through the YOLO → multimodal → result parsing pipeline.