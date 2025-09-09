from configparser import ConfigParser
from pathlib import Path
from helper.logger_setup import setup_logger
from dotenv import load_dotenv
from os import getenv

DEFAULT_CONFIG_PATH = 'config/config.ini'

#Load environmental variables
load_dotenv()

class ConfigurationCenter:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.logger = setup_logger('configuration_reader')
        self.config_path = Path(config_path)

        if not self.config_path.is_file():
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise RuntimeError("Configuration file does not exist.")

        self.config = ConfigParser()
        self.config.read(self.config_path)
        self.logger.info(f"Configuration loaded from: {self.config_path}")

    def _get_section(self, section: str) -> ConfigParser | None:
        if not section:
            self.logger.error("Section name must be a non-empty string.")
            return None
        if section not in self.config:
            self.logger.error(
                f"Section '{section}' not found in configuration file. "
                f"Available sections: {self.config.sections()}"
            )
            return None
        return self.config[section]

    def get_parameter(self, section: str, parameter: str) -> str | None:
        if not parameter:
            self.logger.error("Parameter name must be a non-empty string.")
            return None

        section_data = self._get_section(section)
        if section_data is None:
            return None

        if parameter not in section_data:
            self.logger.error(
                f"Parameter '{parameter}' not found under section '{section}'. "
                f"Available keys: {list(section_data.keys())}"
            )
            return None

        value = section_data.get(parameter)
        return value

    def get_environmental(self,varibale_name):
        retrived_variable=getenv(varibale_name)
        if retrived_variable is None:
            self.logger.error(f'The user tries to retrive environmental variable name:{varibale_name} but not exist')
        return retrived_variable

        

