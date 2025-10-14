"""
JoinSpec Example: Medical Diagnostic Correlation (Dashboard)

Real-world scenario: Hospital diagnostic system that correlates X-ray images
with lab results for the same patient before sending to radiologist for analysis.

JoinSpec ensures both diagnostics arrive and are correlated by patient_id
within a 5-minute window.

📊 Dashboard Features:
- Visualize X-ray and Lab result arrivals
- See correlation matching in real-time
- Track diagnostic report generation
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.subscription import JoinSpec


@flock_type
class XRayImage(BaseModel):
    patient_id: str = Field(default="patient_123", description="Unique patient identifier")
    exam_type: str = Field(default="chest_xray", description="Type of X-ray: chest, spine, etc.")
    image_quality: str = Field(default="high", description="Image quality rating")
    technician_notes: str = Field(
        default="Clear lung fields, good positioning", description="Notes from imaging technician"
    )


@flock_type
class LabResults(BaseModel):
    patient_id: str = Field(default="patient_123", description="Unique patient identifier")
    blood_work: dict = Field(
        default={"wbc": 7500, "rbc": 4.8, "platelets": 250000}, description="Blood test results"
    )
    markers: list[str] = Field(
        default=["normal_range", "no_infection"], description="Important medical markers found"
    )
    lab_notes: str = Field(
        default="No significant findings", description="Notes from lab technician"
    )


@flock_type
class DiagnosticReport(BaseModel):
    patient_id: str
    diagnosis: str
    confidence: str
    treatment_plan: str
    follow_up_needed: bool


flock = Flock()

# Radiologist agent waits for BOTH X-ray AND lab results for same patient
radiologist = (
    flock.agent("radiologist")
    .description(
        "Expert radiologist who analyzes X-ray images alongside lab results "
        "to provide comprehensive diagnostic reports. Uses JoinSpec to correlate "
        "diagnostics by patient_id within 5-minute window."
    )
    .consumes(
        XRayImage,
        LabResults,
        join=JoinSpec(
            by=lambda x: x.patient_id,  # Correlate by patient ID
            within=timedelta(minutes=5),  # Must arrive within 5 minutes
        ),
    )
    .publishes(DiagnosticReport)
)


# Start dashboard and let users publish X-rays and Lab results
# Dashboard will show correlation matching in real-time!
asyncio.run(flock.serve(dashboard=True), debug=True)
