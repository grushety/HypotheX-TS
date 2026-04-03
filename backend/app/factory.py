from flask import Flask

from app.config import Config
from app.extensions import cors, db
import app.models  # noqa: F401 - Register SQLAlchemy models before create_all.
from app.routes.audit import audit_bp
from app.routes.benchmarks import benchmarks_bp
from app.routes.health import health_bp
from app.services.suggestions import BoundarySuggestionService


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    app.instance_path = str(app.config["INSTANCE_DIR"])
    app.config["INSTANCE_DIR"].mkdir(parents=True, exist_ok=True)

    cors.init_app(
        app,
        resources={r"/api/*": {"origins": [app.config["FRONTEND_ORIGIN"]]}},
    )
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Register a single shared BoundarySuggestionService so that in-memory
    # prototype session state persists across requests within the same process.
    app.config["BOUNDARY_SUGGESTION_SERVICE"] = BoundarySuggestionService()

    app.register_blueprint(health_bp)
    app.register_blueprint(benchmarks_bp)
    app.register_blueprint(audit_bp)
    return app
