# Product Requirements Document: BG Ingest Service

## 1. Introduction

This Product Requirements Document (PRD) outlines the specifications for the Blood Glucose (BG) Ingest Service, a microservice designed to fetch, process, and store blood glucose readings from Dexcom's Continuous Glucose Monitoring (CGM) API.

### 1.1 Purpose
The purpose of this document is to provide a comprehensive overview of the functional and non-functional requirements for developing the BG Ingest Service. It serves as the primary reference for engineers, quality assurance specialists, and stakeholders involved in the development process.

### 1.2 Scope
This document covers all aspects of the BG Ingest Service, including Dexcom API integration, data management, scheduling mechanisms, API endpoints, performance requirements, security protocols, and deployment specifications.

### 1.3 Document Conventions
- REQ-FUN-XX: Functional requirement identifier
- REQ-NFR-XX: Non-functional requirement identifier
- US-XX: User story identifier
- AC-XX: Acceptance criteria identifier

### 1.4 References
- Dexcom API Documentation
- AWS DynamoDB Documentation
- OAuth 2.0 Framework (RFC 6749)
- FastAPI Documentation

## 2. Product Overview

### 2.1 Product Description
The BG Ingest Service is a critical microservice within our healthcare data platform that automates the collection of blood glucose measurements from Dexcom's CGM devices. The service authenticates with Dexcom's API, retrieves blood glucose readings, validates and normalizes the data, and stores it in a time-series database (DynamoDB). The service operates both on a scheduled basis and can be triggered in response to external events.

### 2.2 System Context
The BG Ingest Service operates as part of a larger healthcare ecosystem, interfacing with:
- Dexcom API (external data source)
- DynamoDB (data storage)
- RabbitMQ (event publishing)
- Client applications (data consumers)
- Monitoring systems

### 2.3 Key Features
- OAuth2 authentication with Dexcom API
- Automated and on-demand data synchronization
- Data validation, normalization, and deduplication
- RESTful API for data retrieval and service management
- Real-time webhook notification processing
- Comprehensive monitoring and logging

### 2.4 Constraints
- Must comply with healthcare data security regulations
- Must handle intermittent connectivity with external APIs
- Must operate within AWS infrastructure
- Must be designed for high availability and fault tolerance

## 3. Goals and Objectives

### 3.1 Business Goals
- Enhance user experience by automating blood glucose data collection
- Reduce manual data entry errors and improve data accuracy
- Enable real-time monitoring of glucose trends for better healthcare decisions
- Create a scalable foundation for glucose data analytics

### 3.2 Success Metrics
- Achieve 99.9% uptime for the service
- Maintain data lag of less than 5 minutes from reading generation to availability
- Process 100% of incoming webhook notifications within 5 seconds
- Support a minimum of 1000 concurrent users
- Handle up to 1000 readings per user per day
- Keep API response times under 200ms for 95% of requests

### 3.3 Project Phases
1. **Phase 1**: Core implementation with scheduled polling
   - Dexcom API integration with OAuth2
   - Basic data storage and retrieval
   - Scheduled synchronization

2. **Phase 2**: Enhanced data processing
   - Webhook integration
   - Advanced data validation and normalization
   - Performance optimization

3. **Phase 3**: Scaling and monitoring
   - Enhanced monitoring and alerting
   - Caching implementation
   - Full documentation and operational guides

## 4. Target Audience

### 4.1 Primary Users
- **Patients with Diabetes**: Individuals using Dexcom CGM devices who want their glucose readings automatically synchronized with our platform
- **Healthcare Providers**: Doctors and nurses who monitor patients' glucose trends and need accurate, timely data
- **Friends and Family**: Parents, friends and family who monitor patients' glucose trends and need accurate, timely data
- **System Administrators**: Technical staff responsible for maintaining and monitoring the service

### 4.2 Secondary Users
- **Data Scientists**: Professionals analyzing glucose trends for research or product improvement
- **Application Developers**: Engineers building applications that consume glucose data
- **Support Team**: Staff helping users troubleshoot issues with data synchronization

