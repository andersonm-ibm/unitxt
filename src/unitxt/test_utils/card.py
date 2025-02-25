import json
import logging
import math
import os.path
import tempfile

from .. import add_to_catalog, register_local_catalog
from ..artifact import fetch_artifact
from ..metric import _compute
from ..standard import StandardRecipe
from ..templates import TemplatesDict
from ..text_utils import print_dict

TEMP_NAME = "tmp_name"


def test_adding_to_catalog(card):
    with tempfile.TemporaryDirectory() as tmp_dir:
        add_to_catalog(card, TEMP_NAME, overwrite=True, catalog_path=tmp_dir, verbose=False)
        assert os.path.exists(os.path.join(tmp_dir, TEMP_NAME + ".json")), "Card was not added to catalog"


def test_metrics_exist(card):
    for metric_name in card.task.metrics:
        metric, _ = fetch_artifact(metric_name)


def test_loading_from_catalog(card):
    with tempfile.TemporaryDirectory() as tmp_dir:
        add_to_catalog(card, TEMP_NAME, overwrite=True, catalog_path=tmp_dir, verbose=False)
        register_local_catalog(tmp_dir)
        card_, _ = fetch_artifact(TEMP_NAME)
        assert json.dumps(card_.to_dict(), sort_keys=True) == json.dumps(
            card.to_dict(), sort_keys=True
        ), "Card loaded is not equal to card stored"


def load_examples_from_standard_recipe(card, template_card_index, debug, **kwargs):
    print("*" * 80)
    print(f"Using template card index: {template_card_index}")

    if "num_demos" not in kwargs:
        kwargs["num_demos"] = 3

    if "demos_pool_size" not in kwargs:
        kwargs["demos_pool_size"] = 20

    if "loader_limit" not in kwargs:
        kwargs["loader_limit"] = 200

    recipe = StandardRecipe(card=card, template_card_index=template_card_index, **kwargs)
    if debug:
        for max_steps in range(1, recipe.num_steps() + 1):
            examples = print_recipe_output(
                recipe, max_steps=max_steps, num_examples=1, print_header=True, print_stream_size=True
            )
    else:
        examples = print_recipe_output(
            recipe,
            max_steps=recipe.num_steps(),
            num_examples=3,
            print_header=False,
            print_stream_size=False,
            streams=["test"],
        )
    return examples


def print_recipe_output(recipe, max_steps, num_examples, print_header, print_stream_size, streams=None):
    recipe.set_max_steps(max_steps)
    if print_header:
        last_step_description_dict = recipe.get_last_step_description()
        print("=" * 80)
        print("=" * 8)
        print("=" * 8, recipe.get_last_step_description())
        print("=" * 8)
    multi_stream = recipe()
    if print_stream_size:
        for stream_name in multi_stream.keys():
            stream = multi_stream[stream_name]
            num_instances = len(list(iter(stream)))
            print(f"stream named '{stream_name}' has {num_instances} instances")
        print("")
    for stream_name in multi_stream.keys():
        if streams is None or stream_name in streams:
            stream = multi_stream[stream_name]
            examples = list(stream.take(num_examples))
            print("-" * 10)
            print(f"Showing {len(examples)} example(s) from stream '{stream_name}':\n")
            for example in examples:
                print_dict(example)
                print("\n")
    return examples


def test_with_eval(card, debug=False, strict=True, exact_match_score=1.0, full_mismatch_score=0.0, **kwargs):
    if type(card.templates) is TemplatesDict:
        for template_card_index in card.templates.keys():
            examples = load_examples_from_standard_recipe(
                card, template_card_index=template_card_index, debug=debug, **kwargs
            )
    else:
        num_templates = len(card.templates)
        for template_card_index in range(0, num_templates):
            examples = load_examples_from_standard_recipe(
                card, template_card_index=template_card_index, debug=debug, **kwargs
            )

    # metric = evaluate.load('unitxt/metric')
    predictions = []
    for example in examples:
        predictions.append(example["references"][0] if len(example["references"]) > 0 else [])

    results = _compute(predictions=predictions, references=examples)
    if not exact_match_score == None and not math.isclose(
        results[0]["score"]["global"]["groups_mean_score"], exact_match_score
    ):
        message = (
            f"Metric on examples equal predicions is no {exact_match_score}, but {results[0]['score']['global']['groups_mean_score']}."
            f" If you are using matthews_correlation, it is possible that this is because all your examples come from "
            f"one class. Consider setting strict=False"
        )
        if strict:
            raise AssertionError(message)
        else:
            print(f"Warning: {message}")

    predictions = ["a1s", "bfsdf", "dgdfgs", "gfjgfh", "ghfjgh"]
    results = _compute(predictions=predictions, references=examples)
    if not full_mismatch_score == None and results[0]["score"]["global"]["groups_mean_score"] != full_mismatch_score:
        print(
            f"Warning: metric on random predictions is not {full_mismatch_score}, but {results[0]['score']['global']['groups_mean_score']} "
        )


def test_card(card, debug=False, strict=True, exact_match_score=1.0, full_mismatch_score=0.0, **kwargs):
    test_adding_to_catalog(card)
    test_metrics_exist(card)
    test_loading_from_catalog(card)
    test_with_eval(
        card,
        debug=debug,
        strict=strict,
        exact_match_score=exact_match_score,
        full_mismatch_score=full_mismatch_score,
        **kwargs,
    )
