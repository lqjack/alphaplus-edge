# TEST PLAN

## Current Investigation Focus (2024-04-12)

### Latest Findings

| Finding | Status | Evidence |
|---------|--------|----------|
| Coordinate bug fixed | ✅ DONE | wechat_automation.py lines 1699-1701 - coordinate conversion corrected |
| API returns success | ✅ DONE | `{"status":"success","message":"Automation cycle completed. Success: 1/1"}` |
| Fixed coordinates (779.0, 210.0) still appearing | 🔲 INVESTIGATING | Logs show same coordinates used - server may not have reloaded |
| Key functions identified | ✅ DONE | search_account_v2 (923), search_wechat_account (691), _navigate_to_article_list (946), run_cycle (1199) |

### Root Cause Hypotheses

1. **Server Not Reloaded**: Fix applied but server still running old code
2. **Mock Data Leak**: MockOCRProcessor from test file being used in production
3. **Fallback Logic Issue**: Code falling back to hardcoded coordinates on any error
4. **Wrong Import**: Production importing from test file accidentally

### Immediate Debugging Priorities

| Priority | Issue | Status | Action Required |
|----------|-------|--------|----------------|
| P0 | All clicks use fixed position (779.0, 210.0) | 🔍 Investigating | Add logging to trace actual code path |
| P0 | Verify data source (mock vs real OCR) | 🔍 Investigating | Check MockOCRProcessor usage |
| P1 | Server may not have reloaded code | 🔍 Investigating | Verify deployment/restart |
| P1 | Search flow doesn't complete | 🔍 Investigating | Add detailed execution logging |

### Key Functions to Trace

```python
# Add logging to these functions to trace execution:
search_account_v2          # Line 923 - Main entry point
search_wechat_account    # Line 691 - Traditional search
_basic_search_account    # Line 784 - Basic search
_navigate_to_article_list # Line 946 - Article list navigation
run_cycle                # Line 1199 - Main automation cycle
_read_articles_legacy   # Line 1315 - OCR-based reading
```

### Mock vs Real Implementation Check

**Files to audit:**
- `test_wechat_automation_improved.py` - Contains MockOCRProcessor
- `wechat_automation.py` - Main production code
- `mcp_core/ocr_processor.py` - Core OCR implementation

**Audit checklist:**
- [ ] Verify production code doesn't import/use MockOCRProcessor
- [ ] Confirm OCR is called with real screenshots
- [ ] Check if any mock data is returned in production flow
- [ ] Ensure test mocks don't leak into production

---

## Unified Element Locator Service Test Plan

### 1. Test Strategy Overview

This test plan outlines the approach for validating the Unified Element Locator Service implementation, ensuring it meets requirements for accuracy, reliability, and performance.

### 2. Test Levels

#### 2.1 Unit Tests
- **Target**: Individual methods and classes in isolation
- **Framework**: pytest with unittest.mock
- **Coverage Goal**: 90% line coverage, 80% branch coverage
- **Focus Areas**:
  - Input validation and error handling
  - Pipeline stage isolation (YOLO, AI service, result parsing)
  - Fallback strategy selection and execution
  - Dependency injection and mocking

#### 2.2 Integration Tests
- **Target**: Service interactions with real/contracted dependencies
- **Framework**: pytest with service mocking
- **Coverage Goal**: 80% of integration paths
- **Focus Areas**:
  - Full pipeline execution with mocked external dependencies
  - Fallback chaining behavior under various failure scenarios
  - Concurrent access and thread safety
  - Resource cleanup and leak prevention

#### 2.3 End-to-End Tests
- **Target**: Critical user journeys in realistic environments
- **Framework**: pytest with actual WeChat application
- **Coverage Goal**: Core user workflows
- **Focus Areas**:
  - Article fetching workflow completion
  - Search bar location and interaction
  - Article list navigation
  - Dynamic UI adaptation to changes

### 3. Test Environment Requirements

#### 3.1 Hardware
- Minimum: 2 CPU cores, 4GB RAM
- Recommended: 4 CPU cores, 8GB RAM
- Storage: 10GB available space

#### 3.2 Software
- Python 3.10+ (3.12 preferred)
- Required dependencies: See requirements.txt
- Optional: GPU for YOLO acceleration (not required)

#### 3.3 Test Data
- Sample WeChat screenshots for various UI states
- Predefined element locations with expected coordinates
- Mock AI service responses for testing
- Corrupted/invalid test data for error condition testing

### 4. Test Cases by Category

#### 4.1 Input Validation Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| NULL Input | Pass null/None as target description | ValidationError |
| Empty String | Pass empty string as target | ValidationError |
| Invalid Types | Pass non-string types | ValidationError |
| Whitespace Only | Pass string with only spaces | ValidationError (after trim) |
| Valid Input | Pass legitimate target description | Proceed to processing |

