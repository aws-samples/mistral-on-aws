import boto3
import gradio as gr
import io
import json


# default hyperparameters for llm
parameters = {
   "do_sample": True,
    "top_p": 0.6,
    "temperature": 0.9,
    "top_k": 50,
    "max_new_tokens": 2048,
    "stop": ["</s>"]
}

system_prompt = "You are a helpful Assistant, called Mathstral. You are meant to be an expert at math and reasoning generation tasks"


# Helper for reading lines from a stream

class ReadLines:
    def __init__(self, stream):
        self.byte_iterator = iter(stream)
        self.buffer = io.BytesIO()
        self.read_pos = 0

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            self.buffer.seek(self.read_pos)
            line = self.buffer.readline()
            if line and line[-1] == ord("\n"):
                self.read_pos += len(line)
                return line[:-1]
            try:
                chunk = next(self.byte_iterator)
            except StopIteration:
                if self.read_pos < self.buffer.getbuffer().nbytes:
                    continue
                raise
            if "PayloadPart" not in chunk:
                print("Unknown event type:" + chunk)
                continue
            self.buffer.seek(0, io.SEEK_END)
            self.buffer.write(chunk["PayloadPart"]["Bytes"])


# helper method to format prompt

def format_prompt(message, history, system_prompt):
    prompt = ""
    for user_prompt, bot_response in history:
        prompt = f"<s> [INST] {user_prompt} [/INST] {bot_response}</s>"
        prompt += f"### Instruction\n{user_prompt}\n\n"
        prompt += f"### Answer\n{bot_response}\n\n"  
    # add new user prompt if history is not empty
    if len(history) > 0:
        prompt += f" [INST] {message} [/INST] "    
    else:
        prompt += f"<s> [INST] {message} [/INST] "
    return prompt

def create_gradio_app(
    endpoint_name,
    session=boto3,
    parameters=parameters,
    system_prompt=system_prompt,
    format_prompt=format_prompt,
    concurrency_limit=4,
    share=True,
):
    smr = session.client("sagemaker-runtime")

    def generate(
        prompt,
        history,
    ):
        formatted_prompt = format_prompt(prompt, history, system_prompt)

        request = {"inputs": formatted_prompt, "parameters": parameters, "stream": True}
        resp = smr.invoke_endpoint_with_response_stream(
            EndpointName=endpoint_name,
            Body=json.dumps(request),
            ContentType="application/json",
        )

        output = ""
        for c in ReadLines(resp["Body"]):
            c = c.decode("utf-8")
            if c.startswith("data:"):
                chunk = json.loads(c.lstrip("data:").rstrip("/n"))
                if chunk["token"]["special"]:
                    continue
                if chunk["token"]["text"] in request["parameters"]["stop"]:
                    break
                output += chunk["token"]["text"]
                for stop_str in request["parameters"]["stop"]:
                    if output.endswith(stop_str):
                        output = output[: -len(stop_str)]
                        output = output.rstrip()
                        yield output

                yield output
        return output

    demo = gr.ChatInterface(generate, title="Chat with Codestral", concurrency_limit=4, chatbot=gr.Chatbot(layout="panel"))

    demo.launch(share=share)
