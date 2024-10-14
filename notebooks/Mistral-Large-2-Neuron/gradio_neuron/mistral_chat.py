import gradio as gr
import boto3
import json
import io

# hyperparameters for llm
parameters = {
    "model": "nithiyn/codestral-neuron",  # placholder, needed
    "top_p": 0.6,
    "temperature": 0.9,
    "max_tokens": 2048,
    "stop": ["<|eot_id|>"],
}

system_prompt = (
    "You are an helpful Assistant, called Llama 2. Knowing everyting about AWS."
)


# Helper for reading lines from a stream
class LineIterator:
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
def create_messages_dict(message, history, system_prompt):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for user_prompt, bot_response in history:
        messages.append({"role": "user", "content": user_prompt})
        messages.append({"role": "assistant", "content": bot_response})
    messages.append({"role": "user", "content": message})
    return messages


def create_gradio_app(
    endpoint_name,
    session=boto3,
    parameters=parameters,
    system_prompt=system_prompt,
    share=True,
):
    smr = session.client("sagemaker-runtime")

    def generate(
        prompt,
        history,
    ):
        messages = create_messages_dict(prompt, history, system_prompt)

        request = {"messages": messages, **parameters, "stream": True}
        resp = smr.invoke_endpoint_with_response_stream(
            EndpointName=endpoint_name,
            Body=json.dumps(request),
            ContentType="application/json",
        )

        output = ""
        for c in LineIterator(resp["Body"]):
            c = c.decode("utf-8")
            if c.startswith("data:"):
                chunk = json.loads(c.lstrip("data:").rstrip("/n"))["choices"][0]
                if chunk["finish_reason"]:
                    break
                output += chunk["delta"]["content"]
                for stop_str in request["stop"]:
                    if output.endswith(stop_str):
                        output = output[: -len(stop_str)]
                        output = output.rstrip()
                        yield output

                yield output
        return output

    demo = gr.ChatInterface(
        generate, title="Chat with Mistral Codestral", chatbot=gr.Chatbot(layout="panel")
    )

    demo.queue().launch(share=share)