#### 4.2 Screenshot Capture Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Successful Capture | Normal screenshot operation | Valid image returned |
| Permission Denied | Simulate lack of screen capture permissions | ScreenshotCaptureError with guidance |
| Display Not Available | Simulate no active display | ScreenshotCaptureError |
| Low Memory | Simulate constrained memory environment | Downsampled or region-specific capture |
| Platform Fallback | Primary method fails, fallback succeeds | Valid image from alternative method |

#### 4.3 YOLO Pre-screening Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Model Loaded Successfully | Normal YOLO initialization | Model ready for inference |
| Model Loading Failure | Corrupt/missing model file | Fallback to OCR/heuristic path |
| No Objects Detected | YOLO returns empty detections | Empty candidate list |
| Multiple Objects Detected | YOLO returns multiple bounding boxes | List of candidate regions |
| Invalid Bounding Boxes | YOLO returns malformed coordinates | Filtered valid candidates only |

#### 4.4 AI Service Communication Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `computer_use_grounding` Success | Valid single-target grounding payload | Parsed point/bbox/recommended_action result |
| `legacy_visual_fallback` Success | Valid JSON from compatibility screenshot-analysis task | Parsed ElementLocation or list result |
| Service Unavailable | HTTP 503 or timeout | FallbackTriggered to OCR/heuristic |
| Invalid Response Format | Non-JSON or malformed response | ProcessingError with fallback |
| Network Error | Connection refused/dropped | FallbackTriggered with retry logic |
| Rate Limiting | HTTP 429 response | Exponential backoff then fallback |

#### 4.5 Result Parsing Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Valid Coordinates | AI returns proper JSON with coordinates | ElementLocation with valid bounds |
| Out-of-Bounds Coordinates | Coordinates outside screen dimensions | Clamped to valid range or rejected |
| Low Confidence | AI response below threshold | LowConfidenceWarning or fallback |
| Missing Fields | Incomplete JSON response | ProcessingError with fallback |
| Non-Numeric Values | String coordinates in JSON | ProcessingError with fallback |

#### 4.6 Fallback Strategy Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Grounding Success | `computer_use_grounding` succeeds for single-target task | Primary result returned |
| YOLO+Legacy Visual Success | YOLO finds candidates and `legacy_visual_fallback` selects one | Primary result returned |
| YOLO Success, Compatibility Visual Fail | YOLO finds candidates, compatibility visual task fails | Fallback to OCR/heuristic |
| YOLO Fail, OCR Success | No YOLO candidates, OCR works | OCR/heuristic result |
| All Strategies Fail | YOLO, AI, OCR, heuristic all fail | Empty result list |
| Confidence-Based Fallback | High confidence threshold not met | Progressive fallback attempts |

#### 4.7 Performance Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Latency Baseline | Single element location request | Meets performance benchmarks |
| Throughput Test | Sustained load (10 req/sec) | Stable performance, queuing behavior |
| Memory Usage | Continuous operation | No memory leaks, stable footprint |
| Resource Cleanup | After error conditions | Proper resource release |

#### 4.8 End-to-End Workflow Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Article Fetching | Locate and extract article titles | Successful article retrieval |
| Search Interaction | Locate search bar, input text | Correct search results displayed |
| Navigation | Locate and click UI elements | Proper screen transitions |
| UI Change Adaptation | Handle updated WeChat interface | Continued successful operation |

### 5. Test Data Management

#### 5.1 Test Data Factories
- **ScreenshotFactory**: Generates test images with known element placements
- **CoordinateFactory**: Creates valid/invalid coordinate combinations for testing
- **ResponseFactory**: Generates AI service responses for various scenarios
- **ErrorFactory**: Produces exception instances for error condition testing

#### 5.2 Golden Master Data
- **Baseline Screenshots**: Reference images for visual validation
- **Expected Results**: Pre-calculated element locations for known inputs
- **Performance Benchmarks**: Baseline measurements for regression detection

#### 5.3 Data Isolation Strategies
- Temporary directories for each test session
- Unique file names to prevent collisions
- Database transactions rolled back after tests
- Mock objects reset between test cases

### 6. Test Execution Strategy

#### 6.1 Local Development
- Run unit tests on file save/commit
- Execute relevant test suites before feature branches
- Debug failing tests with detailed logging

#### 6.2 Continuous Integration
- Execute full test suite on every pull request
- Run performance benchmarks on schedule
- Deploy to staging environment after successful tests
- Gate production deployment on test success

#### 6.3 Release Testing
- Execute end-to-end tests in staging environment
- Perform smoke tests in production-like environment
- Validate rollback procedures in isolated environment
- Conduct performance validation against baselines

### 7. Test Metrics and Reporting

