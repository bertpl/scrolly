"""JSON Schema for the deck source format."""


def deck_source_schema() -> dict:
    """Return a JSON Schema describing the deck JSON5 source format."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Deck source format",
        "description": (
            "A JSON5 file describing the presentation: a list of slides "
            "on an integer grid, plus optional edges connecting them."
        ),
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Human-readable deck title.",
            },
            "slides": {
                "type": "array",
                "description": "The slides in the deck. Items are bare slide objects or group wrappers.",
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "description": "A single slide.",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Unique slide identifier, referenced by edges.",
                                },
                                "position": {
                                    "type": "array",
                                    "description": "Integer grid position [x, y]. x increases left-to-right, y increases top-to-bottom.",
                                    "items": {"type": "integer"},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                                "source": {
                                    "type": "string",
                                    "description": (
                                        "Path to the slide source file, relative to the deck file. "
                                        "Must end in .slide.json."
                                    ),
                                },
                            },
                            "required": ["id", "position", "source"],
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "description": "A group wrapper containing slides. Rendered as a labelled rectangle in deck view.",
                            "properties": {
                                "group": {
                                    "type": "string",
                                    "description": "Group label, displayed above the group rectangle in deck view.",
                                },
                                "color": {
                                    "type": "string",
                                    "description": "Group background fill as #RGB or #RRGGBB. Defaults to a neutral gray.",
                                },
                                "label_color": {
                                    "type": "string",
                                    "description": (
                                        "Group label color as #RGB or #RRGGBB. Defaults to a "
                                        "black-or-white auto-contrast pick against the background."
                                    ),
                                },
                                "slides": {
                                    "type": "array",
                                    "description": "Slides in this group.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "position": {
                                                "type": "array",
                                                "items": {"type": "integer"},
                                                "minItems": 2,
                                                "maxItems": 2,
                                            },
                                            "source": {"type": "string"},
                                        },
                                        "required": ["id", "position", "source"],
                                        "additionalProperties": False,
                                    },
                                    "minItems": 1,
                                },
                            },
                            "required": ["group", "slides"],
                            "additionalProperties": False,
                        },
                    ],
                },
            },
            "edges": {
                "type": "array",
                "description": "Navigation edges connecting slides.",
                "items": {
                    "type": "array",
                    "description": (
                        "A two-element array of endpoint strings. "
                        'Each endpoint is "slide_id" (side inferred from positions) '
                        'or "slide_id|side" (side explicit: top, bottom, left, right).'
                    ),
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        },
        "required": ["slides"],
        "additionalProperties": False,
    }
