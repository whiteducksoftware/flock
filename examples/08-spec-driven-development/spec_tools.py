"""
Custom Flock Tools for Spec-Driven Development

These tools enable agents to manage specifications, create directories,
and write structured documentation following the devflow pattern.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from flock.registry import flock_tool


# ==============================================================================
# SPEC MANAGEMENT TOOLS
# ==============================================================================


@flock_tool
def create_spec_directory(feature_description: str) -> dict[str, str]:
    """
    Create a new specification directory with a unique ID.

    Generates a spec ID (e.g., S001, S002, etc.) and creates the directory
    structure for PRD, SDD, and PLAN documents.

    Args:
        feature_description: Brief description of the feature being specified

    Returns:
        dict with spec_id, spec_dir, and template_paths
    """
    # Find the highest existing spec ID
    specs_dir = Path(".flock/specs")
    specs_dir.mkdir(parents=True, exist_ok=True)

    existing_specs = list(specs_dir.glob("S*"))
    if existing_specs:
        spec_nums = [
            int(re.search(r"S(\d+)", d.name).group(1))
            for d in existing_specs
            if re.search(r"S(\d+)", d.name)
        ]
        next_num = max(spec_nums) + 1 if spec_nums else 1
    else:
        next_num = 1

    spec_id = f"S{next_num:03d}"
    spec_dir = specs_dir / spec_id
    spec_dir.mkdir(exist_ok=True)

    # Create initial files from templates
    prd_path = spec_dir / "PRD.md"
    sdd_path = spec_dir / "SDD.md"
    plan_path = spec_dir / "PLAN.md"

    # Initialize PRD with header
    prd_path.write_text(
        f"""# Product Requirements Document (PRD)

**Spec ID:** {spec_id}
**Feature:** {feature_description}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Status:** Draft

---

""",
        encoding="utf-8",
    )

    # Initialize SDD with header
    sdd_path.write_text(
        f"""# Solution Design Document (SDD)

**Spec ID:** {spec_id}
**Feature:** {feature_description}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Status:** Draft

---

""",
        encoding="utf-8",
    )

    # Initialize PLAN with header
    plan_path.write_text(
        f"""# Implementation Plan

**Spec ID:** {spec_id}
**Feature:** {feature_description}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Status:** Draft

---

""",
        encoding="utf-8",
    )

    return {
        "spec_id": spec_id,
        "spec_dir": str(spec_dir),
        "prd_path": str(prd_path),
        "sdd_path": str(sdd_path),
        "plan_path": str(plan_path),
    }


@flock_tool
def append_to_document(
    file_path: str, content: str, section_name: str | None = None
) -> str:
    """
    Append content to a specification document.

    Args:
        file_path: Path to the document (PRD.md, SDD.md, or PLAN.md)
        content: Markdown content to append
        section_name: Optional section name to add before content

    Returns:
        Success message with updated file path
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    existing_content = path.read_text(encoding="utf-8")

    # Add section header if provided
    if section_name:
        new_content = f"\n\n## {section_name}\n\n{content}\n"
    else:
        new_content = f"\n\n{content}\n"

    path.write_text(existing_content + new_content, encoding="utf-8")

    return f"Appended to {path.name}: {len(content)} characters"


