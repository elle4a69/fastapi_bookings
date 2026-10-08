"""End-to-End QA Suite: Spoken Intent Normalization & Australian-English Fidelity.

Verifies:
1. Australian-English synthesis:
   - Factual prose transformation without hallucinated entities.
   - Tone synthesis (friendly, concise, zero pushy sales talk).
2. Spelling conversions:
   - Oxford/US spelling converted to Australian English (colour, centre, theatre, organise, licence, etc.).
   - Exact case preservation.
3. Unit and currency fidelity:
   - $120 AUD currency extraction with AUD qualifier.
   - 90 mins / 1.5 hours duration normalization to minutes.
   - 15 km distance extraction with metric fidelity.
4. Material ambiguity detection:
   - Ambiguous ranges or fuzzy statements trigger clarification prompts without silent guessing.
5. Correction handling:
   - Mid-dialogue corrections ("Actually, make that ninety, not sixty") invalidate prior values.
6. Zero hallucinated credentials or phantom facts:
   - Strict factual fidelity without leaking or inventing secrets/tokens.
"""

import pytest

from app.services.business_assistant.onboarding.normalizer import (
    AU_SPELLING_MAP,
    IntentNormalizer,
    NormalizedFieldResult,
)


class TestAustralianEnglishSynthesisQA:
    """Verifies Australian English synthesis and zero-hallucination contracts."""

    def test_synthesis_exact_grooming_prompt_no_hallucinations(self):
        """Verifies Section 6 benchmark:
        'It's a little mobile grooming business, mainly dogs, we go to their house.'
        Must yield: 'We provide mobile dog grooming at clients' homes.'
        No cats, horses, or phantoms permitted.
        """
        raw_text = "It's a little mobile grooming business, mainly dogs, we go to their house."
        synthesized = IntentNormalizer.synthesize_professional_text(raw_text)

        assert synthesized == "We provide mobile dog grooming at clients' homes."
        # Negative assertions against hallucinated entities
        assert "cat" not in synthesized.lower()
        assert "horse" not in synthesized.lower()
        assert "salon" not in synthesized.lower()
        assert "emergency" not in synthesized.lower()

    def test_synthesis_tone_guidance_fidelity(self):
        """Verifies tone instructions are distilled into clear behavioural guidelines."""
        raw_text = "Don't be all salesy. Friendly, short answers, and ask if you're unsure."
        synthesized = IntentNormalizer.synthesize_professional_text(raw_text)

        assert "Use a friendly, concise tone." in synthesized
        assert "Avoid pushy sales language." in synthesized
        assert "Ask a clear question when essential information is uncertain." in synthesized

    def test_spelling_conversions_exhaustive(self):
        """Verifies key Australian spelling transformations across vocabulary."""
        text = (
            "We organize our color palette at the theater center, "
            "specializing in defense licensing for traveling workers."
        )
        converted = IntentNormalizer.enforce_australian_spelling(text)
        expected = (
            "We organise our colour palette at the theatre centre, "
            "specialising in defence licensing for travelling workers."
        )
        assert converted == expected

    def test_spelling_preserves_case(self):
        """Verifies case retention across all forms (Title, UPPER, lower)."""
        assert IntentNormalizer.enforce_australian_spelling("Organize") == "Organise"
        assert IntentNormalizer.enforce_australian_spelling("ORGANIZE") == "ORGANISE"
        assert IntentNormalizer.enforce_australian_spelling("Color and Flavor") == "Colour and Flavour"
        assert IntentNormalizer.enforce_australian_spelling("THEATER CENTER") == "THEATRE CENTRE"

    def test_spelling_dictionary_integrity(self):
        """Verifies core Australian spellings in internal dictionary."""
        assert AU_SPELLING_MAP.get("color") == "colour"
        assert AU_SPELLING_MAP.get("center") == "centre"
        assert AU_SPELLING_MAP.get("organize") == "organise"
        assert AU_SPELLING_MAP.get("defense") == "defence"
        assert AU_SPELLING_MAP.get("traveling") == "travelling"


