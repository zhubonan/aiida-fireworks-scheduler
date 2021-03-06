"""pytest fixtures for simplified testing."""

from pathlib import Path

import pytest

from fireworks.core.launchpad import LaunchPad
from fireworks import fw_config

# pylint: disable=invalid-name, redefined-outer-name

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']


@pytest.fixture(scope='function', autouse=True)
def clear_database_auto(clear_database):  # pylint: disable=unused-argument
    """Automatically clear database in between tests."""
    pass


MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR / 'test_data'
TESTDB_NAME = "aiida-fireworks-scheduler-test"


@pytest.fixture(scope='session')
def launchpad():
    """Get a launchpad"""
    # Manually add the package to be included
    fw_config.USER_PACKAGES = [
        'fireworks.user_objects', 'fireworks.utilities.tests', 'fw_tutorials',
        'fireworks.features'
    ]
    lpd = LaunchPad(name=TESTDB_NAME, strm_lvl='ERROR')
    lpd.reset(password=None, require_password=False)
    yield lpd
    lpd.connection.drop_database(TESTDB_NAME)


@pytest.fixture
def clean_launchpad(launchpad):
    """Get a launchpad in clean state"""
    launchpad.reset(password=None, require_password=False)
    return launchpad
