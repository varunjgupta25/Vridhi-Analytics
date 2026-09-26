"""Optional MLflow lineage integration for reviewed synthetic experiments."""

from __future__ import annotations

from pathlib import Path

from .risk_engine import RiskEngine


def track_training(engine: RiskEngine, artifact_dir: Path, tracking_uri: str, experiment_name: str = "vridhi-synthetic-risk") -> str:
    import mlflow

    if tracking_uri.startswith("sqlite:///"):
        database_path = tracking_uri.removeprefix("sqlite:///")
        if database_path and not database_path.startswith("/"):
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as run:
        mlflow.log_params({f"model.{key}": value for key, value in engine.config.__dict__.items()})
        mlflow.log_params({"dataset.synthetic_only": True, "governance.auto_retraining": False})
        mlflow.log_metrics({key: value for key, value in engine.metrics.items() if isinstance(value, (int, float))})
        mlflow.log_artifact(str(artifact_dir / "risk_engine_metadata.json"), artifact_path="governance")
        mlflow.log_artifact(str(artifact_dir / "risk_engine.joblib"), artifact_path="model")
        return run.info.run_id
