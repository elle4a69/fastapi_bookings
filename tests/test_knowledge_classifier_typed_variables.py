"""Regression tests for typed-variable and promotion safety boundaries."""

from app.services.knowledge.classifier import (
    ClassificationCategory,
    assess_typed_variables,
    classify_curated_memory_candidate,
    classify_proposed_knowledge,
    classify_style_example,
)


def test_only_safe_business_context_variables_are_allowed_in_new_examples():
    assessment = assess_typed_variables(
        "We cover {service_area}; I can check options for {service_name} at {location_name}."
    )

    assert assessment.is_safe is True
    assert assessment.variables == {"service_area", "service_name", "location_name"}


def test_live_operational_and_customer_variables_cannot_be_normalised_into_memory():
    for text in (
        "I can reserve {appointment_time} for you.",
        "The total is {price}.",
        "I will visit {customer_address}.",
        "Please call {customer_phone}.",
        "Customer details: [ADDRESS]",
    ):
        assessment = assess_typed_variables(text)
        assert assessment.is_safe is False


def test_literal_slot_and_redacted_address_are_rejected_from_reusable_learning():
    dynamic = classify_style_example(
        "Can I come tomorrow at 3pm?",
        "Yes, I have an open slot available tomorrow at 3pm.",
    )
    redacted = classify_proposed_knowledge("The business is located at [ADDRESS].")

    assert dynamic.is_safe is False
    assert dynamic.category == ClassificationCategory.DYNAMIC_OPERATIONAL
    assert redacted.is_safe is False
    assert redacted.category == ClassificationCategory.DYNAMIC_OPERATIONAL


def test_memory_promotion_checks_query_as_well_as_response():
    result = classify_curated_memory_candidate(
        "Can you visit 14 Example Street tomorrow at 3pm?",
        "We offer mobile appointments across the service area.",
    )

    assert result.is_safe is False


def test_durable_fact_with_safe_business_variables_remains_rejected_as_procedural():
    result = classify_proposed_knowledge(
        "Can I use {booking_link} to make a booking?"
    )

    assert result.is_safe is False
    assert result.category == ClassificationCategory.PROCEDURAL_EXAMPLE
