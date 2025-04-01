from contextlib import redirect_stdout
from datetime import datetime
from typing import List, Tuple
import io
import re


import gradio as gr
import nest_asyncio
import requests


from llama_index.core import PromptTemplate, Settings
from llama_index.core.agent import ReActAgent
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.memory.types import ChatMessage
from llama_index.core.tools import FunctionTool


from llama_index.llms.bedrock_converse import BedrockConverse
from llama_index.tools.arxiv import ArxivToolSpec


llm = BedrockConverse(model="mistral.mistral-large-2407-v1:0", max_tokens=4000)
Settings.llm = BedrockConverse(model="mistral.mistral-large-2407-v1:0", max_tokens=4000)

# Create memory buffer
memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

def chat(message: str, history: List[dict]):
    """Process chat messages and return updated history and reasoning trace"""
    try:
        if history is None:
            history = []

        memory.put(ChatMessage(role="user", content=message))
        
        # Store the reasoning process
        trace_steps = []
        trace_steps.append("### 🔄 Processing query...")
        
        # Capture stdout to get the full reasoning trace
        thoughts_buffer = io.StringIO()
        with redirect_stdout(thoughts_buffer):
            try:
                response = agent.chat(message)
                
                # Format the response content
                if hasattr(response, 'response'):
                    response_content = response.response
                elif isinstance(response, dict) and 'response' in response:
                    response_content = response['response']
                else:
                    response_content = str(response)
                
                # Extract reasoning steps from the captured output
                raw_output = thoughts_buffer.getvalue()
                
                # Process the raw output to extract key steps
                for line in raw_output.split('\n'):
                    # Clean ANSI color codes
                    clean_line = re.sub(r'\x1b$$.*?m', '', line)
                    
                    if "Running step" in clean_line:
                        step_input = clean_line.split("Step input:")[-1].strip()
                        trace_steps.append(f"### 🔍 Query Step: {step_input}")
                    elif "Thought:" in clean_line:
                        thought = clean_line.replace("Thought:", "").strip()
                        trace_steps.append(f"### 🤔 THOUGHT:\n{thought}")
                    elif "Action:" in clean_line:
                        action = clean_line.replace("Action:", "").strip()
                        trace_steps.append(f"### 🔧 ACTION:\n`{action}`")
                    elif "Action Input:" in clean_line:
                        action_input = clean_line.replace("Action Input:", "").strip()
                        trace_steps.append(f"### 📥 INPUT:\n```json\n{action_input}\n```")
                    elif "Observation:" in clean_line:
                        trace_steps.append(f"### 👁️ OBSERVATION:\n```\n[Content truncated for readability]\n```")
                
                memory.put(ChatMessage(role="assistant", content=response_content))
                
                # Append messages in the correct dictionary format
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response_content})
                
                trace_steps.append("### ✅ Response Generated")
                
            except Exception as e:
                if "max iterations" in str(e).lower():
                    error_response = "I apologize, but I needed too many steps to process your request. Could you please rephrase your question more specifically?"
                    history.append({"role": "user", "content": message})
                    history.append({"role": "assistant", "content": error_response})
                    trace_steps.append("### ⚠️ Error: Maximum iterations exceeded")
                else:
                    raise e

        if len(history) > 12:
            history = history[-12:]
        
        # Format trace output
        trace_text = "\n\n".join(trace_steps)
        return history, trace_text

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        if history is None:
            history = []
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_message})
        return history, f"### ❌ Error occurred: {str(e)}"

        
def github_search(topic: str, num_results: int = 3, sort_by: str = "stars") -> list:
    """Search GitHub repositories by topic"""
    url = f"https://api.github.com/search/repositories?q=topic:{topic}&sort={sort_by}&order=desc"
    response = requests.get(url).json()
    code_repos = [
        {
            'html_url': item['html_url'],
            'description': item['description'],
            'stargazers_count': item['stargazers_count'],
        }
        for item in response['items'][:num_results]
    ]
    return code_repos

