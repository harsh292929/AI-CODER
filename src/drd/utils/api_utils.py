import requests
import mimetypes
import os
import json
import base64
from typing import Dict, Any, Optional, List
import xml.etree.ElementTree as ET
import click

# Update these constants according to your LM Studio setup
LM_STUDIO_URL = 'http://localhost:1234/v1/chat/completions'
MODEL = 'local_model'  # This might vary depending on your LM Studio configuration
MAX_TOKENS = 4000

def get_headers() -> Dict[str, str]:
    return {
        'Content-Type': 'application/json'
    }

def make_api_call(data: Dict[str, Any], headers: Dict[str, str], stream: bool = False) -> requests.Response:
    response = requests.post(LM_STUDIO_URL, json=data, headers=headers, stream=stream)
    response.raise_for_status()
    return response

def parse_response(response: str) -> str:
    try:
        root = ET.fromstring(response)
        return ET.tostring(root, encoding='unicode')
    except ET.ParseError:
        click.echo(f"Error parsing XML response. Returning raw response.", err=True)
        return response

def call_harsh_api_with_pagination(query: str, include_context: bool = False, instruction_prompt: Optional[str] = None) -> str:
    headers = get_headers()
    full_response = ""

    messages = []
    if instruction_prompt:
        messages.append({"role": "system", "content": instruction_prompt})
    messages.append({"role": "user", "content": query})

    data = {
        'model': MODEL,
        'messages': messages,
        'max_tokens': MAX_TOKENS
    }

    while True:
        response = make_api_call(data, headers)
        resp = response.json()
        full_response += resp['choices'][0]['message']['content']

        if resp['choices'][0]['finish_reason'] == 'length':
            # If the response was truncated, continue the conversation
            data['messages'].append({"role": "assistant", "content": full_response})
            data['messages'].append({"role": "user", "content": "Please continue."})
        else:
            break

    return parse_response(full_response)

def call_harsh_vision_api_with_pagination(query: str, image_path: str, include_context: bool = False, instruction_prompt: Optional[str] = None) -> str:
    headers = get_headers()
    full_response = ""

    # Read and encode the image
    mime_type, _ = mimetypes.guess_type(image_path)
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')

    messages = []
    if instruction_prompt:
        messages.append({"role": "system", "content": instruction_prompt})
    
    # Construct the message with both image and text
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}"
                }
            },
            {
                "type": "text",
                "text": query
            }
        ]
    })

    data = {
        'model': MODEL,
        'messages': messages,
        'max_tokens': MAX_TOKENS
    }

    while True:
        response = make_api_call(data, headers)
        resp = response.json()
        full_response += resp['choices'][0]['message']['content']

        if resp['choices'][0]['finish_reason'] == 'length':
            # If the response was truncated, continue the conversation
            data['messages'].append({"role": "assistant", "content": full_response})
            data['messages'].append({"role": "user", "content": "Please continue."})
        else:
            break

    return parse_response(full_response)

def stream_claude_response(query: str, instruction_prompt: Optional[str] = None) -> str:
    headers = get_headers()

    messages = []
    if instruction_prompt:
        messages.append({"role": "system", "content": instruction_prompt})
    messages.append({"role": "user", "content": query})

    data = {
        'model': MODEL,
        'messages': messages,
        'max_tokens': MAX_TOKENS,
        'stream': True
    }

    response = make_api_call(data, headers, stream=True)
    full_response = ""

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                try:
                    chunk_data = json.loads(line[6:])
                    if chunk_data['choices'][0]['delta'].get('content'):
                        chunk = chunk_data['choices'][0]['delta']['content']
                        full_response += chunk
                        click.echo(chunk, nl=False)
                except json.JSONDecodeError:
                    pass

    click.echo()
    return full_response

def parse_paginated_response(response: str) -> List[Dict[str, Any]]:
    # First, try to extract the XML content
    xml_start = response.find('<response>')
    xml_end = response.rfind('</response>') + 11  # +11 to include '</response>'

    if xml_start != -1 and xml_end != -1:
        xml_content = response[xml_start:xml_end]
        try:
            root = ET.fromstring(xml_content)
            # Implement your XML parsing logic here
            # This is a placeholder implementation
            return [{'type': 'xml', 'content': ET.tostring(root, encoding='unicode')}]
        except ET.ParseError:
            click.echo("Error parsing XML. Treating response as regular text.", err=True)

    # If no XML is found or parsing fails, treat the response as regular text
    return [{'type': 'explanation', 'content': response.strip()}]

@click.command()
@click.option('--query', prompt='Enter your query', help='The query to send to the local LM.')
@click.option('--stream', is_flag=True, help='Stream the response.')
@click.option('--instruction', help='Optional instruction prompt.')
@click.option('--image_path', help='Path to an image file for vision API.')
def main(query: str, stream: bool, instruction: Optional[str], image_path: Optional[str]):
    try:
        if image_path:
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            response = call_harsh_vision_api_with_pagination(query, image_path, instruction_prompt=instruction)
            click.echo(response)
        elif stream:
            response = stream_claude_response(query, instruction)
        else:
            response = call_harsh_api_with_pagination(query, instruction_prompt=instruction)
            click.echo(response)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)

if __name__ == '__main__':
    main()