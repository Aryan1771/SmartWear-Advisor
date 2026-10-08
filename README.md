# SmartWear Advisor

A Flask application that combines face recognition, mask/glasses classification, and weather information to produce accessory suggestions. The web service delegates image inference to a separate Hugging Face service and uses Turso for persistent records.

## Architecture

| Component | Responsibility |
| --- | --- |
| `web_app/` and `mainweb.py` | Camera interface, application routes, and admin dashboard |
| `hf_space/` | Face recognition and accessory-model inference |
| `backend/` | Weather integration, recommendations, and data services |
| `ai_model/` | Dataset preparation and local model training |

See [architecture](docs/architecture.md) and the [setup guide](SETUP.md) for service configuration.

## Capabilities

- Browser camera capture with request throttling and one-shot registration.
- Weather integration using OpenWeatherMap and Open-Meteo.
- Registration records, detection history, audit logs, and CSV export.
- Admin workflows with password confirmation for log clearing.
- Mobile-oriented interface with PWA support.

## Local development

Create a virtual environment, activate it, and run from the repository root:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
python mainweb.py
```

On PowerShell, use `Copy-Item .env.example .env`. Configure the copied file before starting the app. The inference service requires its own dependencies and model files; the Flask dependency list alone does not provide inference.

Key settings are `SECRET_KEY`, `ADMIN_PASSWORD`, `HF_API_URL` or `HF_SPACE_URL`, `HF_API_TOKEN` or `HF_TOKEN`, `OWM_API_KEY`, `TURSO_URL`, and `TURSO_TOKEN`. See [.env.example](.env.example) for the supplied configuration.

For a configured deployment:

```bash
gunicorn mainweb:app --workers 2 --timeout 120
```

## Operational limits

Recognition quality depends on the model, image quality, and evaluation data. Accessory suggestions are heuristic outputs; the repository does not supply a validated health assessment. Camera frames are sent to the configured inference service, so deployments need an appropriate consent and data-retention process. Service availability and cold starts affect response times.

## Development status

See the [project report](docs/report.md) for scope and remaining validation. Model accuracy and deployment readiness should be established with recorded experiments, not inferred from the presence of an interface.

## License

See [LICENSE](LICENSE) for the GNU GPL v3 terms.
