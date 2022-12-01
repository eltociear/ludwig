"""Validation checks that are not easily covered by marshmallow schemas like parameter interdependencies.

As these are built out, these auxiliary validations can be gradually removed.
"""
from threading import Lock
from typing import Any, Dict, List

from jsonschema import validate

from ludwig.api_annotations import DeveloperAPI
from ludwig.constants import (
    COMBINED,
    LOSS,
    MODEL_ECD,
    MODEL_TYPE,
    NAME,
    OUTPUT_FEATURES,
    PREPROCESSING,
    SPLIT,
    TRAINER,
    TYPE,
)
from ludwig.features.feature_registries import output_type_registry
from ludwig.schema import get_schema, get_validator

VALIDATION_LOCK = Lock()


def check_feature_names_unique(config: Dict[str, Any]) -> None:
    """Checks that all feature names are unique."""
    pass


def check_tied_features_are_valid(config: Dict[str, Any]) -> None:
    """Checks that all 'tied' parameters map to existing input feature names."""
    pass


def check_dependent_features(config: Dict[str, Any]) -> None:
    """Checks that 'dependent' features map to existing output features, and no circular dependencies."""


def check_training_runway(config: Dict[str, Any]) -> None:
    """Checks that checkpoints_per_epoch and steps_per_checkpoint aren't simultaneously defined."""
    pass


def check_gbm_horovod_incompatibility(config: Dict[str, Any]) -> None:
    """Checks that GBM model type isn't being used with the horovod backend."""
    pass


def check_gbm_feature_types(config: Dict[str, Any]) -> None:
    """Checks that only tabular features are used with GBM models."""
    pass


def check_ray_backend_in_memory_preprocessing(config: Dict[str, Any]) -> None:
    """Checks if it's a ray backend, then feature[preprocessing][in_memory] must be true."""
    pass


def check_sequence_concat_combiner_requirements(config: Dict[str, Any]) -> None:
    """Checks sequence concat combiner requirements.

    At least one of the input features should be a sequence feature.
    """
    pass


def check_tabtransformer_combiner_requirements(config: Dict[str, Any]) -> None:
    """Checks TabTransformer requirements.

    reduce_output cannot be None.
    """
    pass


def check_comparator_combiner_requirements(config: Dict[str, Any]) -> None:
    """Checks ComparatorCombiner requirements.

    All of the feature names for entity_1 and entity_2 are valid features.
    """
    pass


def check_class_balance_preprocessing(config: Dict[str, Any]) -> None:
    """Class balancing is only available for datasets with a single output feature."""
    pass


def check_sampling_exclusivity(config: Dict[str, Any]) -> None:
    """Oversample minority and undersample majority are mutually exclusive."""
    pass


def check_hyperopt_search_space(config: Dict[str, Any]) -> None:
    """Check that all hyperopt parameters search spaces are valid."""
    pass


def check_hyperopt_metric_targets(config: Dict[str, Any]) -> None:
    """Check that hyperopt metric targets are valid."""
    pass


def check_gbm_single_output_feature(config: Dict[str, Any]) -> None:
    """GBM models only support a single output feature."""
    pass


def get_feature_to_metric_names_map(output_features: List[Dict]) -> Dict[str, List[str]]:
    """Returns a dict of output_feature_name -> list of metric names."""
    metrics_names = {}
    for output_feature in output_features:
        output_feature_name = output_feature[NAME]
        output_feature_type = output_feature[TYPE]
        metrics_names[output_feature_name] = output_type_registry[output_feature_type].metric_functions
    metrics_names[COMBINED] = [LOSS]
    return metrics_names


def check_validation_metrics_are_valid(config: Dict[str, Any]) -> None:
    """Checks that validation fields in config.trainer are valid."""
    output_features = config[OUTPUT_FEATURES]
    feature_to_metric_names_map = get_feature_to_metric_names_map(output_features)

    validation_field = config[TRAINER]["validation_field"]
    validation_metric = config[TRAINER]["validation_metric"]

    # Check validation_field.
    if validation_field not in feature_to_metric_names_map.keys():
        raise ValueError(
            f"The specified trainer.validation_field '{validation_field}' is not valid. "
            f"Available validation fields are: {list(feature_to_metric_names_map.keys())}"
        )

    # Check validation_metric.
    valid_validation_metric = validation_metric in feature_to_metric_names_map[validation_field]
    if not valid_validation_metric:
        raise ValueError(
            f"The specified trainer.validation_metric '{validation_metric}' is not valid for the"
            f"trainer.validation_field '{validation_field}'. "
            f"Available (validation_field, validation_metric) pairs are {feature_to_metric_names_map}"
        )


@DeveloperAPI
def validate_config(config: Dict[str, Any], include_auxiliary_validations=True):
    # Update config from previous versions to check that backwards compatibility will enable a valid config
    # NOTE: import here to prevent circular import
    from ludwig.data.split import get_splitter
    from ludwig.utils.backward_compatibility import upgrade_config_dict_to_latest_version

    # Update config from previous versions to check that backwards compatibility will enable a valid config
    updated_config = upgrade_config_dict_to_latest_version(config)
    model_type = updated_config.get(MODEL_TYPE, MODEL_ECD)

    with VALIDATION_LOCK:
        # There is a race condition during schema validation that can cause the marshmallow schema class to
        # be missing during validation if more than one thread is trying to validate at once.
        validate(instance=updated_config, schema=get_schema(model_type=model_type), cls=get_validator())

    # Additional checks.
    if include_auxiliary_validations:
        splitter = get_splitter(**updated_config.get(PREPROCESSING, {}).get(SPLIT, {}))
        splitter.validate(updated_config)

        check_validation_metrics_are_valid(updated_config)
        check_feature_names_unique(updated_config)
        check_tied_features_are_valid(updated_config)
        check_dependent_features(updated_config)
        check_training_runway(updated_config)
        check_gbm_horovod_incompatibility(updated_config)
        check_gbm_feature_types(updated_config)
        check_ray_backend_in_memory_preprocessing(updated_config)
        check_sequence_concat_combiner_requirements(updated_config)
        check_tabtransformer_combiner_requirements(updated_config)
        check_comparator_combiner_requirements(updated_config)
        check_class_balance_preprocessing(updated_config)
        check_sampling_exclusivity(updated_config)
        check_hyperopt_search_space(updated_config)
        check_hyperopt_metric_targets(updated_config)
        check_gbm_single_output_feature(updated_config)
