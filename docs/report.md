# Project report

## Objective

Explore a camera-assisted accessory recommendation workflow that combines face recognition, mask/glasses classification, and weather context.

## Implemented scope

The repository includes a Flask web application, a separate inference service, local model-training scripts, weather integration, and administrative history/reporting workflows. See [architecture](architecture.md) for component responsibilities and [setup](../SETUP.md) for configuration.

## Evaluation requirements

A reproducible model evaluation should record the dataset source and license, subject-disjoint split strategy, class balance, preprocessing, model version, decision thresholds, and per-class precision/recall. Assess performance under different lighting, camera positions, and accessory styles. Face recognition and accessory classification need separate evaluation.

No new accuracy, latency, or availability measurements are asserted in this report. Preserve experiment results with their configuration and hardware details before making performance claims.

## Remaining work

- Validate model quality on held-out subjects and realistic camera conditions.
- Exercise registration, recognition, unknown-face handling, and administrative operations end to end.
- Document deployment-specific consent, retention, and deletion behavior.
- Measure inference latency and service recovery after cold starts or network failures.
