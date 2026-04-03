from flask import Blueprint

sspr_bp = Blueprint("sspr", __name__, template_folder="../../templates/sspr")

from app.blueprints.sspr import routes  # noqa: E402, F401
