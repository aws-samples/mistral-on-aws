import os

from cs_util import Utility
from cs_db import Database
from cs_cust_support_flow import CustomerSupport
from cs_bedrock import BedrockClient

util = Utility()
bedrock_client = BedrockClient()

def generate_response_for_ticket(ticket_id: str):
    thread = {"configurable": {"thread_id": "123456"}}
    
    llm, vision_llm, llm_with_guardrails = bedrock_client.init_llms(ticket_id=ticket_id)
    cust_support = CustomerSupport(llm=llm, vision_llm=vision_llm, llm_with_guardrails=llm_with_guardrails)
    app   = cust_support.build_graph()
    
    state = cust_support.get_jira_ticket(key=ticket_id)
    state = app.invoke(state, thread)
    
    util.log_usage(state['usage'], ticket_id=ticket_id)
    util.log_execution_flow(state["messages"], ticket_id=ticket_id)


def main():
    db = Database()
    db.import_all()

    # create guardrails in Bedrock
    guardrail_id = bedrock_client.create_guardrail()

    # process ticket 'AS-5' - This is for refunds
    generate_response_for_ticket(ticket_id='AS-5')

    # process ticket 'AS-5' - This is for product delivery returns
    generate_response_for_ticket(ticket_id='AS-6')

    # delete guardrails
    bedrock_client.delete_guardrail()

if __name__ == '__main__':
    main()