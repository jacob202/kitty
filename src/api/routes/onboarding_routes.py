from flask import Blueprint, request, jsonify

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

@onboarding_bp.route('/select', methods=['POST'])
def select_domains():
    """Select domains for onboarding."""
    from src.services.onboarding_pipeline import OnboardingPipeline
    
    data = request.get_json() or {}
    domains = data.get('domains', [])
    sources = data.get('sources', [])
    
    pipeline = OnboardingPipeline()
    pipeline.select_domains(domains)
    if sources:
        pipeline.select_sources(sources)
    
    return jsonify({'success': True, 'domains': domains, 'sources': sources})


@onboarding_bp.route('/start', methods=['POST'])
def start_onboarding():
    """Start the onboarding research pipeline."""
    from src.services.onboarding_pipeline import OnboardingPipeline
    
    data = request.get_json() or {}
    domains = data.get('domains', [])
    sources = data.get('sources', [])
    
    pipeline = OnboardingPipeline()
    pipeline.select_domains(domains)
    pipeline.select_sources(sources)
    result = pipeline.start()
    
    return jsonify({'success': True, 'message': result})


@onboarding_bp.route('/status', methods=['GET'])
def get_status():
    """Get onboarding status."""
    from src.services.onboarding_pipeline import OnboardingPipeline
    
    pipeline = OnboardingPipeline()
    status = pipeline.get_status()
    
    return jsonify(status)


@onboarding_bp.route('/domains', methods=['GET'])
def get_available_domains():
    """Get list of available domains."""
    return jsonify([
        {'id': 'audio', 'label': 'Audio & Music', 'icon': '🎵'},
        {'id': 'automotive', 'label': 'Automotive', 'icon': '🚗'},
        {'id': 'fitness', 'label': 'Fitness', 'icon': '💪'},
        {'id': 'health', 'label': 'Health', 'icon': '❤️'},
        {'id': 'growth', 'label': 'Growth', 'icon': '📈'},
        {'id': 'code', 'label': 'Coding', 'icon': '💻'},
        {'id': 'design', 'label': 'Design', 'icon': '🎨'},
        {'id': 'creative', 'label': 'Creative', 'icon': '🎬'},
        {'id': 'research', 'label': 'Research', 'icon': '🔬'},
        {'id': 'infrastructure', 'label': 'Infrastructure', 'icon': '🏠'},
    ])