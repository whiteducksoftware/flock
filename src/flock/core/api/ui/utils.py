# src/flock/core/api/ui/utils.py
"""Utility functions for the Flock FastHTML UI."""

import html
from typing import Any

from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import (
    split_top_level,  # Assuming this is the correct location
)

logger = get_logger("api.ui.utils")


def parse_input_spec(input_spec: str) -> list[dict[str, str]]:
    """Parses an agent input string into a list of field definitions."""
    fields = []
    if not input_spec:
        return fields
    try:
        parts = split_top_level(input_spec)
    except NameError:
        logger.error("split_top_level utility function not found!")
        return fields  # Or raise?

    for part in parts:
        part = part.strip()
        if not part:
            continue
        field_info = {
            "name": "",
            "type": "str",
            "desc": "",
            "html_type": "text",
        }
        name_type_part, *desc_part = part.split("|", 1)
        if desc_part:
            field_info["desc"] = desc_part[0].strip()
        name_part, *type_part = name_type_part.split(":", 1)
        field_info["name"] = name_part.strip()
        if type_part:
            field_info["type"] = type_part[0].strip().lower()

        step = None
        field_type_norm = field_info["type"]
        if field_type_norm.startswith("int"):
            field_info["html_type"] = "number"
        elif field_type_norm.startswith("float"):
            field_info["html_type"] = "number"
            step = "any"
        elif field_type_norm.startswith("bool"):
            field_info["html_type"] = "checkbox"
        elif "list" in field_type_norm or "dict" in field_type_norm:
            field_info["html_type"] = "textarea"
            field_info["rows"] = 3

        if step:
            field_info["step"] = step
        if field_info["name"]:
            fields.append(field_info)
        else:
            logger.warning(
                f"Could not parse field name from input spec part: '{part}'"
            )
    return fields


def format_result_to_html(
    data: Any, level: int = 0, max_level: int = 5, max_str_len: int = 999999
) -> str:
    """Recursively formats a Python object (dict, list, Box, etc.) into an HTML string."""
    if hasattr(data, "to_dict") and callable(data.to_dict):
        data = data.to_dict()
    if level > max_level:
        return html.escape(f"[Max recursion depth {max_level} reached]")

    if isinstance(data, dict):
        if not data:
            return "<i>(empty dictionary)</i>"
        table_html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #dee2e6;">'
        table_html += '<thead style="background-color: #e9ecef;"><tr><th style="text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6;">Key</th><th style="text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6;">Value</th></tr></thead>'
        table_html += "<tbody>"
        for key, value in data.items():
            escaped_key = html.escape(str(key))
            formatted_value = format_result_to_html(
                value, level + 1, max_level, max_str_len
            )  # Recursive call
            table_html += f'<tr><td style="vertical-align: top; padding: 8px; border-top: 1px solid #dee2e6;"><strong>{escaped_key}</strong></td><td style="padding: 8px; border-top: 1px solid #dee2e6;">{formatted_value}</td></tr>'
        table_html += "</tbody></table>"
        return table_html
    elif isinstance(data, (list, tuple)):
        if not data:
            return "<i>(empty list)</i>"
        list_html = '<dl style="margin-left: 20px; padding-left: 0; margin-bottom: 10px;">'
        for i, item in enumerate(data):
            formatted_item = format_result_to_html(
                item, level + 1, max_level, max_str_len
            )  # Recursive call
            list_html += f'<dt style="font-weight: bold; margin-top: 5px;">Item {i + 1}:</dt><dd style="margin-left: 20px; margin-bottom: 5px;">{formatted_item}</dd>'
        list_html += "</dl>"
        return list_html
    else:
        str_value = str(data)
        escaped_value = html.escape(str_value)
        if len(str_value) > max_str_len:
            escaped_value = (
                html.escape(str_value[:max_str_len])
                + f"... <i style='color: #6c757d;'>({len(str_value) - max_str_len} more chars)</i>"
            )

        style = ""
        if isinstance(data, bool):
            style = "color: #d63384; font-weight: bold;"
        elif isinstance(data, (int, float)):
            style = "color: #0d6efd;"
        elif data is None:
            style = "color: #6c757d; font-style: italic;"
            escaped_value = "None"
        return f'<code style="{style}">{escaped_value}</code>'
