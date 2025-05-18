"""Models for blood glucose readings and related data."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TrendDirection(str, Enum):
    """Enum for blood glucose trend directions."""

    RISING_RAPIDLY = "rising_rapidly"
    RISING = "rising"
    STEADY = "steady"
    FALLING = "falling"
    FALLING_RAPIDLY = "falling_rapidly"
    UNKNOWN = "unknown"


class ReadingSource(str, Enum):
    """Enum for blood glucose reading sources."""

    DEXCOM = "dexcom"
    MANUAL = "manual"
    OTHER = "other"


class ReadingType(str, Enum):
    """Enum for blood glucose reading types."""

    CGM = "CGM"
    MANUAL = "manual"
    METER = "meter"


class DeviceInfo(BaseModel):
    """Device information for a glucose reading."""

    device_id: str = Field(..., description="Unique identifier for the device")
    serial_number: str = Field(..., description="Serial number of the device")
    transmitter_id: Optional[str] = Field(None, description="Transmitter ID for CGM devices")
    model: Optional[str] = Field(None, description="Model number or name of the device")
    manufacturer: str = Field("Dexcom", description="Manufacturer of the device")


class GlucoseReading(BaseModel):
    """Model for a blood glucose reading."""

    user_id: str = Field(..., description="User ID associated with the reading")
    timestamp: datetime = Field(..., description="Timestamp of the reading in UTC")
    glucose_value: float = Field(..., description="Blood glucose value", ge=20, le=600)
    glucose_unit: str = Field("mg/dL", description="Unit of glucose measurement")
    trend_direction: TrendDirection = Field(TrendDirection.UNKNOWN, description="Direction of glucose trend")
    device_info: DeviceInfo = Field(..., description="Information about the device")
    reading_type: ReadingType = Field(ReadingType.CGM, description="Type of reading")
    source: ReadingSource = Field(ReadingSource.DEXCOM, description="Source of the reading")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when record was last updated")
    
    @field_validator("glucose_value")
    @classmethod
    def validate_glucose_range(cls, value: float) -> float:
        """Validate that the glucose value is within a physiologically plausible range."""
        if value < 20 or value > 600:
            raise ValueError(f"Glucose value {value} is outside physiological range (20-600 mg/dL)")
        return value
    
    def to_dynamodb_item(self) -> dict:
        """Convert the model to a DynamoDB item."""
        # Convert to dictionary and handle special types
        item = self.model_dump()
        
        # DynamoDB doesn't store Python objects directly, so convert to string or other formats
        item["timestamp"] = item["timestamp"].isoformat()
        item["created_at"] = item["created_at"].isoformat()
        item["updated_at"] = item["updated_at"].isoformat()
        
        # Convert Enum values to strings
        item["trend_direction"] = item["trend_direction"].value
        item["reading_type"] = item["reading_type"].value
        item["source"] = item["source"].value
        
        # Flatten device_info to avoid nested objects
        device_info = item.pop("device_info")
        item["device_id"] = device_info["device_id"]
        item["device_serial_number"] = device_info["serial_number"]
        item["device_transmitter_id"] = device_info.get("transmitter_id")
        item["device_model"] = device_info.get("model")
        item["device_manufacturer"] = device_info["manufacturer"]
        
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "GlucoseReading":
        """Create a GlucoseReading instance from a DynamoDB item."""
        # Extract device info from flattened fields
        device_info = DeviceInfo(
            device_id=item["device_id"],
            serial_number=item["device_serial_number"],
            transmitter_id=item.get("device_transmitter_id"),
            model=item.get("device_model"),
            manufacturer=item.get("device_manufacturer", "Dexcom")
        )
        
        # Parse dates from ISO format
        timestamp = datetime.fromisoformat(item["timestamp"])
        created_at = datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.utcnow()
        updated_at = datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else datetime.utcnow()
        
        # Parse enums from strings
        trend_direction = TrendDirection(item.get("trend_direction", TrendDirection.UNKNOWN.value))
        reading_type = ReadingType(item.get("reading_type", ReadingType.CGM.value))
        source = ReadingSource(item.get("source", ReadingSource.DEXCOM.value))
        
        return cls(
            user_id=item["user_id"],
            timestamp=timestamp,
            glucose_value=float(item["glucose_value"]),
            glucose_unit=item.get("glucose_unit", "mg/dL"),
            trend_direction=trend_direction,
            device_info=device_info,
            reading_type=reading_type,
            source=source,
            created_at=created_at,
            updated_at=updated_at
        ) 