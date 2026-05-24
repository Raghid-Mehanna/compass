"""
Top-level Dagster Definitions for Compass.

Discovered by `dagster dev` via the workspace.yaml at the project root.
"""

from dagster import Definitions

from .assets import hn_landing, processed_jobs, waas_landing, wwr_landing
from .jobs import compass_full_pipeline, compass_landing_only


defs = Definitions(
    assets=[hn_landing, wwr_landing, waas_landing, processed_jobs],
    jobs=[compass_full_pipeline, compass_landing_only],
)