### 4.3 User Needs and Pain Points
| User Type | Needs | Pain Points |
|-----------|-------|-------------|
| Patients | Automatic data sync, minimal setup | Manual data entry, delayed updates, privacy concerns |
| Healthcare Providers | Complete historical data, reliable access | Missing readings, data inconsistencies, delayed updates |
| Friends and Family | Complete historical data, reliable access | Missing readings, data inconsistencies, delayed updates |
| System Administrators | Monitoring tools, easy troubleshooting | Service outages, difficult diagnostics, credential management |
| Application Developers | Well-documented API, consistent data format | Integration complexity, API limitations, data formatting issues |

## 5. Features and Requirements

### 5.1 Dexcom API Integration

#### 5.1.1 OAuth2 Authentication (REQ-FUN-01)
- Implement OAuth2 authorization code flow with PKCE
- Support initial authentication, token storage, and refresh mechanisms
- Handle authentication errors gracefully
- Store tokens securely using AWS Secrets Manager

#### 5.1.2 API Environment Support (REQ-FUN-02)
- Support both Dexcom sandbox and production environments
- Configure environment selection via environment variables
- Implement environment-specific error handling and logging

#### 5.1.3 Token Management (REQ-FUN-03)
- Automatically refresh tokens before expiration
- Handle token revocation scenarios
- Implement token validation checks
- Track token refresh metrics and errors

#### 5.1.4 Rate Limiting and Retry Mechanisms (REQ-FUN-04)
- Implement exponential backoff for failed requests
- Honor Dexcom API rate limits
- Queue requests during rate limiting events
- Implement circuit breaker pattern for API outages

#### 5.1.5 Webhook Support (REQ-FUN-05)
- Register webhook endpoints with Dexcom API
- Validate incoming webhook signatures
- Process webhook payloads for real-time updates
- Handle webhook delivery failures

### 5.2 Data Management

#### 5.2.1 Data Storage (REQ-FUN-06)
- Store BG readings in DynamoDB with the following schema:
  ```
  Table: bg_readings
  Primary Key: user_id (partition key), timestamp (sort key)
  Attributes:
  - user_id: string
  - timestamp: ISO 8601 datetime
  - glucose_value: number (mg/dL)
  - trend_direction: string (enum)
  - device_info: map (device_id, serial_number, etc.)
  - reading_type: string (enum: CGM, manual)
  - source: string (default: "dexcom")
  - created_at: ISO 8601 datetime
  - updated_at: ISO 8601 datetime
  ```

#### 5.2.2 Data Validation (REQ-FUN-07)
- Validate glucose values against physiological ranges (20-600 mg/dL)
- Validate timestamp format and reasonableness
- Ensure required fields are present
- Validate trend direction against allowed values
- Log validation failures with detailed error information

#### 5.2.3 Data Normalization (REQ-FUN-08)
- Convert all timestamps to UTC ISO 8601 format
- Standardize glucose units to mg/dL
- Normalize trend direction terminology
- Ensure consistent device information format

#### 5.2.4 Data Deduplication (REQ-FUN-09)
- Check for existing readings with same user_id and timestamp
- Implement update strategy for duplicate readings
- Track and log deduplication events
- Implement conflict resolution strategy

### 5.3 Scheduling and Triggers

#### 5.3.1 Polling Configuration (REQ-FUN-11)
- Support configurable polling intervals via environment variables
- Default polling interval: 900 seconds (15 minutes)
- Implement jitter to prevent API thundering herd
- Track and log polling metrics

#### 5.3.2 Webhook Endpoint (REQ-FUN-12)
- Implement webhook receiver endpoint
- Process notifications asynchronously
- Send appropriate HTTP responses to webhook source
- Support webhook payload validation

#### 5.3.3 Manual Trigger (REQ-FUN-13)
- Provide API endpoint for manual synchronization
- Support user-specific synchronization
- Return detailed synchronization results
- Implement request idempotency

#### 5.3.4 Concurrency Management (REQ-FUN-14)
- Prevent duplicate processing of the same user's data
- Implement distributed locking mechanism
- Handle synchronization timeouts
- Gracefully manage queue backlogs

