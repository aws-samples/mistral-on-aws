import boto3
import os
from typing import Tuple
from cs_util import Utility
from langchain_aws import ChatBedrockConverse

GUARDRAIL_NAME = "customer-support-content-safety-guardrail"
DEFAULT_MODEL  = "mistral.mistral-large-2407-v1:0"
VISION_MODEL   = 'us.mistral.pixtral-large-2502-v1:0'
AWS_REGION = "us-west-2"

class BedrockClient:
    def __init__(self):
        self.util = Utility()
        self.guardrail_id = ''
        self.guardrail_version = 'DRAFT'
        

    def init_llms(self, ticket_id: str):

        self.util.log_data(f'Initializing Bedrock client', ticket_id=ticket_id)
        self.util.log_data(f'Using guardrail_id==> {self.guardrail_id}', ticket_id=ticket_id)

        # Initialize ChatBedrockConverse for Text
        llm = ChatBedrockConverse(
            model=DEFAULT_MODEL,
            temperature=0,
            max_tokens=4000,
            region_name=AWS_REGION,
        )

        llm_with_guardrails = ChatBedrockConverse(
            model=DEFAULT_MODEL,
            temperature=0,
            max_tokens=4000,
            region_name=AWS_REGION,
            guardrails={
                        "guardrailIdentifier": self.guardrail_id,
                        "guardrailVersion": self.guardrail_version,
                        "trace": "enabled"
                        }
        )

        # Initialize ChatBedrockConverse for Vision
        vision_llm = ChatBedrockConverse(
            model=VISION_MODEL,
            temperature=0,
            max_tokens=4000,
            region_name=AWS_REGION,
        )

        return llm, vision_llm, llm_with_guardrails
    

    def create_guardrail(self) -> str:
        """
        Creates a guardrail in Amazon Bedrock with topic policy configuration.
        
        Returns:
            Tuple[str, str]: Guardrail ID and version
        """
        try:
            # Initialize the Bedrock client
            bedrock_client = boto3.client('bedrock', AWS_REGION)

            # check if guardrail already exists 
            response = bedrock_client.list_guardrails()

            guardrail_exists = False
            # Check if guardrail exists
            for guardrail in response['guardrails']:
                if guardrail['name'] == GUARDRAIL_NAME:
                    guardrail_exists = True
                    self.guardrail_id = guardrail['id']
                    
                    return self.guardrail_id
            
            if (not guardrail_exists):
                # Create the guardrail
                create_response = bedrock_client.create_guardrail(
                    name=GUARDRAIL_NAME,
                    description='Guardrails to prevent harmful content generation',
                    contentPolicyConfig={
                        'filtersConfig': [
                            {
                                'type': 'SEXUAL',
                                'inputStrength': 'MEDIUM',
                                'outputStrength': 'MEDIUM'
                            },
                            {
                                'type': 'VIOLENCE',
                                'inputStrength': 'MEDIUM',
                                'outputStrength': 'MEDIUM'
                            },
                            {
                                'type': 'HATE',
                                'inputStrength': 'MEDIUM',
                                'outputStrength': 'MEDIUM'
                            },
                            {
                                'type': 'INSULTS',
                                'inputStrength': 'MEDIUM',
                                'outputStrength': 'MEDIUM'
                            },
                            {
                                'type': 'MISCONDUCT',
                                'inputStrength': 'MEDIUM',
                                'outputStrength': 'MEDIUM'
                            },
                            {
                                'type': 'PROMPT_ATTACK',
                                'inputStrength': 'LOW',
                                'outputStrength': 'NONE'
                            }
                        ]
                    },
                    wordPolicyConfig={
                        'wordsConfig': [
                            {'text': 'stock and investment advise'}
                        ],
                        'managedWordListsConfig': [
                            {'type': 'PROFANITY'}
                        ]
                    },
                    contextualGroundingPolicyConfig={
                        'filtersConfig': [
                            {
                                'type': 'GROUNDING',
                                'threshold': 0.65
                            },
                            {
                                'type': 'RELEVANCE',
                                'threshold': 0.75
                            }
                        ]
                    },
                    blockedInputMessaging="""Input prompt or context is not appropriate for customer support.""",
                    blockedOutputsMessaging="""Generated output is not appropriate for the customer support""",
                )
                
                self.guardrail_id  = create_response['guardrailId']
                return self.guardrail_id
            
        except Exception as e:
            self.util.log_error(f"Error creating guardrail: {str(e)}", ticket_id='NA')
            raise e
    
    def delete_guardrail(self) -> bool:
        """
        Deletes a guardrail from Amazon Bedrock.
        
        Args:
            guardrail_id (str): The identifier of the guardrail to delete
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Initialize the Bedrock client
            bedrock_client = boto3.client('bedrock')
            
            # Delete the guardrail
            response = bedrock_client.delete_guardrail(guardrailIdentifier=self.guardrail_id)
            
            # Check if deletion was successful
            if response['ResponseMetadata']['HTTPStatusCode'] == 202:
                self.util.log_data(f"Successfully deleted guardrail", ticket_id='NA')
                return True
            
            return False
            
        except bedrock_client.exceptions.ResourceNotFoundException:
            self.util.log_error(f"Guardrail with ID {self.guardrail_id} not found")
            return False
        except Exception as e:
            self.util.log_error(f"Error deleting guardrail: {str(e)}")
            return False
    
    
