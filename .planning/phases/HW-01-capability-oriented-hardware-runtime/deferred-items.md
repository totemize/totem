# Deferred Items

- `tests/unit/test_mock_transports.py::test_display_manager_uses_explicit_mock_transport` still expects the Plan 27 client-only `DisplayManager` to construct a concrete mock driver without an injected canonical bus. This predates Plan 01-28 and is outside the registry/contract facade scope; update it with the next display-wrapper compatibility work.
- `tests/unit/test_radio_primitives.py::test_mock_radios_report_real_shape_and_transition_idempotently` still invokes a mock-backed `NetworkManager` without a canonical client and expects local event ownership. This predates Plan 01-28 and belongs with the upcoming radio-wrapper compatibility migration.