### 5.4 API Endpoints

#### 5.4.1 Get Latest Reading (REQ-FUN-15)
- Endpoint: `GET /api/bg/{userId}/latest`
- Response: Latest glucose reading with timestamp, value, and trend
- Support ETag and conditional requests
- Include proper caching headers

#### 5.4.2 Get Readings (REQ-FUN-16)
- Endpoint: `GET /api/bg/{userId}`
- Support query parameters:
  - startDate (ISO 8601)
  - endDate (ISO 8601)
  - limit (default: 100, max: 1000)
  - page/cursor for pagination
- Return paginated results with next/prev links
- Include trend data and device information

#### 5.4.3 Webhook Receiver (REQ-FUN-17)
- Endpoint: `POST /api/bg/{userId}/webhook`
- Validate webhook signatures
- Return 202 Accepted response
- Process payload asynchronously
- Support Dexcom-specific notification formats

#### 5.4.4 Manual Sync (REQ-FUN-18)
- Endpoint: `POST /api/bg/{userId}/sync`
- Support optional date range parameters
- Return synchronization job status
- Provide detailed results or error information
- Support idempotency keys

### 5.5 Non-Functional Requirements

#### 5.5.1 Performance (REQ-NFR-01)
- Maximum response time for API endpoints: 200ms (95th percentile)
- Support for at least 1000 concurrent users
- Handle up to 1000 readings per user per day
- Process webhook notifications within 5 seconds
- Complete scheduled sync for a user within 30 seconds

#### 5.5.2 Reliability (REQ-NFR-02)
- 99.9% uptime (less than 8.8 hours of downtime per year)
- Circuit breakers for external API calls
- Maximum 3 retry attempts for failed API calls
- Data consistency validation
- Comprehensive error logging and monitoring

#### 5.5.3 Security (REQ-NFR-03)
- Secure storage of Dexcom API credentials in AWS Secrets Manager
- JWT validation for all protected endpoints
- Rate limiting based on IP and user ID
- Input validation and sanitization for all endpoints
- Audit logging for all data access and modifications
- Data encryption at rest and in transit

#### 5.5.4 Scalability (REQ-NFR-04)
- Support horizontal scaling via containerization
- Efficient DynamoDB table design with appropriate indexes
- Optimized query patterns to minimize read/write costs
- Implement caching for frequently accessed data
- Stateless service design for easy scaling

## 6. User Stories and Acceptance Criteria

### 6.1 Dexcom Integration

#### US-01: OAuth Authentication
**As a** user with a Dexcom account,  
**I want** to securely authorize the application to access my Dexcom data,  
**So that** my glucose readings can be automatically synchronized.

**Acceptance Criteria:**
- AC-01: The system initiates the OAuth2 authorization flow with Dexcom
- AC-02: Users are redirected to Dexcom's authorization page
- AC-03: After authorization, the system securely stores the access and refresh tokens
- AC-04: The system refreshes tokens automatically before expiration
- AC-05: Users receive clear error messages if authorization fails

#### US-02: Data Synchronization
**As a** diabetic patient,  
**I want** the system to automatically fetch my glucose readings from Dexcom,  
**So that** I don't have to manually enter my readings.

**Acceptance Criteria:**
- AC-06: The system fetches new glucose readings every 15 minutes by default
- AC-07: All readings are stored with correct timestamp, glucose value, and trend information
- AC-08: The system handles Dexcom API outages gracefully with appropriate retries
- AC-09: Users can see the last successful sync time
- AC-10: Duplicate readings are handled appropriately

#### US-03: Real-time Updates
**As a** patient monitoring my glucose levels,  
**I want** to receive real-time updates when new readings are available,  
**So that** I can respond quickly to changing glucose levels.

**Acceptance Criteria:**
- AC-11: Webhook notifications from Dexcom are processed within 5 seconds
- AC-12: New readings from webhooks are immediately available via the API
- AC-13: The system validates webhook signatures for security
- AC-14: Failed webhook deliveries are logged for troubleshooting
- AC-15: The system handles webhook payload format changes gracefully

