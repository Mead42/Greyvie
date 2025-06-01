from src.utils.validation import RequiredFieldRule, TypeRule, RangeRule, ValidationEngine
from src.utils.pipeline import DataTransformationPipeline
from src.utils.batch_processing import BatchProcessor
from src.metrics import readings_ingested_total

# Define validation rules and pipeline for ingestion
validation_rules = [
    RequiredFieldRule('user_id'),
    RequiredFieldRule('timestamp'),
    RequiredFieldRule('glucose_value'),
    TypeRule('glucose_value', (int, float)),
    RangeRule('glucose_value', 20, 600),
]
validation_engine = ValidationEngine(validation_rules)
pipeline = DataTransformationPipeline(validation_engine)

@router.post("/ingest", status_code=201)
async def ingest_reading(
    request: Request,
    db_client: GlucoseReadingRepository = Depends(get_glucose_repository)
):
    """
    Ingest a single blood glucose reading.
    """
    data = await request.json()
    normalized, errors = pipeline.process_reading(data)
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    reading = GlucoseReading(**normalized)
    db_client.create(reading)
    readings_ingested_total.labels(source='dexcom').inc()
    return {"status": "success", "data": reading.model_dump()}

@router.post("/ingest/batch", status_code=201)
async def ingest_batch(
    request: Request,
    db_client: GlucoseReadingRepository = Depends(get_glucose_repository)
):
    """
    Ingest a batch of blood glucose readings.
    """
    records = await request.json()
    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="Input must be a list of readings")
    batch = BatchProcessor(pipeline, error_strategy='skip')
    processed, error_collector = batch.process_batch(records)
    for norm in processed:
        reading = GlucoseReading(**norm)
        db_client.create(reading)
        readings_ingested_total.labels(source='dexcom').inc()
    summary = batch.summary()
    return {
        "status": "success" if not error_collector.has_errors() else "partial",
        "processed": len(processed),
        "failed": summary['failed'],
        "errors": error_collector.get_errors(),
    } 