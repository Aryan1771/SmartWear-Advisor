# Architecture

SmartWear Advisor separates the browser application from model inference.

## Components

| Location | Responsibility |
| --- | --- |
| `web_app/` | Flask routes, HTML templates, browser camera flow, and admin interface |
| `mainweb.py` | Web application entry point and keepalive startup |
| `hf_space/` | Separately deployed inference service, face matching, and accessory classification |
| `backend/` | Database, weather, recommendation, and keepalive helpers |
| `ai_model/` | Local dataset preparation, training, and detection scripts |

## Request flow

1. The browser captures a frame during registration or recognition.
2. The Flask service validates the request and delegates inference to the configured endpoint.
3. Inference results and weather data inform the recommendation flow.
4. Application records support detection history and administrator reporting.

## Configuration and boundaries

Use [.env.example](../.env.example) and [SETUP.md](../SETUP.md) to configure each service. Keep inference tokens, database credentials, and admin secrets on the server. The inference service has separate dependencies and model assets. Browser camera permission does not imply consent to retain images indefinitely; document deployment-specific retention separately.

The entry point starts a keepalive helper. Account for that background network activity when running locally or deploying multiple workers.
