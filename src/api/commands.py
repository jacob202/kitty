from flask import Blueprint, jsonify, request

from src.core.command_engine import CommandResult, get_command_engine
from src.core.stuck import get_stuck_action
from src.memory.task_tracker import process_done_command

commands_bp = Blueprint('commands', __name__)


def _bootstrap_commands():
    engine = get_command_engine()

    def handle_stuck(args: str, **ctx):
        action = get_stuck_action()
        return CommandResult(
            success=True,
            message=f"Stuck? Here's your next step: {action['next_action']}",
            data={"command": "/stuck", "response": f"Stuck? Here's your next step: {action['next_action']}", "action": action},
        )

    def handle_done(args: str, **ctx):
        result = process_done_command(f"done {args}")
        return CommandResult(
            success=True,
            message=result['response'],
            data={"command": f"done {args}", "response": result['response'], "next_task": result.get('next_task')},
        )

    engine.register("stuck", handle_stuck, description="ADHD rescue: one concrete next step", category="core")
    engine.register("done", handle_done, description="Mark a task as completed", category="core", visible=False)


@commands_bp.route('/api/command', methods=['POST'])
def handle_command():
    _bootstrap_commands()
    data = request.get_json()
    command = data.get('command', '').strip()

    if not command.startswith("/"):
        if command.startswith("done "):
            command = f"/done {command[5:]}"
        else:
            return jsonify({"command": command, "response": f"Unknown command: {command}", "action": {}})

    engine = get_command_engine()
    result = engine.execute(command)
    return jsonify({
        "command": command,
        "response": result.message if result.success else result.error,
        "action": result.data.get("action", {}),
        "next_task": result.data.get("next_task"),
    })
