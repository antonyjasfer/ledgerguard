"""Configuration and fixtures for opt-in AWS integration tests.

ALL tests in this package are skipped by default to prevent accidental AWS resource
consumption or cost incurrence unless LEDGERGUARD_RUN_AWS_INTEGRATION=true is explicitly set.
"""

import os
import pytest


def pytest_collection_modifyitems(config, items):
    run_aws = os.getenv("LEDGERGUARD_RUN_AWS_INTEGRATION", "false").lower() in ("true", "1", "yes")
    if not run_aws:
        skip_marker = pytest.mark.skip(
            reason="AWS integration tests skipped by default. Set LEDGERGUARD_RUN_AWS_INTEGRATION=true to run."
        )
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_marker)