class TestUnitAndCurrencyFidelityQA:
    """Verifies exact extraction and preservation of currencies, durations, and distances."""

    @pytest.mark.parametrize(
        "utterance,expected_val,expected_qual",
        [
            ("It is $120 AUD per dog", 120, "AUD"),
            ("Charge $85.50 dollars per session", 85.50, "AUD"),
            ("Total cost is 150 AUD", 150, "AUD"),
            ("$220 for the full package", 220, "AUD"),
        ],
    )
    def test_currency_fidelity_aud(self, utterance, expected_val, expected_qual):
        res = IntentNormalizer.normalize_field("price", utterance, field_type="price")
        assert res.normalized_value == expected_val
        assert res.unit == "currency"
        assert res.qualifier == expected_qual
        assert not res.ambiguous

    @pytest.mark.parametrize(
        "utterance,expected_mins",
        [
            ("Appointments take 90 mins", 90),
            ("Appointments take 90 minutes", 90),
            ("Session lasts 1.5 hours", 90),
            ("Standard session is 60 minutes", 60),
            ("Quick wash is 45 minutes", 45),
            ("We take forty-five minutes", 45),
            ("Two hours max", 120),
        ],
    )
    def test_duration_fidelity_minutes(self, utterance, expected_mins):
        res = IntentNormalizer.normalize_field("duration", utterance, field_type="duration")
        assert res.normalized_value == expected_mins
        assert res.unit == "minutes"
        assert not res.ambiguous

    @pytest.mark.parametrize(
        "utterance,expected_dist,expected_unit",
        [
            ("We travel up to 15 km", 15, "km"),
            ("Service radius is 25 kilometres", 25, "km"),
            ("Covering within 10km of Bondi", 10, "km"),
        ],
    )
    def test_distance_fidelity_metric(self, utterance, expected_dist, expected_unit):
        val, unit, qual = IntentNormalizer.extract_number_and_units(utterance)
        assert val == expected_dist
        assert unit == expected_unit
        assert qual == "distance"


class TestMaterialAmbiguityDetectionQA:
    """Verifies material ambiguity detection prevents silent defaults and prompts for clarification."""

    def test_duration_ambiguity_no_silent_default(self):
        """A fuzzy duration must never silently default to a guess."""
        utterance = "About an hour, sometimes longer for the bigger ones."
        res = IntentNormalizer.normalize_field("duration", utterance, field_type="duration")

        assert res.ambiguous is True
        assert res.normalized_value is None
        assert res.clarification_prompt is not None
        assert "specify the standard duration" in res.clarification_prompt

    def test_price_ambiguity_range_triggers_clarification(self):
        """Pricing ranges must ask for standard or starting price."""
        utterance = "Somewhere between 80 to 120 dollars depending on the breed."
        res = IntentNormalizer.normalize_field("price", utterance, field_type="price")

        assert res.ambiguous is True
        assert res.normalized_value is None
        assert res.clarification_prompt is not None
        assert "exact standard price" in res.clarification_prompt

    def test_general_ambiguity_flag(self):
        res = IntentNormalizer.normalize_field("duration", "Maybe an hour or so, not totally sure")
        assert res.ambiguous is True


class TestCorrectionHandlingQA:
    """Verifies conversational correction handling invalidates prior values."""

    def test_correction_overwrites_prior_duration(self):
        utterance = "Actually, make that ninety, not sixty."
        res = IntentNormalizer.normalize_field(
            "duration",
            utterance,
            previous_value=60,
            field_type="duration",
        )

        assert res.is_correction is True
        assert res.normalized_value == 90
        assert res.invalidated_previous_value == 60
        assert res.unit == "minutes"

    def test_correction_overwrites_prior_price(self):
        utterance = "Actually, make it 120 AUD instead of 100."
        res = IntentNormalizer.normalize_field(
            "price",
            utterance,
            previous_value=100,
            field_type="price",
        )

        assert res.is_correction is True
        assert res.normalized_value == 120
        assert res.invalidated_previous_value == 100
        assert res.qualifier == "AUD"

    def test_correction_overwrites_business_name(self):
        utterance = "Actually, make that Frank's Canine Care instead of Frank's Paws"
        res = IntentNormalizer.normalize_field(
            "business_name",
            utterance,
            previous_value="Frank's Paws",
            field_type="string",
        )

        assert res.is_correction is True
        assert "Frank's Canine Care" in str(res.normalized_value)
        assert res.invalidated_previous_value == "Frank's Paws"


class TestZeroHallucinatedCredentialsQA:
    """Verifies that no hallucinated secrets, keys, or credentials can enter normalized fields."""

    def test_no_credential_hallucination_in_normalization(self):
        utterances = [
            "We are a mobile grooming service in Melbourne.",
            "Our phone is 0412 345 678 and email is hello@example.com.au.",
            "We offer bath and wash for $120 AUD.",
        ]
        forbidden_tokens = ["api_key", "secret", "password", "bearer", "token", "livekit_key"]

        for u in utterances:
            result = IntentNormalizer.normalize_field("description", u)
            val_str = str(result.normalized_value).lower()
            for token in forbidden_tokens:
                assert token not in val_str

    def test_no_credential_hallucination_in_synthesis(self):
        utterance = "We provide mobile wash and grooming for small to large dogs."
        synthesized = IntentNormalizer.synthesize_professional_text(utterance)
        forbidden_tokens = ["secret", "bearer", "jwt", "apikey", "password"]
        for token in forbidden_tokens:
            assert token not in synthesized.lower()
