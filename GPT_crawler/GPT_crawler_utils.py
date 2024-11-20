from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
import json
import requests
import backoff

load_dotenv()
client = OpenAI()

def load_prompt(file):
    with open(file, 'r') as f:
        return f.read()
    
def get_text_snapshot(web_url):
    """
    Fetch a text snapshot of the webpage using r.jina.ai.
    
    Args:
        web_url (str): The URL of the webpage to process.
        
    Returns:
        str: The cleaned text content from the webpage, or an error message.
    """
    try:
        # Construct the API URL
        api_url = f"https://r.jina.ai/{web_url}"
        
        # Make a GET request to fetch the cleaned content
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

        # Return the text content of the response
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error fetching text snapshot: {e}"

@backoff.on_exception(backoff.expo, RateLimitError, max_time=60)
def find_available_content(url):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": load_prompt('./2024-11-19-content_finder.md')
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": get_text_snapshot(url)
                    }
                ]
            }
        ],
        temperature=0.0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "categories_dict",
                "schema": {
                    "type": "object",
                    "properties": {
                        "categories": {
                            "description": "The categories of contents to be collected, in a dictionary format. The key is the category name, and the value is the url to contents.",
                            "type": "object"
                        }
                    },
                    "additionalProperties": False
                }
            }
        }
    )
    return completion

@backoff.on_exception(backoff.expo, RateLimitError, max_time=60)
def GPT_boolean(url, query):
    """
    Checks if the given URL's content matches the query description.

    Args:
        url (str): The URL to evaluate.
        query (str): The query description to validate against the URL.

    Returns:
        bool: True if the URL content matches the query description, False otherwise.
    """
    try:
        # OpenAI completion API call
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
            {"role": "system", "content": "Some times AI returns incorrect urls, You are a helpful assistant that evaluates that checks the webpage snap shot and determine if there actually stories (with title and urls) in that page. Return 'True' if the content is relevant to the query and 'False' otherwise. return false if page not found or story not found."},
            {"role": "user", "content": get_text_snapshot(url)},
            {"role": "user", "content": query}
            ],
            temperature=0.0,
            response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "GPT_boolean",
                "schema": {
                "type": "object",
                "properties": {
                    "decision": {
                    "description": "Whether or not the URL is related to the query.",
                    "type": "boolean"
                    }
                },
                "additionalProperties": False
                }
            }
            }
        )

        # Extract the model's response
        response = json.loads(completion.choices[0].message.content)
        decision = response.get("decision", None)

        # Return True or False based on the response
        if isinstance(decision, bool):
            return decision
        else:
            raise ValueError("Unexpected response from GPT model.")
    
    except Exception as e:
        print(f"Error occurred: {e}")
        return False

@backoff.on_exception(backoff.expo, RateLimitError, max_time=60)
def get_titles_and_urls(url):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": load_prompt('./2024-11-19-get_title_and_url.md')
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": get_text_snapshot(url)
                    }
                ]
            }
        ],
        temperature=0.0,
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "titles_dict",
            "schema": {
                "type": "object",
                "properties": {
                    "titles_and_urls": {
                        "description": "A dictionary where keys are content titles and values are the corresponding URLs.",
                        "type": "object",
                        "additionalProperties": {  # Enforce key-value pairs in titles_and_urls
                            "type": "string",  # Each value (URL) must be a string
                            "description": "The URL corresponding to the title."
                        }
                    },
                    "next_page": {
                        "description": "The URL of the next page to fetch titles and URLs from. Empty means no more pages.",
                        "type": "string"
                    }
                },
                "required": ["titles_and_urls", "next_page"],  # Ensure both keys are present
                "additionalProperties": False  # Disallow extra fields
            }
        }
    }
    )
    
    return completion

@backoff.on_exception(backoff.expo, RateLimitError, max_time=60)
def get_content(url):
    completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": load_prompt('./2024-11-19-get_content.md')
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": get_text_snapshot(url)
                        }
                    ]
                }
            ],
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "story_dict",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "description": "A dictionary containing the extracted story information.",
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "description": "The title of the story.",
                                        "type": "string"
                                    },
                                    "author": {
                                        "description": "The author of the story, if available. Empty string if unknown.",
                                        "type": "string"
                                    },
                                    "content": {
                                        "description": "The main content of the story.",
                                        "type": "string"
                                    }
                                },
                                "required": ["title", "author", "content"],
                                "additionalProperties": False  # No extra fields allowed
                            },
                            "next_page": {
                                "description": "The URL of the next page to fetch more content from. Empty string means no more pages.",
                                "type": "string"
                            }
                        },
                        "required": ["content", "next_page"],  # Ensure these keys are always present
                        "additionalProperties": False  # Disallow extra fields in the top-level object
                    }
                }
    }
    )
    return completion
