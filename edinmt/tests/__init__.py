from edinmt import setup_logger
from edinmt.configs.config import TestConfig

#Make a separate logger for all of our tests 
TEST_LOGGER = setup_logger(
    name="edinmt.tests", 
    level=TestConfig.LOG_LEVEL, 
    to_stdout=True
)