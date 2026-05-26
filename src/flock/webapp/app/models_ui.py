# Pydantic models specific to UI interactions, if needed.
# For MVP, we might not need many here, as we'll primarily pass basic dicts to flock_service.
# Example:
# from pydantic import BaseModel
# class SaveFlockRequest(BaseModel):
#     current_flock_json: str # Or a more structured model if preferred
#     new_filename: str
