from __future__ import annotations

import os

import pytest


@pytest.mark.integration
def test_real_endpoint_smoke_requires_explicit_opt_in() -> None:
    if os.environ.get("RUN_LLM_INTEGRATION") != "1":
        pytest.skip("set RUN_LLM_INTEGRATION=1 to enable live endpoint integration")
    pytest.fail(
        "live endpoint smoke is not implemented in M1; use the loopback fake-server unit tests"
    )
