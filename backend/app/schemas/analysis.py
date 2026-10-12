"""Analysis summary schema exposed to clients (subset of ``RepoAnalysis``)."""

from app.schemas.common import CamelModel


class AnalysisSummary(CamelModel):
    """Headline static-analysis facts shown as chips on the roast page."""

    languages: dict[str, int]
    file_count: int
    has_readme: bool
    has_tests: bool
    has_dependency_file: bool
    has_env_file_committed: bool
    secrets_found_count: int
    commit_count: int
