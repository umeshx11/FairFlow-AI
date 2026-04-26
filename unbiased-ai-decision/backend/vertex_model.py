from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
try:
    from google.cloud import aiplatform, storage
except ImportError:
    aiplatform = None
    storage = None
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from bias_analyzer import PreparedDataset
from schemas import DomainName


VERTEX_REQUIRED_ENV = (
    "VERTEX_PROJECT_ID",
    "VERTEX_REGION",
    "VERTEX_STAGING_BUCKET",
    "VERTEX_MODEL_BUCKET",
)


@dataclass(slots=True)
class TrainedModelBundle:
    domain: DomainName
    pipeline: Pipeline
    local_dir: Path
    model_path: Path
    metadata_path: Path
    feature_columns: list[str]
    model_family: str
    artifact_uri: str | None = None
    vertex_model_name: str | None = None
    endpoint_name: str | None = None


def use_vertex_ai() -> bool:
    return os.getenv("USE_VERTEX_AI", "false").strip().lower() == "true"


def vertex_sdk_available() -> bool:
    return aiplatform is not None and storage is not None


def validate_vertex_environment() -> None:
    if not use_vertex_ai():
        return
    if not vertex_sdk_available():
        raise RuntimeError(
            "Vertex AI is enabled but the Google Cloud Vertex SDK dependencies are not installed."
        )
    missing = [name for name in VERTEX_REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Vertex AI is enabled but not fully configured. Missing: " + ", ".join(missing)
        )


def _serving_image_uri() -> str:
    return os.getenv(
        "VERTEX_SERVING_IMAGE_URI",
        "us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-5:latest",
    )


def _bucket_name_from_uri(uri: str) -> str:
    return uri.replace("gs://", "").split("/", 1)[0]


def _prefix_from_uri(uri: str) -> str:
    parts = uri.replace("gs://", "").split("/", 1)
    return parts[1].rstrip("/") if len(parts) > 1 else ""


def _init_vertex() -> None:
    if not vertex_sdk_available():
        raise RuntimeError("Vertex AI SDK dependencies are not installed.")
    aiplatform.init(
        project=os.environ["VERTEX_PROJECT_ID"],
        location=os.environ["VERTEX_REGION"],
        staging_bucket=os.environ["VERTEX_STAGING_BUCKET"],
    )


def _storage_client() -> Any:
    if storage is None:
        raise RuntimeError("Google Cloud Storage SDK dependency is not installed.")
    return storage.Client(project=os.environ["VERTEX_PROJECT_ID"])


def train_domain_random_forest(prepared: PreparedDataset, audit_id: str) -> TrainedModelBundle:
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=250,
                    min_samples_leaf=2,
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(prepared.feature_frame, prepared.labels)

    local_dir = Path(tempfile.mkdtemp(prefix=f"fairflow-{audit_id}-"))
    model_path = local_dir / "model.joblib"
    metadata_path = local_dir / "metadata.json"
    joblib.dump(pipeline, model_path)
    metadata_path.write_text(
        json.dumps(
            {
                "domain": prepared.domain,
                "feature_columns": prepared.feature_columns,
                "target_column": prepared.target_column,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return TrainedModelBundle(
        domain=prepared.domain,
        pipeline=pipeline,
        local_dir=local_dir,
        model_path=model_path,
        metadata_path=metadata_path,
        feature_columns=prepared.feature_columns,
        model_family=f"{prepared.domain}_random_forest",
    )


def _upload_directory(bundle: TrainedModelBundle, audit_id: str) -> str:
    model_bucket_uri = os.environ["VERTEX_MODEL_BUCKET"]
    bucket_name = _bucket_name_from_uri(model_bucket_uri)
    prefix = _prefix_from_uri(model_bucket_uri)
    artifact_prefix = "/".join(part for part in (prefix, "fairflow-models", audit_id) if part)
    bucket = _storage_client().bucket(bucket_name)

    for local_path in bundle.local_dir.iterdir():
        blob = bucket.blob(f"{artifact_prefix}/{local_path.name}")
        blob.upload_from_filename(str(local_path))

    return f"gs://{bucket_name}/{artifact_prefix}"


def _find_existing_endpoint(display_name: str):
    try:
        matches = aiplatform.Endpoint.list(filter=f'display_name="{display_name}"')
    except Exception:
        matches = []
    return matches[0] if matches else None


def register_and_deploy_model(bundle: TrainedModelBundle, audit_id: str) -> TrainedModelBundle:
    if not use_vertex_ai():
        return bundle

    _init_vertex()
    artifact_uri = _upload_directory(bundle, audit_id)
    model = aiplatform.Model.upload(
        display_name=f"fairflow-{bundle.domain}-{audit_id}",
        artifact_uri=artifact_uri,
        serving_container_image_uri=_serving_image_uri(),
        sync=True,
    )

    endpoint_display_name = f"fairflow-{bundle.domain}-endpoint"
    endpoint = _find_existing_endpoint(endpoint_display_name)
    if endpoint is None:
        endpoint = aiplatform.Endpoint.create(display_name=endpoint_display_name, sync=True)

    model.deploy(
        endpoint=endpoint,
        deployed_model_display_name=f"fairflow-{bundle.domain}-{audit_id}",
        machine_type=os.getenv("VERTEX_MACHINE_TYPE", "n1-standard-2"),
        traffic_percentage=100,
        sync=True,
    )

    bundle.artifact_uri = artifact_uri
    bundle.vertex_model_name = model.resource_name
    bundle.endpoint_name = endpoint.resource_name
    return bundle


def train_register_and_deploy(prepared: PreparedDataset, audit_id: str) -> TrainedModelBundle:
    bundle = train_domain_random_forest(prepared, audit_id)
    return register_and_deploy_model(bundle, audit_id)


def predict_with_endpoint(endpoint_name: str, feature_frame) -> tuple[np.ndarray, np.ndarray]:
    _init_vertex()
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_name)
    instances = feature_frame.astype(float).to_dict(orient="records")
    response = endpoint.predict(instances=instances)
    predictions: list[int] = []
    probabilities: list[float] = []
    for item in response.predictions:
        if isinstance(item, dict):
            probability = float(
                item.get("probability", item.get("score", item.get("positive_probability", 0.0)))
            )
            prediction = item.get("prediction", item.get("label"))
            if prediction is None:
                prediction = int(probability >= 0.5)
            if isinstance(prediction, str):
                prediction = 1 if prediction.lower() in {"1", "true", "yes", "approved", "hired", "treated"} else 0
            predictions.append(int(prediction))
            probabilities.append(probability)
        else:
            probability = float(item)
            predictions.append(int(probability >= 0.5))
            probabilities.append(probability)
    return np.asarray(predictions).astype(int), np.asarray(probabilities).astype(float)


def cleanup_bundle(bundle: TrainedModelBundle) -> None:
    shutil.rmtree(bundle.local_dir, ignore_errors=True)
