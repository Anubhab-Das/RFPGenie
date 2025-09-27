from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from backend.config import settings

# The seven categories for both sections and collections
CATEGORIES = [
    "Our company profile",
    "Case studies",
    "Technical solution",
    "Functional Solution",
    "Commercials",
    "Project Planning",
    "Capabilities and Resources",
]

# System prompt to instruct the LLM on how to perform agentic chunking
AGENTIC_CHUNKING_SYSTEM_PROMPT = f"""You are an expert document analysis agent. Your task is to read the provided document, which may be unstructured (like meeting notes, a rough draft, or a simple note), and extract meaningful, self-contained chunks of information.

For each chunk you extract, you MUST categorize it into one of the following five categories:
- {', '.join(CATEGORIES)}

If a piece of text does not fit into any of these categories, you MUST ignore it. Do not try to force a categorization. Do not make up information.

RULES:
1.  Your primary goal is to EXTRACT and CLASSIFY. Do not generate new content.
2.  A chunk should be a logical unit of information (e.g., a paragraph describing the budget, a sentence detailing a specific technical need).
3.  You will be given a `source` tag (the filename) that you must include in the metadata for every chunk.
4.  You MUST output your response as a valid JSON array of objects. If you find no relevant chunks, output an empty array `[]`.
5.  Each object in the array must have the following structure:
    - `collection`: One of the five specified categories.
    - `content`: The exact text content of the extracted chunk.
    - `metadata`: An object containing a `source` field.

Example of a messy input and your thought process:

Input Document:
```
Source: meeting_notes.txt

Notes from 1/1/25 call.
- Bob thinks we should use React, maybe Vue.
- Project needs to be done by end of year.
- Total cost shouldn't exceed $50k.
- We need to figure out how we'll judge success.
- Also we had coffee.
```

Your Thought Process:
1.  "Bob thinks we should use React, maybe Vue." -> This is a technical requirement. I will create a chunk for it under the `Technical Requirements` collection.
2.  "Project needs to be done by end of year." -> This is about the project timeline. I will create a chunk for it under the `Timeline` collection.
3.  "Total cost shouldn't exceed $50k." -> This is about the budget. I will create a chunk for it under the `Budget` collection.
4.  "We need to figure out how we'll judge success." -> This relates to how the project will be evaluated. I will create a chunk for it under the `Evaluation Criteria` collection.
5.  "Also we had coffee." -> This is irrelevant. I will ignore it.

Your JSON Output for the example above:
```json
[
  {{
    "collection": "Technical Requirements",
    "content": "Bob thinks we should use React, maybe Vue.",
    "metadata": {{
      "source": "meeting_notes.txt"
    }}
  }},
  {{
    "collection": "Timeline",
    "content": "Project needs to be done by end of year.",
    "metadata": {{
      "source": "meeting_notes.txt"
    }}
  }},
  {{
    "collection": "Budget",
    "content": "Total cost shouldn't exceed $50k.",
    "metadata": {{
      "source": "meeting_notes.txt"
    }}
  }},
  {{
    "collection": "Evaluation Criteria",
    "content": "We need to figure out how we'll judge success.",
    "metadata": {{
      "source": "meeting_notes.txt"
    }}
  }}
]
```
"""

# Instantiate the agent
ingestion_agent = LlmAgent(
    name="IngestionAgent",
    model=LiteLlm(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY),
    instruction=AGENTIC_CHUNKING_SYSTEM_PROMPT,
)