@flock_tool
def read_document(file_path: str) -> str:
    """
    Read the contents of a specification document.

    Args:
        file_path: Path to the document to read

    Returns:
        Document contents as string
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    return path.read_text(encoding="utf-8")


@flock_tool
def list_specs() -> list[dict[str, str]]:
    """
    List all existing specifications.

    Returns:
        List of dicts with spec_id, spec_dir, and status
    """
    specs_dir = Path(".flock/specs")
    if not specs_dir.exists():
        return []

    specs = []
    for spec_dir in sorted(specs_dir.glob("S*")):
        if spec_dir.is_dir():
            # Try to extract feature name from PRD
            prd_path = spec_dir / "PRD.md"
            feature = "Unknown"
            if prd_path.exists():
                content = prd_path.read_text(encoding="utf-8")
                match = re.search(r"\*\*Feature:\*\*\s*(.+)", content)
                if match:
                    feature = match.group(1).strip()

            specs.append(
                {
                    "spec_id": spec_dir.name,
                    "spec_dir": str(spec_dir),
                    "feature": feature,
                }
            )

    return specs


@flock_tool
def finalize_spec(spec_id: str, confidence: Literal["high", "medium", "low"]) -> str:
    """
    Mark a specification as complete and ready for implementation.

    Args:
        spec_id: The spec ID (e.g., S001)
        confidence: Confidence level in the specification

    Returns:
        Success message
    """
    specs_dir = Path(".flock/specs")
    spec_dir = specs_dir / spec_id

    if not spec_dir.exists():
        raise FileNotFoundError(f"Spec directory not found: {spec_id}")

    # Update all documents to mark as complete
    for doc_name in ["PRD.md", "SDD.md", "PLAN.md"]:
        doc_path = spec_dir / doc_name
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            # Update status line
            content = re.sub(
                r"\*\*Status:\*\*\s*\w+",
                f"**Status:** Complete ({confidence} confidence)",
                content,
            )
            doc_path.write_text(content, encoding="utf-8")

    # Create a COMPLETE marker file
    complete_marker = spec_dir / ".complete"
    complete_marker.write_text(
        f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Confidence: {confidence}\n",
        encoding="utf-8",
    )

    return f"Spec {spec_id} marked as complete with {confidence} confidence"


# ==============================================================================
# RESEARCH TOOLS
# ==============================================================================


@flock_tool
def format_research_findings(
    research_type: str, findings: str, insights: list[str], recommendations: list[str]
) -> str:
    """
    Format research findings into a structured markdown section.

    Args:
        research_type: Type of research (market, technical, security, ux)
        findings: Main findings text
        insights: List of key insights
        recommendations: List of recommendations

    Returns:
        Formatted markdown string
    """
    output = f"### {research_type.title()} Research\n\n"
    output += f"{findings}\n\n"

    if insights:
        output += "**Key Insights:**\n"
        for insight in insights:
            output += f"- {insight}\n"
        output += "\n"

    if recommendations:
        output += "**Recommendations:**\n"
        for rec in recommendations:
            output += f"- {rec}\n"
        output += "\n"

    return output


# ==============================================================================
# IMPLEMENTATION TOOLS
# ==============================================================================


@flock_tool
def parse_plan_phases(plan_path: str) -> list[dict]:
    """
    Parse a PLAN.md file and extract phases with tasks.

    Args:
        plan_path: Path to PLAN.md file

    Returns:
        List of dicts with phase_number, description, tasks
    """
    path = Path(plan_path)
    if not path.exists():
        raise FileNotFoundError(f"Plan not found: {plan_path}")

    content = path.read_text(encoding="utf-8")

    # Simple parser for phases (assumes format: ## Phase N: Description)
    phases = []
    current_phase = None

    for line in content.split("\n"):
        # Match phase headers
        phase_match = re.match(r"##\s+Phase\s+(\d+):\s*(.+)", line)
        if phase_match:
            if current_phase:
                phases.append(current_phase)
            current_phase = {
                "phase_number": int(phase_match.group(1)),
                "description": phase_match.group(2).strip(),
                "tasks": [],
            }
            continue

        # Match task items
        if current_phase and re.match(r"^[-*]\s+", line):
            task = line.strip().lstrip("-* ").strip()
            if task:
                current_phase["tasks"].append(task)

    if current_phase:
        phases.append(current_phase)

    return phases


@flock_tool
def get_current_date() -> str:
    """
    Get the current date in YYYY-MM-DD format.

    Returns:
        Current date string
    """
    return datetime.now().strftime("%Y-%m-%d")


@flock_tool
def get_current_datetime() -> str:
    """
    Get the current date and time in YYYY-MM-DD HH:MM:SS format.

    Returns:
        Current datetime string
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