def news_search(topic: str, num_results: int = 3) -> list:
    """Search for news using NewsAPI"""
    API_KEY = ''
    BASE_URL = 'https://newsapi.org/v2/everything'
    
    try:
        params = {
            'q': topic,
            'apiKey': API_KEY,
            'sortBy': 'publishedAt',
            'language': 'en',
            'domains': 'techcrunch.com,wired.com,theverge.com,venturebeat.com,arstechnica.com,deeplearning.ai',
            'pageSize': num_results
        }
        
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'ok' and data['totalResults'] > 0:
                articles = []
                for article in data['articles'][:num_results]:
                    articles.append({
                        'title': article['title'],
                        'link': article['url'],
                        'published': article['publishedAt'],
                        'summary': article['description'],
                        'content': article['content']
                    })
                return articles
            else:
                print(f"No results found for topic: {topic}")
                return []
        elif response.status_code == 429:
            print("Rate limit exceeded")
            return []
        else:
            print(f"Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return []

# Create tools
github_tool = FunctionTool.from_defaults(fn=github_search)
news_tool = FunctionTool.from_defaults(fn=news_search)
arxiv_tool = ArxivToolSpec()
api_tools = arxiv_tool.to_tool_list()
api_tools.extend([news_tool, github_tool])

# System prompt
system_prompt = """
You are a friendly and engaging technology expert with access to the GitHub API, arXiv API, and TechCrunch API. 
Think of yourself as an enthusiastic tech researcher having a conversation with a colleague.
Your news_search tool returns the absolute latest articles, often just minutes or hours old.
## Tools
You have access to these tools and are responsible for using them in any sequence you deem appropriate:
{tool_desc}

## Output Format
To answer the question, please use the following format:

Thought: Explain your thinking process conversationally
Action: tool name (one of {tool_names})
Action Input: the input to the tool in JSON format

If a tool returns no results, try:
1. Using a different tool
2. Modifying your search terms
3. If all tools fail, acknowledge that you couldn't find the information

When you get an empty result, don't repeat the same exact search - try a different approach.

Continue until you can answer or determine you can't find the information, then use:

Thought: [Explain your conclusion]
Answer: [Provide your findings or explain why you couldn't find the information]

## Additional Rules
- If a search returns no results, try alternative search terms or different tools
- Don't repeat the same search multiple times
- If no information is found after trying different approaches, acknowledge the limitation
- Use a conversational, engaging tone
- Connect ideas across different sources when relevant
- Highlight what's exciting or surprising
- Keep it concise but interesting
- Always check the dates of the articles and mention if they're not recent
- If articles are more than 30 days old, try another search or tool
- Format dates in a user-friendly way (e.g., "2 days ago" or "March 15, 2024")
- Keep responses clear and concise, but when the answer should be longer format feel free to make it so if it helps the user understand the full answer.

## Current Conversation
Below is the current conversation consisting of interleaving human and assistant messages.
"""

# Create and configure agent
react_system_prompt = PromptTemplate(template=system_prompt)
agent = ReActAgent.from_tools(
    api_tools,
    llm=llm,
    verbose=True,
    max_iterations=10,
    memory=memory
)
agent.update_prompts({"agent_worker:system_prompt": react_system_prompt})
agent.reset()


def create_gradio_interface():
    with gr.Blocks(css="""
        .markdown-display {
            height: 600px;
            overflow-y: auto;
            padding: 15px;
            background-color: #f7f7f7;
            border-radius: 5px;
        }
    """) as demo:
        gr.Markdown("# AI Research Assistant")
        
        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    [],
                    type='messages',
                    label="Chat History"
                )
                
                msg = gr.Textbox(
                    show_label=False,
                    placeholder="Ask about the latest tech news, research papers, or GitHub projects...",
                    container=False,
                    lines=1,
                    max_lines=1
                )
                
                clear = gr.Button("Clear Conversation")
            
            with gr.Column(scale=1):
                agent_reasoning = gr.Markdown(
                    value="The agent's reasoning will appear here...",
                    label="Agent Reasoning Process",
                    elem_classes=["markdown-display"]
                )

        # Update the submission flow
        msg.submit(
            chat,
            [msg, chatbot],
            [chatbot, agent_reasoning],
        ).then(
            lambda: "",
            None,
            msg
        )

        clear.click(
            fn=lambda: ([], "The agent's reasoning will appear here..."),
            inputs=None,
            outputs=[chatbot, agent_reasoning],
            queue=False
        )
        
        return demo

if __name__ == "__main__":
    demo = create_gradio_interface()
    demo.launch(server_name="0.0.0.0", server_port=7864, share=True)