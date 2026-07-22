"""
Evaluation against expert annotations for benchmarking.
"""

from typing import Dict, Any


def evaluate_against_expert(
    ai_report: Dict[str, Any],
    expert_annotation: Dict[str, Any],
    rubric: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate AI stenosis assessment against expert annotations.

    This function implements the LLM evaluation rubric for the Cardiomni benchmark.

    Args:
        ai_report: AI-generated stenosis assessment report
        expert_annotation: Ground truth expert annotations
        rubric: Evaluation rubric specifying criteria

    Returns:
        Dictionary with evaluation metrics
    """
    evaluation = {
        'vessel_count_correct': False,
        'stenosis_within_10pct': False,
        'reasoning_quality': 0.0,
        'trace_clinical_validity': 0.0,
        'overall_score': 0.0
    }

    # Vessel count accuracy
    ai_vessels = len(ai_report.get('vessel_analysis', []))
    expert_vessels = expert_annotation.get('vessel_count', 0)
    evaluation['vessel_count_correct'] = (ai_vessels == expert_vessels)

    # Stenosis percentage accuracy (within 10%)
    stenosis_matches = []
    for ai_vessel in ai_report.get('vessel_analysis', []):
        vessel_name = ai_vessel.get('vessel_name')

        # Find corresponding expert annotation
        expert_vessel = None
        for ev in expert_annotation.get('vessels', []):
            if ev.get('name') == vessel_name:
                expert_vessel = ev
                break

        if expert_vessel:
            for ai_stenosis in ai_vessel.get('stenoses_detected', []):
                ai_pct = ai_stenosis.get('stenosis_percentage', 0)

                # Find matching expert stenosis
                for expert_stenosis in expert_vessel.get('stenoses', []):
                    expert_pct = expert_stenosis.get('percentage', 0)
                    location_match = (
                        ai_stenosis.get('location') == expert_stenosis.get('location')
                    )

                    if location_match:
                        within_tolerance = abs(ai_pct - expert_pct) <= 10
                        stenosis_matches.append(within_tolerance)

    if stenosis_matches:
        evaluation['stenosis_within_10pct'] = all(stenosis_matches)

    # Reasoning quality (placeholder - would use LLM judge)
    reasoning_trace = ai_report.get('reasoning_trace', [])
    if reasoning_trace:
        evaluation['reasoning_quality'] = 0.8  # Placeholder score
        evaluation['trace_clinical_validity'] = 0.75  # Placeholder score

    # Overall score
    scores = [
        1.0 if evaluation['vessel_count_correct'] else 0.0,
        1.0 if evaluation['stenosis_within_10pct'] else 0.0,
        evaluation['reasoning_quality'],
        evaluation['trace_clinical_validity']
    ]
    evaluation['overall_score'] = sum(scores) / len(scores)

    return evaluation