### 6.2 Data Management

#### US-04: Database Modeling
**As a** system architect,  
**I want** an efficient database design for storing glucose readings,  
**So that** the system can scale to support many users with fast query performance.

**Acceptance Criteria:**
- AC-16: DynamoDB table is designed with appropriate partition and sort keys
- AC-17: Indexes support efficient querying by date ranges
- AC-18: Schema supports all required attributes for glucose readings
- AC-19: Data access patterns are optimized for common queries
- AC-20: The database design supports the expected volume of readings

#### US-05: Data Validation
**As a** healthcare provider,  
**I want** glucose data to be validated for accuracy,  
**So that** I can trust the readings when making treatment decisions.

**Acceptance Criteria:**
- AC-21: The system validates glucose values are within physiological range (20-600 mg/dL)
- AC-22: Invalid readings are flagged and logged
- AC-23: Timestamps are validated for reasonableness (not in future, not too old)
- AC-24: Required fields are validated for presence and format
- AC-25: Validation failures generate appropriate error messages

#### US-06: Historical Data Access
**As a** patient,  
**I want** to access my historical glucose readings,  
**So that** I can track trends and patterns over time.

**Acceptance Criteria:**
- AC-26: Users can query readings by custom date ranges
- AC-27: Results are paginated for large data sets
- AC-28: Trend information is included with readings
- AC-29: Response times remain under 200ms for typical queries
- AC-30: Data is consistently formatted across all responses

### 6.3 Administration

#### US-07: Manual Synchronization
**As a** system administrator,  
**I want** to manually trigger synchronization for a specific user,  
**So that** I can troubleshoot data issues or ensure latest data availability.

**Acceptance Criteria:**
- AC-31: Administrators can trigger sync via API endpoint
- AC-32: The system returns detailed success/failure information
- AC-33: Manual syncs can specify date ranges
- AC-34: Concurrent manual sync requests are handled properly
- AC-35: Sync operations are logged for audit purposes

#### US-08: System Monitoring
**As a** DevOps engineer,  
**I want** comprehensive monitoring and logging of the ingest service,  
**So that** I can quickly identify and resolve issues.

**Acceptance Criteria:**
- AC-36: The system logs all API calls with appropriate detail
- AC-37: Error events are logged with context information
- AC-38: Performance metrics are collected for all operations
- AC-39: Alerts are generated for system failures or performance degradation
- AC-40: Health check endpoints provide accurate service status

#### US-09: Secure Access
**As a** security officer,  
**I want** all data access to be properly authenticated and authorized,  
**So that** patient health information remains private and secure.

**Acceptance Criteria:**
- AC-41: All API endpoints require appropriate authentication
- AC-42: User data is only accessible to authorized individuals
- AC-43: API credentials are securely stored
- AC-44: All data access is logged for audit purposes
- AC-45: The system implements rate limiting to prevent abuse

### 6.4 Integration

#### US-10: Data Consumption
**As an** application developer,  
**I want** a well-documented API for retrieving glucose data,  
**So that** I can build applications that utilize this data.

**Acceptance Criteria:**
- AC-46: The API is documented using OpenAPI/Swagger
- AC-47: Response formats are consistent and well-structured
- AC-48: Error responses include helpful messages and codes
- AC-49: Rate limits and authentication requirements are clearly documented
- AC-50: Sample code or SDK is provided for common operations

## 7. Technical Requirements

### 7.1 Technology Stack

#### 7.1.1 Programming Language and Framework
- Python 3.11 or later
- FastAPI web framework for API development
- Pydantic for data validation and settings management
- Uvicorn ASGI server for production deployment

#### 7.1.2 Data Storage
- AWS DynamoDB for primary data storage
- Table design:
  - bg_readings: Primary table for glucose readings
  - user_tokens: Table for storing OAuth tokens
  - sync_jobs: Table for tracking synchronization jobs

#### 7.1.3 External Services
- Dexcom API (sandbox and production environments)
- AWS Secrets Manager for credential storage
- RabbitMQ for event publishing and async processing

