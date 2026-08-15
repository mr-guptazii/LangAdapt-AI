"""Scoring functions for the evaluation framework — plain multiset precision/
recall/F1 over detected-error categories. Order doesn't matter (a sentence
with two past-tense errors is satisfied by two categories in any order); an
extra unexpected category counts against precision, a missing one against recall.
"""
from collections import Counter
from dataclasses import dataclass


@dataclass
class PRF1:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int


def precision_recall_f1(expected: list[str], predicted: list[str]) -> PRF1:
    expected_counts = Counter(expected)
    predicted_counts = Counter(predicted)

    tp = sum((expected_counts & predicted_counts).values())
    fp = sum((predicted_counts - expected_counts).values())
    fn = sum((expected_counts - predicted_counts).values())

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fp == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return PRF1(precision=round(precision, 3), recall=round(recall, 3), f1=round(f1, 3), true_positives=tp, false_positives=fp, false_negatives=fn)
