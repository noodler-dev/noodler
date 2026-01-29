import json
import os
import logging
from openai import OpenAI
from typing import List, Dict

logger = logging.getLogger(__name__)


def categorize_annotations(annotations: List) -> List[Dict[str, str]]:
    """
    Categorize annotations using OpenAI API.

    Args:
        annotations: List of Annotation objects with notes

    Returns:
        List of dictionaries with 'name' and 'description' keys

    Raises:
        ValueError: If API key is missing or API call fails
        json.JSONDecodeError: If LLM response is not valid JSON
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    # Filter annotations with non-empty notes
    annotations_with_notes = [
        ann for ann in annotations if ann.notes and ann.notes.strip()
    ]

    if not annotations_with_notes:
        return []

    # Build prompt with all annotation notes
    annotations_text = "\n\n".join(
        [
            f"Annotation {i + 1}:\n{ann.notes.strip()}"
            for i, ann in enumerate(annotations_with_notes)
        ]
    )

    prompt = f"""You are analyzing error annotations from an AI application evaluation dataset. 
Review the following annotations and identify common failure modes/categories.

Annotations:
{annotations_text}

Return a JSON array of failure mode categories. Each category should have:
- name: A concise category name (e.g., "Hallucination", "Format Error", "Incorrect Reasoning")
- description: A brief description of this failure mode

Format your response as a valid JSON array: [{{"name": "...", "description": "..."}}, ...]

Focus on identifying distinct failure patterns. Aim for 3-10 categories that capture the main types of failures."""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini for cost efficiency, can be changed to gpt-4 if needed
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing AI application failures and categorizing them into meaningful failure modes. Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent categorization
        )

        content = response.choices[0].message.content.strip()

        # Try to extract JSON from response (in case LLM adds extra text)
        # Look for JSON array pattern
        start_idx = content.find("[")
        end_idx = content.rfind("]") + 1

        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON array found in LLM response")

        json_str = content[start_idx:end_idx]
        categories = json.loads(json_str)

        # Validate structure
        if not isinstance(categories, list):
            raise ValueError("LLM response is not a list")

        validated_categories = []
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            if "name" not in cat or not cat["name"]:
                continue
            validated_categories.append(
                {
                    "name": str(cat["name"]).strip(),
                    "description": str(cat.get("description", "")).strip(),
                }
            )

        return validated_categories

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise ValueError(f"Invalid JSON response from LLM: {e}")
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise ValueError(f"Failed to categorize annotations: {e}")
