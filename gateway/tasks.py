import logging
import re

from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.tasks")

TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def sync_next_action(action_description: str) -> bool:
    """
    Surgically update the 'Next Smallest Action' in TASKS.md.
    This helps close the 'Execution Gap' by recording chat decisions immediately.
    """
    if not TASKS_PATH.exists():
        logger.error("TASKS.md not found at %s", TASKS_PATH)
        return False

    try:
        content = TASKS_PATH.read_text()

        # Look for the section after ## Next Smallest Action
        # Pattern: ## Next Smallest Action\n\n[Existing Action]
        section_header = "## Next Smallest Action"

        if section_header not in content:
            # Append it if it somehow went missing
            new_content = content.rstrip() + f"\n\n{section_header}\n\n- {action_description}\n"
        else:
            # Replace the existing first item or the entire section until the next header
            parts = content.split(section_header)
            prefix = parts[0]
            suffix = parts[1].lstrip()

            # Find the end of the next-action block (usually double newline or next header)
            # We'll just replace the first paragraph after the header
            remaining_parts = re.split(r"\n\n|\n#", suffix, 1)
            rest = remaining_parts[1] if len(remaining_parts) > 1 else ""

            # Reconstruct
            connector = "\n\n" if not rest.startswith("#") else "\n\n"
            new_content = f"{prefix}{section_header}\n\n- {action_description}{connector}{rest}"

        TASKS_PATH.write_text(new_content)
        logger.info("Successfully synced next action: %s", action_description)
        return True

    except Exception as e:
        logger.error("Failed to sync task to TASKS.md: %s", e)
        return False
