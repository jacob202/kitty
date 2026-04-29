from flask import Blueprint, jsonify, request
from typing import Dict
from src.core.stuck import get_stuck_action
from src.memory.task_tracker import process_done_command

commands_bp = Blueprint('commands', __name__)

@commands_bp.route('/api/command', methods=['POST'])
def handle_command():
    data = request.get_json()
    command = data.get('command', '').strip()
    if command == '/stuck':
        action = get_stuck_action()
        return jsonify({
            "command": command,
            "response": f"Stuck? Here's your next step: {action['next_action']}",
            "action": action
        })
    if command.startswith('done '):
        result = process_done_command(command)
        return jsonify({
            "command": command,
            "response": result['response'],
            "next_task": result.get('next_task')
        })
    return jsonify({
        "command": command,
        "response": f"Unknown command: {command}",
        "action": {}
    })