#### 7.1.4 Development Tools
- Docker and Docker Compose for containerization
- Poetry for dependency management
- Pytest for testing
- Mypy for type checking
- Black and isort for code formatting
- Flake8 for linting

### 7.2 Architecture

#### 7.2.1 System Components
- **API Layer**: FastAPI application handling HTTP requests
- **Authentication Service**: Manages OAuth flows and token refresh
- **Data Ingest Service**: Handles data fetching, validation, and storage
- **Webhook Processor**: Processes real-time notifications
- **Scheduler**: Manages periodic synchronization
- **Event Publisher**: Publishes events to message queue

#### 7.2.2 Component Interactions
```
┌────────────┐      ┌────────────┐      ┌────────────┐
│  Dexcom    │◄────►│  BG Ingest │◄────►│  DynamoDB  │
│  API       │      │  Service   │      │            │
└────────────┘      └─────┬──────┘      └────────────┘
                          │
                          ▼
┌────────────┐      ┌────────────┐      ┌────────────┐
│  Client    │◄────►│  API       │      │  RabbitMQ  │
│  Apps      │      │  Layer     │◄────►│            │
└────────────┘      └────────────┘      └────────────┘
```

#### 7.2.3 API Design
- RESTful API design principles
- Resource-oriented endpoints
- Consistent error handling
- JWT authentication
- Rate limiting
- Pagination for list responses

### 7.3 Environment Configuration

#### 7.3.1 Required Environment Variables
```
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<access_key>
AWS_SECRET_ACCESS_KEY=<secret_key>

# DynamoDB Configuration
DYNAMODB_ENDPOINT=http://dynamodb-local:8000
DYNAMODB_TABLE=bg_readings
DYNAMODB_USER_TOKENS_TABLE=user_tokens
DYNAMODB_SYNC_JOBS_TABLE=sync_jobs

# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
RABBITMQ_EXCHANGE=bg_events
RABBITMQ_QUEUE=bg_readings

# Dexcom API Configuration
DEXCOM_CLIENT_ID=<client_id>
DEXCOM_CLIENT_SECRET=<client_secret>
DEXCOM_REDIRECT_URI=http://localhost:5001/oauth/callback
DEXCOM_API_BASE_URL=https://sandbox-api.dexcom.com
DEXCOM_API_VERSION=v2

# Service Configuration
SERVICE_ENV=development  # development, staging, production
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
POLL_INTERVAL_SECONDS=900
MAX_RETRIES=3
RETRY_BACKOFF_FACTOR=2
REQUEST_TIMEOUT_SECONDS=30
```

#### 7.3.2 Secrets Management
- AWS Secrets Manager for storing sensitive credentials
- Environment-based configuration loading
- Secret rotation support
- Fallback mechanisms for development environments

### 7.4 Monitoring and Logging

#### 7.4.1 Logging
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Request ID tracking across components
- User ID context in logs
- Performance metrics logging

#### 7.4.2 Metrics
- API response times by endpoint
- Error rates and types
- Token refresh success/failure rates
- Data volume metrics
- Webhook processing times
- Sync job completion rates

#### 7.4.3 Alerts
- Service availability alerts
- Error rate threshold alerts
- Token refresh failure alerts
- Data synchronization failure alerts
- Performance degradation alerts

### 7.5 Development Workflow

#### 7.5.1 Code Management
- Git-based version control
- Feature branch workflow
- Pull request reviews
- Semantic versioning
- Changelog maintenance

#### 7.5.2 Testing Strategy
- Unit tests for core functionality
- Integration tests for external services
- Mock-based testing for external dependencies
- Performance testing for critical paths
- Security scanning

#### 7.5.3 CI/CD Pipeline
- Automated testing on pull requests
- Code quality checks
- Container building and publishing

## 8. Design and User Interface

### 8.1 API Design

#### 8.1.1 RESTful Endpoints

