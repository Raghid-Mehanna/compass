"""
Dagster job definitions for Compass.

`compass_full_pipeline` materializes the entire DAG end-to-end:
the three landing assets in parallel, then the processed asset once
all three succeed.

`compass_landing_only` is a smaller job that just runs the scrapers
(useful when you only want to refresh raw data and re-run the
transformer separately later).
"""

from dagster import AssetSelection, define_asset_job


compass_full_pipeline = define_asset_job(
    name="compass_full_pipeline",
    selection=AssetSelection.all(),
    description="Run all three spiders, then the BeautifulSoup transformer.",
)

compass_landing_only = define_asset_job(
    name="compass_landing_only",
    selection=AssetSelection.groups("landing"),
    description="Refresh landing-zone data without re-running the transformer.",
)
