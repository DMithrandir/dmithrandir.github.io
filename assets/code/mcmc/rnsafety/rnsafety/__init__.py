"""Reverse-noise safety audit toolkit.

Public API::

    from rnsafety import audit_stream, AuditReport, make_sample

    sample = make_sample("reverse_spike", n_steps=512, dim=256, seed=0)
    report = audit_stream(sample)
    print(report.verdict, report.risk_score)
"""

from __future__ import annotations

from .core import (  # noqa: F401
    DetectionCertificate,
    ReverseNoiseStats,
    SpectralReport,
    UpdateStats,
    cosine,
    detection_certificate,
    describe_reverse_noise,
    effective_condition_number,
    gradient_loss_increment,
    noise_benefit_increment,
    noise_benefit_condition_boundary,
    noise_covariance,
    quadratic_loss_increment,
    required_alignment_for_power,
    reverse_score,
    spectral_report,
    update_identity_terms,
)
from .generate import FAMILIES, AttackSpec, gradient_stream, make_stream  # noqa: F401
from .audit import (  # noqa: F401
    AuditReport,
    Baseline,
    MonitorResult,
    audit_samples,
    audit_stream,
    fit_baseline,
)

make_sample = make_stream

__all__ = [
    "audit_stream",
    "audit_samples",
    "AuditReport",
    "Baseline",
    "MonitorResult",
    "fit_baseline",
    "make_sample",
    "make_stream",
    "gradient_stream",
    "AttackSpec",
    "FAMILIES",
    "ReverseNoiseStats",
    "UpdateStats",
    "DetectionCertificate",
    "SpectralReport",
    "cosine",
    "reverse_score",
    "describe_reverse_noise",
    "detection_certificate",
    "spectral_report",
    "effective_condition_number",
    "noise_covariance",
    "update_identity_terms",
    "quadratic_loss_increment",
    "gradient_loss_increment",
    "noise_benefit_increment",
    "noise_benefit_condition_boundary",
    "required_alignment_for_power",
]

__version__ = "0.1.0"
