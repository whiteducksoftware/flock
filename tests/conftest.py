import os
import pytest
import dotenv


def pytest_configure(config):
    """
    Load environment variables from .env file if it exists.
    This ensures any environment variables defined in .env are available for tests.
    """
    # Load from .env file if it exists
    dotenv.load_dotenv()


def pytest_addoption(parser):
    """Add command-line options for pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require Azure AI Search credentials",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly requested."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def azure_credentials():
    """
    Fixture to provide Azure Search credentials.
    
    This will check for the required environment variables and
    skip tests that need them if they're not set.
    """
    required_vars = ["AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        pytest.skip(f"Azure Search credentials missing: {', '.join(missing)}")
    
    return {
        "endpoint": os.environ.get("AZURE_SEARCH_ENDPOINT"),
        "api_key": os.environ.get("AZURE_SEARCH_API_KEY"),
        "index_name": os.environ.get("AZURE_SEARCH_INDEX_NAME")
    } 