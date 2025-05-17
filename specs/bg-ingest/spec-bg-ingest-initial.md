# BG Ingest Service Requirements Documentation

## 1. System Overview
The BG Ingest Service is a microservice responsible for fetching blood glucose readings from Dexcom's API and storing them in a time-series database. The service operates on a scheduled basis and can be triggered by external applications.

## 2. Functional Requirements

### 2.1 Dexcom API Integration
- Implement OAuth2 authentication flow with Dexcom API
- Support both sandbox and production Dexcom API environments
- Handle token refresh and expiration
- Implement rate limiting and retry mechanisms for API calls
- Support webhook notifications from Dexcom for real-time updates

### 2.2 Data Management
- Store blood glucose readings in DynamoDB with the following attributes:
  - User ID
  - Timestamp
  - Glucose value (mg/dL)
  - Trend direction
  - Device information
  - Reading type (CGM, manual, etc.)
- Implement data validation and normalization
- Support data deduplication
- Maintain data retention policies

### 2.3 Scheduling and Triggers
- Support configurable polling intervals (default: 900 seconds)
- Implement webhook endpoint for external triggers
- Support manual trigger via API endpoint
- Handle concurrent requests and prevent duplicate processing

### 2.4 API Endpoints
- `GET /api/bg/{userId}/latest`
  - Returns most recent BG reading
  - Response includes timestamp and glucose value
- `GET /api/bg/{userId}`
  - Supports date range filtering
  - Returns paginated results
  - Includes trend data
- `POST /api/bg/{userId}/webhook`
  - Validates webhook signatures
  - Processes incoming Dexcom notifications
- `POST /api/bg/{userId}/sync`
  - Manually triggers a sync for a specific user
  - Returns sync status and results

## 3. Non-Functional Requirements

### 3.1 Performance
- Maximum response time for API endpoints: 200ms
- Support for at least 1000 concurrent users
- Handle up to 1000 readings per user per day
- Process webhook notifications within 5 seconds

### 3.2 Reliability
- 99.9% uptime
- Implement circuit breakers for external API calls
- Automatic retry mechanism for failed API calls
- Data consistency checks
- Error logging and monitoring

### 3.3 Security
- Secure storage of Dexcom API credentials
- JWT validation for webhook endpoints
- Rate limiting for API endpoints
- Input validation and sanitization
- Audit logging for all operations

### 3.4 Scalability
- Horizontal scaling capability
- Efficient DynamoDB table design
- Optimized query patterns
- Caching strategy for frequent queries

## 4. Technical Requirements

### 4.1 Dependencies
- Python 3.11+
- FastAPI framework
- AWS SDK (boto3)
- RabbitMQ for event publishing
- DynamoDB for data storage
- HTTP client (httpx/requests)
- Testing frameworks (pytest, moto)

### 4.2 Environment Variables
```
DYNAMODB_ENDPOINT=http://dynamodb-local:8000
AWS_REGION=us-east-1
DYNAMODB_TABLE=bg_readings
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
DEXCOM_CLIENT_ID=your_client_id
DEXCOM_CLIENT_SECRET=your_client_secret
DEXCOM_REDIRECT_URI=http://localhost:5001/oauth/callback
DEXCOM_API_BASE_URL=https://sandbox-api.dexcom.com
POLL_INTERVAL_SECONDS=900
```

## 5. Monitoring and Logging

### 5.1 Metrics
- API response times
- Error rates
- Sync success/failure rates
- Data ingestion volume
- Token refresh success rate
- Webhook processing times

### 5.2 Logging
- Structured logging for all operations
- Error tracking and alerting
- Audit trail for data modifications
- Performance metrics logging

## 6. Testing Requirements

### 6.1 Unit Tests
- API endpoint functionality
- Data validation and normalization
- OAuth flow
- Error handling

### 6.2 Integration Tests
- DynamoDB operations
- Dexcom API integration
- Webhook processing
- Event publishing

### 6.3 Performance Tests
- Load testing
- Concurrent user simulation
- Data ingestion benchmarks

## 7. Deployment Requirements

### 7.1 Containerization
- Docker image with multi-stage build
- Health check endpoints
- Resource limits and requests
- Environment variable configuration

### 7.2 CI/CD
- Automated testing
- Docker image building
- Version tagging

## 8. Documentation Requirements

### 8.1 API Documentation
- OpenAPI/Swagger documentation
- Authentication requirements
- Rate limiting details
- Error codes and handling

### 8.2 Operational Documentation
- Deployment procedures
- Monitoring setup
- Troubleshooting guides
- Backup and recovery procedures

This requirements documentation provides a comprehensive overview of the bg-ingest service. The service is designed to be scalable, reliable, and maintainable while meeting the specific needs of blood glucose data ingestion from Dexcom's API.
