from pydantic import BaseModel

# TODO: Define models for Dexcom API responses
class GlucoseReading(BaseModel):
    # Example fields, update according to Dexcom API
    value: float
    timestamp: str 