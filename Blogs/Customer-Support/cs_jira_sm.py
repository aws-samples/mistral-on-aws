# JIRA imports
from jira import JIRA
from jira.resources import Issue
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import os
import requests
from cs_util import Utility

JIRA_PROJECT_NAME = "AnyCompany - Support"
JIRA_PROJECT_KEY = "AS"
JIRA_BOT_USER_ID = 'jira.ai.bot@gmail.com'
# Custom Field IDs
JIRA_CATEGORY_FIELD_ID = 10049
JIRA_RESPONSE_FIELD_ID = 10047

class JiraSM:
    def __init__(self):
        load_dotenv()
        self.jira_api_token=os.getenv("JIRA_API_TOKEN")
        self.jira_username=os.getenv("JIRA_USERNAME")
        self.jira_instance_url=os.getenv("JIRA_INSTANCE_URL")

        self.util = Utility()

    def get_jira_object(self):
        '''
        This function creates a Jira object to connect to Jira instance
        '''
        options = {'server': self.jira_instance_url}
        jira = JIRA(options, basic_auth=(self.jira_username, self.jira_api_token))
        return jira
    

    def download_attachment(self, attachment_url, filename, ticket_id):
        '''
        This function downloads attachment from Jira ticket and saves it locally in temp directory
        '''

        auth = HTTPBasicAuth(self.jira_username, self.jira_api_token)
        headers = {
            "Accept": "application/json"
        }

        response = requests.get(attachment_url, headers=headers, stream=True, auth=auth)
        response.raise_for_status()  # Raise an exception for HTTP errors

        file_path = os.path.join(self.util.get_temp_path(), filename)
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
                
        self.util.log_data(data=f"Downloaded: {file_path}", ticket_id='NA')
        return file_path
    
    def get_ticket(self, key: str):
        if (len(key) > 0):
            jira = self.get_jira_object()
            issue = jira.issue(key)
            return issue
        else:
            return None
        
    
    def update_custom_field_value(self, key: str, field_name: str, value):
        jira_issue = self.get_ticket(key)
        jira_issue.update(fields={field_name: [{'value': value}]})
        
    
    def assign_to_bot(self, key: str):
        jira_issue = self.get_jira_object()
        jira_issue.assign_issue(key, JIRA_BOT_USER_ID)

    
    def get_category_field_id(self):
        return JIRA_CATEGORY_FIELD_ID
    
    def get_response_field_id(self):
        return JIRA_RESPONSE_FIELD_ID