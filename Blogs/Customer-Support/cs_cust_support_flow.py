import sys
import json
from typing import Literal
from cs_jira_sm import JiraSM
from cs_db import Database
from cs_util import Utility

# LangGraph imports
from typing import Annotated
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, InjectedState
from langchain_core.tools.structured import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.runnables.graph import MermaidDrawMethod

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

from IPython.display import Image, display
from cs_bedrock import BedrockClient

# class to hold state information
class JiraAppState(MessagesState):
    key: str
    summary: str
    description: str
    attachments: list
    category: str
    response: str
    transaction_id: str
    order_no: str
    usage: list
    

class CustomerSupport:

    def __init__(self, llm, vision_llm, llm_with_guardrails):
        self.util = Utility()
        self.bedrock_client = BedrockClient()
        
        self.state = None
        self.graph_app = None
        self.thread = {"configurable": {"thread_id": "123456"}}

        self.llm = llm
        self.vision_llm = vision_llm
        self.llm_with_guardrails = llm_with_guardrails

    

    def determine_ticket_category_tool(self, state: JiraAppState):
        '''
        This function uses LLM to categorize ticket
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])
        self.state = state # setting this for usage in ReAct tools

        prompt = f"""
                        Task: Categorize the support ticket based on the provided details.

                        Ticket Title: {state['summary']}
                        Ticket Body: {state['description']}
                        
                        Categories:
                        Transaction
                        Delivery
                        Refunds
                        Other
                        
                        Respond with only the most appropriate category. Do not include any additional text.

                        """
        
        state['messages'].append(HumanMessage(content=prompt))
        ai_msg = self.llm_with_guardrails.invoke(state['messages'], self.thread)
        state = self.add_usage(state, ai_msg)
        
        state['messages'].append(ai_msg)
        state['category'] = ai_msg.content.strip()

        return state
    
    def add_usage(self, state: JiraAppState, ai_msg: AIMessage):
        '''
        This function adds usage information to the state object
        '''

        model = ai_msg.response_metadata.get('model_name')
        usage_data = ai_msg.usage_metadata
        latency = ai_msg.response_metadata.get('metrics').get('latencyMs')

        latency_total = 0
        if type(latency) is list:
            for l in latency:
                latency_total += l
        else:
            latency_total = latency

        state['usage'].append(
            {
                'model_name': model,
                'input_tokens': usage_data.get('input_tokens'),
                'output_tokens': usage_data.get('output_tokens'),
                'latency': latency_total
             })
        
        return state

    def assign_ticket_category_in_jira_tool(self, state: JiraAppState):
        '''
        This function assigns ticket category and resolver in Jira
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        jira_sm = JiraSM()
        category_field_id = f'customfield_{jira_sm.get_category_field_id()}'
        jira_sm.update_custom_field_value(state['key'], category_field_id, state['category'])

        self.util.log_data(data=f"Updated category to '{state['category']}'", ticket_id=state['key'])

        return state


    def extract_transaction_id_tool(self, state: JiraAppState):
        '''
        This function extracts transaction id from the ticket description. 
        If ticket has an screenshot as attachment, extracts transaction id from the attachment
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name)
        
        human_messages = [{"type": "text", "text": 
                        f"""
                        
                        Task: Extract and return the transaction ID in the following JSON format:

                        {{
                        "transactionid": "<transaction_id>"
                        }}
                        
                        Output only the JSON object, with no additional text or formatting.

                        """
                        }]

        use_vlm = False

        state['messages'].append(HumanMessage(content=human_messages))
        
        if (len(state['attachments']) > 0):
            file_name = state['attachments'][0]['filename']
            image_data = self.util.add_image_content(file_name, ticket_id=state['key'])  # let's use first image
            human_messages.append(image_data)
            use_vlm = True
            self.util.display_image(file_name)

        if (use_vlm):
            # we are not adding images section to state['messages']
            messages = [HumanMessage(content=human_messages)]
            
            ai_msg = self.vision_llm.invoke(messages, self.thread)
            state = self.add_usage(state, ai_msg)
        else:
            ai_msg = self.llm.invoke(state['messages'], self.thread)
            state = self.add_usage(state, ai_msg)
        
        state['messages'].append(ai_msg)
        response_content = ai_msg.content
        
        response_content = self.util.clean_json_string(response_content)
        jsonobj = json.loads(response_content)
        
        state['transaction_id'] = jsonobj['transactionid']

        return state



    def extract_order_number_tool(self, state: JiraAppState):
        '''
        This function extracts order number from the ticket description. 
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        prompt = """
                    Task: Extract and return the order number in the following JSON format:

                    {
                    "orderno": "<order_no>"
                    }
                    
                    Provide only the JSON object, without any additional text or formatting.
                    """

        state['messages'].append(HumanMessage(content=prompt))
        ai_msg = self.llm.invoke(state['messages'], self.thread)
        state = self.add_usage(state, ai_msg)
        state['messages'].append(ai_msg)

        response_content = ai_msg.content
        response_content = self.util.clean_json_string(response_content)

        jsonobj = json.loads(response_content)
        
        state['order_no'] = jsonobj['orderno']

        return state

    def decide_ticket_flow_condition(self, state: JiraAppState) -> Literal["Extract Transaction ID", "Extract Order Number"]:

        '''
        This function determines the workflow based on the intent (ticket category). 
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])
        category = state['category'].lower()

        if (category == 'transaction'):
            return "Extract Transaction ID"
        else:
            return "Extract Order Number"
        

    def find_transaction_details_tool(self, state: JiraAppState):
        '''
        This function queries the SQLite database to find transaction information for the provided transaction id
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name)

        # query database to check transaction status
        query = """
            SELECT * FROM transactions
            WHERE transaction_id = ?
            LIMIT 1
        """
        self.util.log_data(state['transaction_id'], ticket_id=state['key'])

        db = Database()
        state['response'] = db.execute_query(query, params=[state['transaction_id']], 
                                            not_found_message=f"No record found for Transaction ID: {state['transaction_id']}")

        state['response'] = f"{state['response']} \nIn case of transaction failures, customer's account is not debited"
        self.util.log_data(data=state['response'], ticket_id=state['key'])
        
        return state
    
    def get_last_tool_id(self, messages):
        # Traverse messages in reverse to find the last AIMessage with a tool call
        for msg in reversed(messages):
            # If tool_calls attribute exists (LangChain style)
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                return tool_calls[0].get("id") or tool_calls[0].id
            
            # If content is a list of dicts (OpenAI/LLM style)
            content = getattr(msg, "content", None)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") in ("tool_use", "tool_call"):
                        return item.get("id")
        return None


    def assess_damaged_delivery(self, order_no, 
                                state: Annotated[dict, InjectedState]):
        """
        Use this tool to handle tasks related to damaged deliveries. It performs a damage assessment by analyzing and comparing delivered product images.

        order_no: str
    
        Returns:
            str: The result of the damage assessment.
        """

        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])
        
        human_messages = [{"type": "text", "text": f"""
                    # Input:
                        # - Image 1: A picture of the product as listed on the website.
                        # - Image 2: A picture of the product returned by the customer, who claims it is damaged.
                        
                    # Task:
                        # Analyze the two images and answer the following questions:
                    
                    ## Questions:
                        1. Product Verification:
                        - Do both images depict the same product?
                        - Compare key features such as:
                            - Model number
                            - Color
                            - Design
                            - Logos
                            - Patterns
                            - Dimensions
                            - Any other identifiable attributes.
                        - If the images do not represent the same product, request that the customer provide a clearer or additional picture of the returned product for verification.
                    
                        2. Damage Assessment:
                        - If the products are confirmed to be the same, does the returned product (Image 2) show any signs of damage?
                        - If yes, describe:
                            - Type of damage (e.g., scratches, dents, broken parts).
                            - Extent of damage.
                    
                    ## Guidelines for Analysis:
                        - Fraud Prevention Measures:
                        1. Ensure accurate identification of similarities or differences between Image 1 and Image 2 to confirm if they represent the same product.
                        2. Carefully assess Image 2 for visible signs of damage or tampering after verifying it matches Image 1.
                        
                        - Use a systematic approach to evaluate both images side by side.
                        - Focus on details like unique characteristics or discrepancies.
                    
                    ## Additional Instructions:
                        - If it is determined that Image 2 does not match Image 1 (i.e., they are different products):
                        - Clearly state this in your response.
                        - Instruct that a clearer or additional image of the returned product be provided by the customer for further analysis.
                        
                    # Output:
                        - Provide a clear and detailed response to each question.

                        """
                        }]
        
        
        #state1 = self.graph_app.get_state(self.thread)

        state['messages'].append(HumanMessage(content=human_messages))
        listed_product_picture = './data/listed-bottle.jpg'
        image_data = self.util.add_image_content(listed_product_picture, ticket_id=state['key'])  
        human_messages.append(image_data)


        if (len(state['attachments']) > 0):
            file_name = state['attachments'][0]['filename']
            image_data = self.util.add_image_content(file_name, ticket_id=state['key'])  # This is the damaged product picture shared by customer
            human_messages.append(image_data)
            self.util.log_data("Listed Product Picture", ticket_id=state['key'])
            self.util.display_image(listed_product_picture)
            self.util.log_data("Customer Shared Picture", ticket_id=state['key'])
            self.util.display_image(file_name)
            
        messages = [HumanMessage(content=human_messages)]
        ai_msg = self.vision_llm.invoke(messages, self.thread)
        self.state = self.add_usage(self.state, ai_msg)
        response_content = ai_msg.content
        
        return response_content
        

    # @tool
    def find_refund_status(self, order_no: str, state: Annotated[dict, InjectedState]) -> str:
        """
        Use this tool to retrieve the refund status for a specific order.

        Args:
            order_no (str): The order number for which the refund status is being requested.

        Returns:
            str: The current status of the refund process.

        """

        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])
        query = """
            SELECT * FROM refunds
            WHERE order_no = ?
            LIMIT 1
        """

        db = Database()
        response = db.execute_query(query, params=[order_no], 
                                            not_found_message=f'No refund record found for order no: {order_no}')

        self.util.log_data(data=response, ticket_id=state['key'])
        return response


    def find_order_details_tool(self, state: JiraAppState):
        '''
        This function queries the SQLite database to find order information for the provided order number
        '''
        
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        # query database to check order details
        query = """
            SELECT * FROM orders
            WHERE order_no = ?
            LIMIT 1
        """

        db = Database()
        response = db.execute_query(query, params=[state['order_no']],
                                    not_found_message=f"No records found for order number {state['order_no']}")
        
        prompt = f"""
                        Task: Respond to the question in the support ticket using the provided order details. 
                        
                        Ticket Title: {state['summary']}
                        Ticket Body: {state['description']}
                        Order number: {state['order_no']}
                        Order details: {response}

                        If additional information is needed, use the available tools to gather it before responding.

                        """
        
        state['messages'].append(HumanMessage(content=prompt))

        # llm_with_tools = self.llm.bind_tools([self.assess_damaged_delivery, self.find_refund_status])    
        llm_with_tools = self.llm.bind_tools([StructuredTool.from_function(self.assess_damaged_delivery), 
                                              StructuredTool.from_function(self.find_refund_status)])


        ai_msg = llm_with_tools.invoke(state['messages'], self.thread)
        state = self.add_usage(state, ai_msg)

        state['messages'].append(ai_msg)
        state['response'] = ai_msg.content

        return state

    

    def generate_response_tool(self, state: JiraAppState):
        '''
        This function uses context from previous steps to generate a context-aware response to the customer query

        '''
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        last_ai_message = state['messages'][-1]
        response = ''

        if (type(last_ai_message) is ToolMessage):
            response = last_ai_message.content
            state['messages'] = state['messages'][:-3]
            state['messages'].append(AIMessage(content=response))
        else:
            response = state['response']
        
        prompt = f"""
            Task: Generate a response to the customer's query based on the provided context. 

            Guidelines:
            - Address the response directly to the customer.
            - Ensure the response is concise and accurate.
            - If accurate information is unavailable, respond with: "I am sorry, I do not have enough information to provide an accurate response."
            - Do not ask for additional information if you have enough data to prepare response

            Context: {response}
            
            """
        
        state['messages'].append(HumanMessage(content=prompt))

        ai_msg = self.llm_with_guardrails.invoke(state['messages'], self.thread)
        state = self.add_usage(state, ai_msg)
            
        state['messages'].append(ai_msg)
        state['response'] = ai_msg.content
        
        return state


    def update_response_in_jira_tool(self, state: JiraAppState):
        '''
        This function updates Jira ticket with the generated response
        '''

        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        jira_sm = JiraSM()
        response_field_id = f'customfield_{jira_sm.get_response_field_id()}'
        jira_sm.update_custom_field_value(state['key'], response_field_id, state['response'])
        
        self.util.log_data(data=f"Updated ticket with Response.", ticket_id=state['key'])

        return state


    def order_query_decision(self, state: JiraAppState):

        '''
        ReAct agent can determine whether a tool calling is required to answer customer query.
        This function implements conditional flow to either directly generate response or call 
        other tools to acquire additional context.
        '''

        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=state['key'])

        messages = state["messages"]

        last_message = messages[-1]
        # self.util.log_data(last_message.content, ticket_id=state['key'])

        if ((last_message.tool_calls)):
            return "tools"
        return "Generate Response"
    
    def build_graph(self):
        """
        This function prepares LangGraph nodes, edges, conditional edges, compiles the graph and displays it 
        """

        # create StateGraph object
        graph_builder = StateGraph(JiraAppState)

        # add nodes to the graph
        graph_builder.add_node("Determine Ticket Category", self.determine_ticket_category_tool)
        graph_builder.add_node("Assign Ticket Category in JIRA", self.assign_ticket_category_in_jira_tool)
        graph_builder.add_node("Extract Transaction ID", self.extract_transaction_id_tool)
        graph_builder.add_node("Extract Order Number", self.extract_order_number_tool)
        graph_builder.add_node("Find Transaction Details", self.find_transaction_details_tool)
        
        graph_builder.add_node("Find Order Details", self.find_order_details_tool)
        graph_builder.add_node("Generate Response", self.generate_response_tool)
        graph_builder.add_node("Update Response in JIRA", self.update_response_in_jira_tool)

        graph_builder.add_node("tools", ToolNode([StructuredTool.from_function(self.assess_damaged_delivery), StructuredTool.from_function(self.find_refund_status)]))
        
        # add edges to connect nodes
        graph_builder.add_edge(START, "Determine Ticket Category")
        graph_builder.add_edge("Determine Ticket Category", "Assign Ticket Category in JIRA")
        graph_builder.add_conditional_edges("Assign Ticket Category in JIRA", self.decide_ticket_flow_condition)
        graph_builder.add_edge("Extract Order Number", "Find Order Details")
        
        graph_builder.add_edge("Extract Transaction ID", "Find Transaction Details")
        graph_builder.add_conditional_edges("Find Order Details", self.order_query_decision, ["Generate Response", "tools"])
        graph_builder.add_edge("tools", "Generate Response")
        graph_builder.add_edge("Find Transaction Details", "Generate Response")
        
        graph_builder.add_edge("Generate Response", "Update Response in JIRA")
        graph_builder.add_edge("Update Response in JIRA", END)

        # compile graph
        checkpoint = MemorySaver()
        app = graph_builder.compile(checkpointer=checkpoint)
        self.graph_app = app
        self.util.log_data(data="Workflow compiled successfully", ticket_id='NA')

        # Visualize the graph
        display(Image(app.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.API)))

        return app
    


    def get_jira_ticket(self, key: str):
        '''
        This function reads gets provided Jira ticket and prepares JiraAppState object
        '''
        self.util.log_header(function_name=sys._getframe().f_code.co_name, ticket_id=key)

        jira_sm = JiraSM()
        issue = jira_sm.get_ticket(key)
        if (issue is None):
            # log_error()
            return
        
        state = JiraAppState()
        attachments = issue.fields.attachment or []
        local_attachments = []
        for attachment in attachments:
            file_name = f'{issue.key}-{attachment.filename}'
            attachment_path = jira_sm.download_attachment(attachment_url=attachment.content, filename=file_name, ticket_id=key)
            local_attachments.append({"filename": attachment_path})

        state['key'] = issue.key
        state['summary'] = issue.fields.summary
        state['description'] = issue.fields.description
        state['attachments'] = local_attachments
        state['usage'] = [] 
        
        system_prompt = f''' 
            You are a professional and courteous customer support agent for AnyCompany. Your goal is to assist users effectively and efficiently using the tools and information provided. 

            Guidelines:
            1. Maintain a polite, helpful, and pleasant tone at all times.
            2. Avoid using strong or negative words. For example, replace words like "frustrating" with softer alternatives such as "inconvenience."
            3. Respond to customer queries based strictly on factual information.
            4. If sufficient information is not available to address a query, respond with: "I do not have enough information to answer this query."
            
            Your primary objective is to provide accurate, empathetic, and solution-oriented support while ensuring a positive customer experience.
        '''

        messages = [
            SystemMessage(
                    content=system_prompt)
            ]
        
        state['messages'] = messages
        return state

