# Standard library imports
import logging
import base64
import sys
import os
import re
from IPython.display import Image, display
from langchain_core.messages.base import get_msg_title_repr

RESET = "\033[0m"
HEADER_GREEN = "\033[38;5;29m"
DATA_BLUE = "\033[94m"
ORANGE = "\033[38;5;208m"
PURPLE = "\033[38;5;93m"
ERROR_RED = "\033[38;5;196m"

DATA_PATH = './data'
LOG_FILE_NAME = './data/cs_logs.log'

class Utility:
    def __init__(self):

        logging.basicConfig(
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[
                                logging.StreamHandler(),
                                logging.FileHandler(LOG_FILE_NAME)
                            ]
                        )

        self.logger = logging.getLogger(__name__)
        self.data_path = DATA_PATH

        self.temp_path = f'{DATA_PATH}/temp'
        self.db_path = f'{self.temp_path}/customer_support_db.db'

    def get_temp_path(self):
        return self.temp_path
    
    def get_db_path(self):
        return self.db_path

    def get_data_path(self):
        return self.data_path
    
    def log_header(self, function_name: str, ticket_id: str=''):
        print(f'{HEADER_GREEN}')  # set color 
        self.logger.info(f' #### {function_name} ## Ticket: {ticket_id}####')
        #print(f'{RESET}')
    
    def log_data(self, data, ticket_id: str):
        print(f'{DATA_BLUE}')  # reset color
        self.logger.info(f'Ticket: {ticket_id} -- {data}')
        #print(f'{RESET}')

    def log_error(self, error, ticket_id: str):
        print(f'{ERROR_RED}') # reset color
        self.logger.error(f'Ticket: {ticket_id} -- {error}')
        #print(f'{RESET}')

    def log_usage(self, usage: list, ticket_id: str):
        print(f'{DATA_BLUE}')  # reset color

        # Find the maximum length of model names to determine column width
        model_col_width = max(
            len('Model'),
            max(len(item['model_name']) for item in usage) 
        )

        col_width = 15
        # Create the header with dynamic width for Model column
        usage_to_print = (
            f'LLM Usage for Ticket: {ticket_id}\n'
            f'{"Model":<{model_col_width}} {"Input Tokens":<{col_width}} {"Output Tokens":<{col_width}} {"Latency":<{col_width}}'
        )
        
        # Add each usage item with aligned columns
        for item in usage:
            usage_to_print += (
                f"\n{item['model_name']:<{model_col_width}}"
                f"  {item['input_tokens']:<{col_width}}"
                f"{item['output_tokens']:<{col_width}}"
                f"{item['latency']:<{col_width}}"
            )

        self.logger.info(usage_to_print)
        #print(f'{RESET}')


    def log_execution_flow(self, messages, ticket_id: str):
        print(f'{HEADER_GREEN}') # set color 
        self.logger.info(f" =========   Execution Flow for Ticket: {ticket_id}  ========= ")
        for m in messages:
            title = get_msg_title_repr(m.type.title() + " Message")
            if m.name is not None:
                title += f"\nName: {m.name}"

            self.logger.info(f"{title}\n\n{m.content}")
    

    def display_image(self, image_path):
        ''' 
        This functions displays an image
        '''
        if os.path.exists(image_path):
            display(Image(filename=image_path))


    def clean_json_string(self, json_string):
        ''' 
        This functions removes decorators in llm response.
        Remove triple backticks and 'json' identifier
        '''
        pattern = r'```json\n(.*?)```'
        cleaned_string = re.search(pattern, json_string, flags=re.DOTALL)
        
        if cleaned_string:
            return cleaned_string.group(1).strip()
        return json_string.strip()


    def get_image_format(self, image_path):
        '''
        This function identifies image format by its extension
        '''
        file_type = image_path.split('.')[-1]
        file_type = file_type.lower()
        if file_type == 'jpg':
            file_type = 'jpeg'

        return file_type


    def add_image_content(self, image_path: str, ticket_id: str):
        '''
        This function reads image content and adds image data to the payload
        '''
        
        self.log_data(data=f'image path ===> {image_path}', ticket_id=ticket_id)

        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
            base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
        
            return {
            "type": "image",
                "source": {"type": "base64", 
                        "media_type": f"image/{self.get_image_format(image_path)}", 
                        "data": base64_encoded
                        }
            }