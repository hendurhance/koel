import random
import threading
from typing import List
from app.utils.custom_logger import get_logger
import os

logger = get_logger(__name__)

class UserAgentRotator:
    """
    A class to manage and rotate User-Agent headers for HTTP requests.
    Loads User-Agent strings from a specified text file.
    Implements the Singleton pattern to ensure a single instance.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, user_agents_file: str = None):
        """
        Implementing Singleton pattern to ensure only one instance exists.
        Optionally accepts a path to a User-Agent text file.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UserAgentRotator, cls).__new__(cls)
                    cls._instance._initialize(user_agents_file)
        return cls._instance

    def _initialize(self, user_agents_file: str):
        """
        Initialize the UserAgentRotator by loading User-Agent strings from a text file.
        
        Args:
            user_agents_file (str, optional): Path to the User-Agent text file.
                                              Defaults to 'user_agents.txt' in the same directory.
        """
        if user_agents_file is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir)
            user_agents_file = os.path.join(app_dir, 'user_agents.txt')

        self.user_agents = self._load_user_agents(user_agents_file)
        if not self.user_agents:
            logger.error("User-Agent list is empty. Please provide valid User-Agent strings.")
            raise ValueError("User-Agent list cannot be empty.")

        logger.info(f"Initialized UserAgentRotator with {len(self.user_agents)} User-Agent(s) from '{user_agents_file}'.")

    def _load_user_agents(self, file_path: str) -> List[str]:
        """
        Load User-Agent strings from a text file.
        
        Args:
            file_path (str): Path to the User-Agent text file.
        
        Returns:
            List[str]: A list of User-Agent strings.
        """
        user_agents = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue 
                    user_agents.append(line)
            logger.debug(f"Loaded {len(user_agents)} User-Agent(s) from '{file_path}'.")
        except FileNotFoundError:
            logger.error(f"User-Agent file not found at '{file_path}'.")
            raise
        except Exception as e:
            logger.error(f"Error reading User-Agent file at '{file_path}': {e}")
            raise
        return user_agents

    def get_random_user_agent(self) -> str:
        """
        Returns a random User-Agent string from the pool.
        
        Returns:
            str: A randomized User-Agent string.
        """
        user_agent = random.choice(self.user_agents)
        logger.debug(f"Selected User-Agent: {user_agent}")
        return user_agent

    def add_user_agent(self, user_agent: str):
        """
        Adds a new User-Agent string to the pool.
        
        Args:
            user_agent (str): The User-Agent string to add.
        """
        if user_agent not in self.user_agents:
            self.user_agents.append(user_agent)
            logger.info(f"Added new User-Agent to rotator: {user_agent}")
        else:
            logger.debug(f"User-Agent already exists in rotator: {user_agent}")

    def remove_user_agent(self, user_agent: str):
        """
        Removes a User-Agent string from the pool.
        
        Args:
            user_agent (str): The User-Agent string to remove.
        """
        if user_agent in self.user_agents:
            self.user_agents.remove(user_agent)
            logger.info(f"Removed User-Agent from rotator: {user_agent}")
        else:
            logger.debug(f"User-Agent not found in rotator: {user_agent}")
