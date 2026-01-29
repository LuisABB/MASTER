"""Countries/regions routes."""
from flask import Blueprint, jsonify

countries_bp = Blueprint('countries', __name__)

# Supported regions
REGIONS = [
    {'code': 'MX', 'name': 'México'},
    {'code': 'CR', 'name': 'Costa Rica'},
    {'code': 'ES', 'name': 'España'}
]


@countries_bp.route('/regions', methods=['GET'])
def get_regions():
    """
    Get list of supported regions/countries.
    
    GET /v1/regions
    """
    return jsonify({
        'regions': REGIONS,
        'count': len(REGIONS)
    })
