# Document Processing Tests

This folder contains the test suite for the document classification and domain processing pipeline.

## Test Files

- test_processor_utils.py
  Tests shared JSON parsing and confidence utility functions.

- test_processors.py
  Tests processor routing, extraction validation, and deterministic confidence using mocked LLM responses.

- test_classifier_real_llm.py
  Tests supported, unsupported, and ambiguous document classification using the real LLM.

- test_processors_real_llm.py
  Tests all domain processors using the real LLM.


## Run Fast Tests

Use these during normal development:

py -m pytest tests/document_processing/test_processor_utils.py -v

py -m pytest tests/document_processing/test_processors.py -v

Or run all tests except real-LLM integration tests:

py -m pytest -m "not integration" -v

These tests run quickly and do not call the real LLM.


## Run Real-LLM Tests

Make sure the configured LLM service is running before starting these tests.

Test the document classifier:

py -m pytest tests/document_processing/test_classifier_real_llm.py -v -s

Test all domain processors:

py -m pytest tests/document_processing/test_processors_real_llm.py -v -s

Or run all real-LLM integration tests:

py -m pytest -m integration -v -s

Real-LLM tests may take several minutes.


## When to Run Which Tests

Run the fast tests after any change to document-processing code.

Run the real-LLM classifier tests after changing:

- classifier prompts
- supported document types
- classification thresholds
- classifier logic
- LLM configuration

Run the real-LLM processor tests after changing:

- processor prompts
- extraction schemas
- confidence calculations
- processor logic
- LLM configuration


## Current Validated Results

Milestone 5 was validated with:

Utility tests              16/16 passed
Mocked processor tests     26/26 passed
Real-LLM classifier tests  11/11 passed
Real-LLM processor tests    8/8 passed

Total                      61/61 passed


The real-LLM tests are regression tests and should remain in the repository.

## Milestone 6.5 validation

- Deterministic M6/M6.5 tests: 64/64 passed

Run the real-LLM M6.5 integration test with:

```text
py -m pytest tests/document_processing_tests/test_milestone6_real_llm.py -v -s
```

This test validates the real performance-evidence orchestration end to end: DocumentService upload metadata and expected-type verification, independent real-LLM classification, persisted classification, real PerformanceProcessor extraction, persisted ProcessingResult, ENTITY_EVIDENCE routing, one ATTACH_EVIDENCE review draft, PENDING_REVIEW lifecycle, approval synchronization, exact Goal evidence attachment, lightweight provenance, and idempotent reapplication without duplicate Goal evidence.
