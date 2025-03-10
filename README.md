# Amazon Bedrock Session Management API Demo for Infrastructure Diagnostics

This project demonstrates a powerful implementation of Amazon Bedrock Session Management APIs for maintaining and tracking infrastructure diagnostic sessions. It provides a robust framework for creating, storing, and retrieving diagnostic information during infrastructure incident resolution.

The demo implements a comprehensive session management system that allows infrastructure engineers to document their diagnostic steps, attach screenshots, and maintain a clear context of the troubleshooting process. The solution uses AWS Bedrock's Session Management APIs to ensure reliable storage and retrieval of diagnostic information, with built-in retry mechanisms and error handling for production-grade reliability.

## Repository Structure
```
.
└── bedrock_session_demo.py    # Main script implementing the Bedrock Session Management functionality
```

## Usage Instructions

### Prerequisites
- Python 3.x
- AWS credentials configured with appropriate permissions for Bedrock services
- Required Python packages:
  - boto3
  - rich
- AWS Region configured (default: us-east-1)

### Installation
```bash
# Clone the repository
git clone <repository-url>

# Install required packages
pip install boto3 rich
```

### Quick Start
1. Configure your AWS credentials:
```bash
aws configure
```

2. Run the script with basic parameters:
```python
from bedrock_session_demo import create_troubleshooting_session, store_diagnostic_step, retrieve_diagnostic_context

# Create a new diagnostic session
session_id = create_troubleshooting_session(
    incident_id="INC-001",
    system_affected="payment-microservice",
    severity="high"
)

# Store a diagnostic step
diagnostic_data = {
    "component": "payment-gateway",
    "action": "Verified API connectivity",
    "result": "Connection successful, latency: 150ms",
    "next_steps": "Monitor latency patterns"
}

success, invocation_id, step_id = store_diagnostic_step(
    session_id,
    engineer_id="ENG-123",
    diagnostics_data=diagnostic_data
)
```

### More Detailed Examples

#### Creating a Session with Screenshots
```python
# Create a diagnostic session with screenshots
diagnostic_data = {
    "component": "database-cluster",
    "action": "Performance analysis",
    "result": "High CPU utilization detected",
    "next_steps": "Scale up instance size"
}

screenshots = [
    "/path/to/cpu_metrics.png",
    "/path/to/memory_usage.png"
]

success, invocation_id, step_id = store_diagnostic_step(
    session_id,
    engineer_id="ENG-456",
    diagnostics_data=diagnostic_data,
    screenshots=screenshots
)
```

### Troubleshooting

#### Common Issues

1. Authentication Failures
```
Error: The session {session_id} does not exist or is not accessible
```
- Verify AWS credentials are properly configured
- Check IAM permissions for Bedrock services
- Ensure the correct AWS region is set

2. Session Creation Failures
```
Error: ValidationException
```
- Verify all required parameters are provided
- Check parameter format and length restrictions
- Ensure incident_id and system_affected are not empty

#### Debugging
- Enable verbose logging by setting environment variables:
```bash
export AWS_SDK_LOAD_CONFIG=1
export AWS_SDK_DEBUG=true
```
- Log files location: `~/.aws/logs/`
- Required permissions:
  - `bedrock:CreateSession`
  - `bedrock:GetSession`
  - `bedrock:CreateInvocation`
  - `bedrock:PutInvocationStep`

## Data Flow

The system processes diagnostic information through a structured workflow that maintains session context and ensures data consistency.

```ascii
[Input Data] -> [Session Creation] -> [Invocation Creation] -> [Step Storage]
     |               |                       |                       |
     v               v                       v                       v
User Input --> Session ID --> Invocation ID --> Diagnostic Steps --> Persistent Storage
```

Component Interactions:
1. Session Management layer handles session creation and validation
2. Invocation system manages atomic operations within sessions
3. Step Storage component handles diagnostic data and attachments
4. Retry mechanism ensures reliable data storage
5. Validation layer verifies data integrity at each step
6. Image processing handles screenshot attachments
7. Context retrieval system provides comprehensive session information
