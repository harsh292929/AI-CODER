from ...api.harsh_api import call_harsh_vision_api_with_pagination


def handle_image_query(query, image_path, instruction_prompt=None):
    return call_harsh_vision_api_with_pagination(query, image_path, include_context=True, instruction_prompt=instruction_prompt)