**Authentication Endpoints:**
```
POST /oauth/authorize
  - Initiates OAuth flow with Dexcom
  - Parameters: client_id, redirect_uri, state, code_challenge

GET /oauth/callback
  - OAuth callback handler
  - Parameters: code, state

POST /oauth/refresh
  - Manually refresh access token
  - Parameters: user_id
```

**Data Endpoints:**
```
GET /api/bg/{userId}/latest
  - Returns most recent reading
  - Response includes timestamp, glucose value, trend

GET /api/bg/{userId}
  - Returns readings for specified time period
  - Query parameters: startDate, endDate, limit, cursor
  - Supports pagination
  - Returns readings with all attributes

POST /api/bg/{userId}/webhook
  - Webhook receiver for Dexcom notifications
  - Validates webhook signatures
  - Processes notifications asynchronously

POST /api/bg/{userId}/sync
  - Manually triggers synchronization
  - Query parameters: startDate, endDate
  - Returns sync job status and ID
```

**Administrative Endpoints:**
```
GET /health
  - Service health check
  - Returns status of dependencies

GET /metrics
  - Service metrics endpoint
  - Returns performance and operational metrics

GET /api/jobs/{jobId}
  - Returns status of sync job
  - Includes detailed results or errors
```

#### 8.1.2 Response Formats

**Standard Success Response:**
```json
{
  "status": "success",
  "data": {
    // Response data
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      // Additional error details
    }
  }
}
```

**Glucose Reading Format:**
```json
{
  "user_id": "user123",
  "timestamp": "2023-08-15T14:30:00Z",
  "glucose_value": 120,
  "glucose_unit": "mg/dL",
  "trend_direction": "steady",
  "device_info": {
    "device_id": "G6-12345",
    "serial_number": "SN12345678",
    "transmitter_id": "TX12345"
  },
  "reading_type": "CGM",
  "source": "dexcom"
}
```

### 8.2 Error Handling

#### 8.2.1 Error Codes
- `AUTH_ERROR`: Authentication or authorization failures
- `VALIDATION_ERROR`: Input validation failures
- `RESOURCE_NOT_FOUND`: Requested resource not found
- `EXTERNAL_API_ERROR`: Issues with external API calls
- `RATE_LIMIT_EXCEEDED`: Rate limiting applied
- `INTERNAL_ERROR`: Unexpected internal errors
- `DATA_ERROR`: Data processing or validation errors

#### 8.2.2 HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource successfully created
- `202 Accepted`: Request accepted for processing
- `400 Bad Request`: Input validation failures
- `401 Unauthorized`: Authentication failures
- `403 Forbidden`: Authorization failures
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limiting applied
- `500 Internal Server Error`: Unexpected errors
- `503 Service Unavailable`: Service temporarily unavailable

### 8.3 Rate Limiting

#### 8.3.1 Rate Limit Tiers
- Standard tier: 100 requests per minute per IP
- Authenticated tier: 300 requests per minute per user
- Webhook endpoints: 1000 requests per minute per IP

#### 8.3.2 Rate Limit Headers
```
X-RateLimit-Limit: <requests_per_minute>
X-RateLimit-Remaining: <requests_remaining>
X-RateLimit-Reset: <reset_timestamp>
```

### 8.4 Documentation

#### 8.4.1 API Documentation
- OpenAPI/Swagger documentation
- Interactive API explorer
- Authentication guide
- Error code reference
- Rate limiting details
- Example requests and responses

#### 8.4.2 Developer Guides
- Getting started guide
- Authentication implementation guide
- Webhook integration guide
- Common use cases
- Troubleshooting guide

### 8.5 Security Design

#### 8.5.1 Authentication Flow
1. Client initiates OAuth flow with code challenge
2. User authenticates with Dexcom
3. Dexcom redirects with authorization code
4. Service exchanges code for access and refresh tokens
5. Service stores tokens securely
6. Service uses tokens for API calls
7. Service refreshes tokens automatically

#### 8.5.2 Data Protection
- All data encrypted in transit (TLS 1.2+)
- All data encrypted at rest (AWS KMS)
- Token storage with encryption
- PII and PHI handling compliant with regulations
- Regular security audits