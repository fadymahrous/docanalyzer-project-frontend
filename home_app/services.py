from config.configuration import ConfigurationCenter
config_center = ConfigurationCenter()
from helper.logger_setup import setup_logger
from typing import List,Dict
import re
from django.forms.models import model_to_dict
from .models import UploadedFile



logger = setup_logger('home_app')
extention_compiler=re.compile(r".*\.([A-z]*)")

class Local_Supporter:

    @staticmethod
    def file_size_exceeded(uploaded_file,size_limit)->bool:
            if uploaded_file.size / 1024 > int(size_limit):
                logger.error(f"File is not accepted file size is {uploaded_file.size} and it exceeded tne limit of {size_limit}")
                return True
            return False
    
    @staticmethod
    def allowed_file_extention(uploaded_file_name:str,allowd_extentions:List)->bool:
        captured=extention_compiler.search(uploaded_file_name)
        if captured[1] in allowd_extentions:
             return True
        return False
         
    @staticmethod
    def clean_dict_for_sqs(message_to_clean:UploadedFile)->Dict:
        converted_to_dict=model_to_dict(message_to_clean)
        converted_to_dict.pop("filelocation",None)
        return converted_to_dict
         
         
        

