"""Arm E0: a RAPTURE-style extraction verifier. This is prior art, not our method.

Reproduces Kushmerick, "Regression testing for wrapper maintenance", AAAI-99, from
the paper's own Figure 2 and feature list. Comments mark where the paper specifies
behaviour, where reproduction required a choice, and where we deliberately differ.

PAPER-SPECIFIED
  - The nine features and their definitions, with the paper's worked values for the
    string '20 Maple St.' reproduced in the tests.
  - Feature values per (feature, attribute) are treated as normally distributed;
    parameters are the mean and standard deviation over previously verified labels.
  - A label's verification probability is the combination of the per-value normal
    densities plus the density of the tuple count.
  - Three dependency assumptions: independence (product), entailment (min),
    equivalence (geometric mean). The paper reports equivalence generally best, and
    HTML density alone as the strongest single feature.
  - The decision compares the cumulative normal probability of the label's
    verification probability, under parameters fitted to the verified labels, against
    a threshold tau. tau = 1/2 is "reject if v is below the verified mean".
  - Footnote 1: a wrapper whose execution is undefined is rejected immediately.

REASONABLE REPRODUCTION CHOICE
  - Zero variance: the paper prints P = 1.0 for a feature whose verified values are
    all identical (its code word-count column), which a normal density cannot give.
    We return 1.0 on an exact match and 0.0 otherwise.
  - A label here is a single tuple of (name, price, currency), so the tuple-count
    term is constant. It is kept for faithfulness rather than dropped.
  - Attribute values are stringified before features are computed, since the paper's
    features are defined over extracted text.

OUR MODIFICATION
  - None. Features, combination, and decision rule are as published. E0 is measured
    before it is improved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import erf, exp, pi, prod, sqrt
from statistics import fmean, pstdev

# The paper's nine features, with its worked values for '20 Maple St.' in the tests.
FEATURES: dict[str, Callable[[str], float]] = {
    "digit_density": lambda s: _density(s, str.isdigit),
    "letter_density": lambda s: _density(s, str.isalpha),
    "upper_density": lambda s: _density(s, str.isupper),
    "lower_density": lambda s: _density(s, str.islower),
    "punctuation_density": lambda s: _density(s, _is_punctuation),
    "html_density": lambda s: _density(s, lambda c: c in "<>"),
    "length": lambda s: float(len(s)),
    "word_count": lambda s: float(len(s.split())),
    "mean_word_length": lambda s: fmean([len(w) for w in s.split()]) if s.split() else 0.0,
}

ALL_FEATURES = tuple(FEATURES)
# The paper's strongest single feature (its settings 9 and 22).
HTML_DENSITY_ONLY = ("html_density",)

DEPENDENCY_ASSUMPTIONS: dict[str, Callable[[Sequence[float]], float]] = {
    "independence": prod,
    "entailment": min,
    "equivalence": lambda ps: prod(ps) ** (1 / len(ps)),
}


def _density(text: str, predicate: Callable[[str], bool]) -> float:
    if not text:
        return 0.0
    return sum(1 for char in text if predicate(char)) / len(text)


def _is_punctuation(char: str) -> bool:
    return not char.isalnum() and not char.isspace()


def _normal_density(value: float, mean: float, deviation: float) -> float:
    if deviation == 0:
        return 1.0 if value == mean else 0.0
    return exp(-0.5 * ((value - mean) / deviation) ** 2) / (deviation * sqrt(2 * pi))


def _normal_cumulative(value: float, mean: float, deviation: float) -> float:
    if deviation == 0:
        return 1.0 if value >= mean else 0.0
    return 0.5 * (1 + erf((value - mean) / (deviation * sqrt(2))))


@dataclass(frozen=True)
class RaptureVerifier:
    """Fitted verifier. Holds only distribution parameters, never any ground truth."""

    fields: tuple[str, ...]
    features: tuple[str, ...]
    combine: str
    feature_params: dict[tuple[str, str], tuple[float, float]]
    tuple_count_params: tuple[float, float]
    verification_params: tuple[float, float]

    def verification_probability(self, record: Mapping[str, object]) -> float:
        """The paper's VERIFPR: combine per-value densities into one probability."""
        mean, deviation = self.tuple_count_params
        densities = [_normal_density(1.0, mean, deviation)]
        for feature in self.features:
            for field in self.fields:
                value = FEATURES[feature](str(record[field]))
                densities.append(_normal_density(value, *self.feature_params[feature, field]))
        return DEPENDENCY_ASSUMPTIONS[self.combine](densities)

    def accepts(self, record: Mapping[str, object], tau: float) -> bool:
        """The paper's RAPTURE: reject when the label probability does not exceed tau.

        A record missing any required field is rejected outright, which is the paper's
        treatment of a wrapper whose execution is undefined.
        """
        if any(record.get(field) in (None, "") for field in self.fields):
            return False
        probability = _normal_cumulative(
            self.verification_probability(record), *self.verification_params
        )
        return probability > tau


def fit(
    reference: Sequence[Mapping[str, object]],
    *,
    fields: Sequence[str],
    features: Sequence[str] = ALL_FEATURES,
    combine: str = "equivalence",
) -> RaptureVerifier:
    """Fit from previously verified extractions only. Ground truth is never an input."""
    if not reference:
        raise ValueError("RAPTURE needs at least one previously verified label")

    feature_params = {
        (feature, field): _parameters(
            [FEATURES[feature](str(record[field])) for record in reference]
        )
        for feature in features
        for field in fields
    }
    verifier = RaptureVerifier(
        fields=tuple(fields),
        features=tuple(features),
        combine=combine,
        feature_params=feature_params,
        # Every fixture yields exactly one tuple per page, so this term is constant.
        tuple_count_params=(1.0, 0.0),
        verification_params=(0.0, 0.0),
    )
    # VERIFPRPARAMS: the verified labels' own verification probabilities set the scale
    # the decision threshold is applied against.
    probabilities = [verifier.verification_probability(record) for record in reference]
    return RaptureVerifier(
        fields=verifier.fields,
        features=verifier.features,
        combine=combine,
        feature_params=feature_params,
        tuple_count_params=verifier.tuple_count_params,
        verification_params=_parameters(probabilities),
    )


def _parameters(values: Sequence[float]) -> tuple[float, float]:
    return fmean(values), pstdev(values)
