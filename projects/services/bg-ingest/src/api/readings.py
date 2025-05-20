"""API endpoints for retrieving blood glucose readings."""

from datetime import datetime, timedelta
import hashlib
import json
from typing import Optional, Dict, Any

from fastapi import APIRouter, Query, Request, Response, HTTPException, Depends
from starlette.status import HTTP_304_NOT_MODIFIED

from src.data.glucose_repository import GlucoseReadingRepository, get_glucose_repository
from src.models.glucose import GlucoseReading


router = APIRouter(tags=["glucose"])


def parse_iso_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO format datetime string.
    
    Args:
        date_string: ISO format datetime string
        
    Returns:
        Optional[datetime]: Parsed datetime or None if input is None
    """
    if not date_string:
        return None
    try:
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid date format: {date_string}. Expected ISO 8601 format (YYYY-MM-DDTHH:MM:SS+HH:MM)."
        )


@router.get("/{user_id}/latest")
async def get_latest_reading(
    user_id: str,
    request: Request,
    response: Response,
    db_client: GlucoseReadingRepository = Depends(get_glucose_repository)
) -> Dict[str, Any]:
    """
    Get the latest blood glucose reading for a user.
    
    Args:
        user_id: User ID
        request: Request object
        response: Response object
        db_client: DynamoDB client
        
    Returns:
        Dict[str, Any]: Latest reading
    """
    # Get latest reading from database
    reading = db_client.get_latest_reading_for_user(user_id)
    if not reading:
        raise HTTPException(status_code=404, detail="No readings found")
    
    # Convert the reading to a dict for response
    reading_dict = reading.model_dump()
    
    # Generate ETag based on the content
    reading_json = json.dumps(reading_dict, sort_keys=True)
    etag = f'"{hashlib.md5(reading_json.encode()).hexdigest()}"'
    
    # Check If-None-Match header for client-side caching
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=HTTP_304_NOT_MODIFIED)
    
    # Set ETag and cache headers for client-side caching
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    
    return {
        "status": "success",
        "data": reading_dict
    }


@router.get("/{user_id}")
async def get_readings(
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    cursor: Optional[str] = None,
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    format: Optional[str] = Query(None, pattern="^(default|simple|csv)$"),
    db_client: GlucoseReadingRepository = Depends(get_glucose_repository)
) -> Dict[str, Any]:
    """
    Get blood glucose readings for a user with filtering, pagination, and formatting options.
    
    Args:
        user_id: User ID
        start_date: Optional start date (ISO format)
        end_date: Optional end date (ISO format)
        limit: Maximum number of readings to return
        cursor: Pagination cursor
        sort: Sort order (asc or desc)
        format: Response format
        db_client: DynamoDB client
        
    Returns:
        Dict[str, Any]: Readings with pagination info
    """
    # Parse date parameters
    start = parse_iso_datetime(start_date) if start_date else datetime.utcnow() - timedelta(days=1)
    end = parse_iso_datetime(end_date) if end_date else datetime.utcnow()
    
    # Handle pagination cursor if provided
    if cursor:
        try:
            # Decode cursor (for simple implementation, assume it's a timestamp)
            cursor_timestamp = datetime.fromisoformat(cursor)
            
            # Adjust start/end based on cursor and sort direction
            if sort.lower() == "desc":
                end = cursor_timestamp
            else:
                start = cursor_timestamp
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor format")
    
    # Query database with pagination
    # Note: Current repository doesn't support pagination with cursors directly
    # For this implementation, we'll just get readings in the time range and handle cursors manually
    readings = db_client.get_readings_by_user_in_time_range(
        user_id=user_id,
        start_time=start,
        end_time=end,
        limit=limit + 1  # Get one extra item to determine if there are more results
    )
    
    # Sort based on requested order if needed (repository already returns desc)
    if sort.lower() == "asc":
        readings.reverse()
    
    # Check if we have more results than requested limit
    has_more = len(readings) > limit
    if has_more:
        readings = readings[:limit]  # Remove the extra item
    
    # Process results based on format
    formatted_readings = format_readings(readings, format)
    
    # Build response with pagination links
    response = {
        "status": "success",
        "data": formatted_readings,
        "pagination": {
            "count": len(readings),
            "sort": sort.lower(),
        }
    }
    
    # Add next/prev cursors if available
    if has_more and readings:
        next_cursor = readings[-1].timestamp.isoformat()
        response["pagination"]["next"] = next_cursor
        response["pagination"]["next_url"] = (
            f"/api/bg/{user_id}?start_date={start_date or ''}"
            f"&end_date={end_date or ''}&limit={limit}&cursor={next_cursor}&sort={sort}"
        )
    
    if cursor and readings:
        prev_cursor = readings[0].timestamp.isoformat()
        response["pagination"]["prev"] = prev_cursor
        response["pagination"]["prev_url"] = (
            f"/api/bg/{user_id}?start_date={start_date or ''}"
            f"&end_date={end_date or ''}&limit={limit}&cursor={prev_cursor}"
            f"&sort={'asc' if sort == 'desc' else 'desc'}"
        )
    
    return response


def format_readings(readings: list[GlucoseReading], format_type: Optional[str]) -> list:
    """
    Format readings based on requested format.
    
    Args:
        readings: List of glucose readings
        format_type: Format type (default, simple, csv)
        
    Returns:
        list: Formatted readings
    """
    if not format_type or format_type == "default":
        # Return full reading objects
        return [reading.model_dump() for reading in readings]
    
    elif format_type == "simple":
        # Return simplified reading objects with only essential fields
        simple_readings = []
        for reading in readings:
            simple_readings.append({
                "timestamp": reading.timestamp.isoformat(),
                "glucose_value": reading.glucose_value,
                "glucose_unit": reading.glucose_unit,
                "trend_direction": reading.trend_direction.value,
            })
        return simple_readings
    
    elif format_type == "csv":
        # Return readings formatted as CSV strings (header + rows)
        csv_lines = ["timestamp,glucose_value,glucose_unit,trend_direction"]
        for reading in readings:
            csv_lines.append(
                f"{reading.timestamp.isoformat()},{reading.glucose_value},"
                f"{reading.glucose_unit},{reading.trend_direction.value}"
            )
        return csv_lines
    
    # Should never reach here due to FastAPI parameter validation
    return [reading.model_dump() for reading in readings] 