#### 7.1 Coverage Metrics
- Line coverage: Target ≥90%
- Branch coverage: Target ≥80%
- Complexity coverage: Target ≥85% (for complex methods)
- Public interface coverage: Target 100%

#### 7.2 Quality Metrics
- Test failure rate: Target 0% for stable branches
- Mean time to recovery: Target <30 minutes for test failures
- Test execution time: Target <10 minutes for full suite
- Flaky test rate: Target <1% after investigation

#### 7.3 Reporting
- JUnit XML output for CI integration
- HTML coverage reports for visual inspection
- Test trend analysis over time
- Failure categorization and tracking

### 8. Risk-Based Testing Priorities

#### High Priority
1. Input validation and error handling
2. Fallback chaining under failure conditions
3. Resource cleanup and leak prevention
4. End-to-end workflow completion
5. Performance under load conditions

#### Medium Priority
1. Edge case handling in coordinate validation
2. Concurrent access and thread safety
3. Configuration validation and loading
4. Logging and metrics accuracy
5. Platform-specific fallback mechanisms

#### Low Priority
1. Extreme boundary value testing
2. Exotic error condition combinations
3. Performance optimization validation
4. Documentation accuracy verification
5. Localization and internationalization (deferred feature)

### 11. Current Debugging Test Cases

#### 11.1 Coordinate Verification Tests
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Click Position Logging | Log all click positions to verify actual coordinates used | Unique coordinates per click action |
| OCR Bounds Accuracy | Verify OCR returns correct bounds for elements | Bounds match visual position |
| Coordinate Transformation | Confirm coordinates are in screen space | No offset/transform errors |

#### 11.2 Execution Flow Tracing
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Function Entry Logging | Log entry to search_account_v2 | Trace execution path |
| Search Bar Location | Verify search bar detection method | YOLO/OCR/Heuristic used |
| Result Click | Verify correct account is clicked | Correct coordinates used |
| Article List Navigation | Verify "图文消息" click | Unique coordinates |

#### 11.3 Mock vs Real Data Verification
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| OCR Processor Usage | Verify real OCR is called | OCR processes screenshots |
| Mock Isolation | Ensure mocks don't leak to production | No MockOCRProcessor in prod |
| Data Source Check | Verify returned data is from OCR | Content matches screenshot |

#### 11.4 Server Deployment Verification
| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Code Reload | Verify server has latest code | New coordinates in logs |
| Restart Test | Test after server restart | Fresh code execution |

### 9. Acceptance Criteria

#### Functional Requirements
- [ ] Successfully locates WeChat UI elements with ≥85% accuracy
- [ ] Implements YOLO → multimodal → result parsing pipeline
- [ ] Provides graceful degradation to OCR/heuristic methods
- [ ] Returns properly formatted ElementLocation results
- [ ] Handles error conditions without crashing

#### Performance Requirements
- [ ] Element location latency ≤3000ms for 95% of requests
- [ ] Memory usage ≤4GB under normal load
- [ ] No memory leaks detected over extended operation
- [ ] Fallback frequency ≤15% with effective chaining

#### Reliability Requirements
- [ ] Service availability ≥99% under normal conditions
- [ ] Automatic recovery from transient failures
- [ ] Proper error logging and metric collection
- [ ] Resource cleanup after error conditions

#### Operational Requirements
- [ ] Proper logging at appropriate levels (debug/info/warn/error)
- [ ] Configuration via environment variables or files
- [ ] Health check endpoints for liveness/readiness
- [ ] Proper shutdown and cleanup procedures

### 10. Test Execution Schedule

#### Phase 1: Unit Testing (Days 1-2)
- Implement and validate all unit test cases
- Achieve target coverage metrics
- Fix identified defects

#### Phase 2: Integration Testing (Days 3-4)
- Execute integration test scenarios
- Validate service contracts and interactions
- Address integration defects

#### Phase 3: End-to-End Testing (Days 5-6)
- Execute critical user journey tests
- Validate performance and reliability
- Address workflow defects

#### Phase 4: Release Preparation (Day 7)
- Execute full test suite
- Generate final test reports
- Obtain stakeholder sign-off for release

### 11. Contingency Plans

#### Test Environment Issues
- Use containerized environments for consistency
- Maintain backup of known-good test data
- Have alternative testing approaches ready

#### Dependency Availability Issues
- Implement comprehensive mocking strategies
- Use contract tests when real dependencies unavailable
- Schedule testing around known dependency maintenance

#### Resource Constraints
- Prioritize tests by risk and value
- Use sampling approaches for large test sets
- Leverage cloud resources for scalable testing when needed

This test plan provides a comprehensive approach to validating the Unified Element Locator Service implementation, ensuring it meets all functional, performance, and reliability requirements while minimizing risk through structured testing approaches.
