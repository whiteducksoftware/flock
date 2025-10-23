"""
Getting Started: Medical Diagnostics with JoinSpec

This example demonstrates JoinSpec: correlating multiple artifact types (X-ray + Lab results)
for the same entity (patient) before processing together.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.core.subscription import JoinSpec
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class XRayImage(BaseModel):
    patient_id: str
    exam_type: str = Field(description="Type of X-ray: chest, spine, etc.")
    image_quality: str = Field(description="Image quality rating")
    technician_notes: str = Field(description="Notes from imaging technician")


@flock_type
class LabResults(BaseModel):
    patient_id: str
    blood_work: dict = Field(description="Blood test results")
    markers: list[str] = Field(description="Important medical markers found")
    lab_notes: str = Field(description="Notes from lab technician")


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
        "to provide comprehensive diagnostic reports"
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


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("🏥 Medical Diagnostic Correlation System")
    print("=" * 50)
    print("📋 Scenario: X-ray + Lab results correlation\n")

    # Patient 1: X-ray arrives first, then lab results (correlated!)
    print("👤 Patient A-001:")
    print("   ➡️  X-ray received (chest X-ray)")
    await flock.publish(
        XRayImage(
            patient_id="A-001",
            exam_type="chest_xray",
            image_quality="excellent",
            technician_notes="Clear lung fields, good positioning",
        )
    )

    print("   ➡️  Lab results received (blood work)")
    await flock.publish(
        LabResults(
            patient_id="A-001",
            blood_work={"wbc": 7500, "rbc": 4.8, "platelets": 250000},
            markers=["normal_range", "no_infection"],
            lab_notes="All values within normal limits",
        )
    )

    # Patient 2: Lab results arrive first, then X-ray (order doesn't matter!)
    print("\n👤 Patient B-002:")
    print("   ➡️  Lab results received (blood work)")
    await flock.publish(
        LabResults(
            patient_id="B-002",
            blood_work={"wbc": 12000, "rbc": 4.2, "platelets": 180000},
            markers=["elevated_wbc", "possible_infection"],
            lab_notes="Elevated white blood cell count",
        )
    )

    print("   ➡️  X-ray received (spine X-ray)")
    await flock.publish(
        XRayImage(
            patient_id="B-002",
            exam_type="spine_xray",
            image_quality="good",
            technician_notes="Slight curvature noted in thoracic region",
        )
    )

    # Patient 3: Only X-ray (no lab results yet - will wait!)
    print("\n👤 Patient C-003:")
    print("   ➡️  X-ray received (waiting for lab results...)")
    await flock.publish(
        XRayImage(
            patient_id="C-003",
            exam_type="abdominal_xray",
            image_quality="fair",
            technician_notes="Patient movement during scan",
        )
    )

    print("\n⏳ Processing correlations...")
    await flock.run_until_idle()

    # Retrieve diagnostic reports
    reports = await flock.store.get_by_type(DiagnosticReport)

    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC REPORTS GENERATED:")
    print("=" * 50)

    if reports:
        for i, report in enumerate(reports, 1):
            print(f"\n🏥 Report #{i} - Patient {report.patient_id}")
            print(f"   Diagnosis: {report.diagnosis}")
            print(f"   Confidence: {report.confidence}")
            print(f"   Treatment: {report.treatment_plan}")
            print(f"   Follow-up: {'Yes' if report.follow_up_needed else 'No'}")
    else:
        print("No reports generated yet (waiting for correlations)")

    print("\n" + "=" * 50)
    print(f"✅ Correlated {len(reports)} patient diagnostics")
    print("⏳ Patient C-003 still waiting for lab results...")
    print("\n💡 KEY FEATURE: JoinSpec ensures both diagnostics arrive")
    print("   before sending to radiologist for analysis!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
