# Agentic Portfolio Management System

An AI-powered, multi-agent portfolio management system that provides intelligent trading recommendations through collaboration between specialized LLM-based agents.

## Overview

This system uses multiple AI agents that work together to analyze markets, generate trading signals, manage risk, and continuously learn from performance. The system operates in **advisory mode**, providing well-reasoned recommendations that require human approval before execution.

## Key Features

- **Multi-Agent Architecture**: Specialized agents for momentum trading, mean reversion, sentiment analysis, risk management, and research
- **LLM-Powered Reasoning**: Uses GPT-4 or Claude for sophisticated market analysis and decision-making
- **QuantConnect Integration**: Leverages existing strategies and data infrastructure
- **Human-in-the-Loop**: All recommendations require approval
- **Continuous Learning**: Research agent monitors performance and proposes improvements
- **Real-Time Dashboard**: Web interface for monitoring and decision-making

## Architecture

```
Orchestrator Agent (CIO)
         ↓
    ┌────┴────┐
    ↓         ↓         ↓
Strategy  Research  Risk Manager
Agents    Agent     Agent
    ↓         ↓         ↓
  QuantConnect + Market Data
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- QuantConnect account
- OpenAI or Anthropic API key

### Installation

1. Clone the repository:
```bash
cd "11 Agentic Portfolio Management"
```

2. Copy environment template:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Start infrastructure:
```bash
docker-compose up -d
```

4. Install dependencies:
```bash
poetry install
# or
pip install -r requirements.txt
```

5. Run database migrations:
```bash
python scripts/setup_db.py
```

6. Start the API server:
```bash
uvicorn src.api.main:app --reload
```

7. Launch the dashboard:
```bash
streamlit run src/ui/app.py
```

## Documentation

- [DESIGN.md](./DESIGN.md) - System architecture and design decisions
- [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) - Detailed implementation plan
- [docs/API.md](./docs/api.md) - API documentation
- [docs/DEPLOYMENT.md](./docs/deployment.md) - Deployment guide

## Project Structure

```
11 Agentic Portfolio Management/
├── src/
│   ├── agents/          # Agent implementations
│   ├── core/            # Core infrastructure (DB, messaging, LLM)
│   ├── integrations/    # QuantConnect and market data
│   ├── models/          # Data models
│   ├── api/             # FastAPI routes
│   └── ui/              # Streamlit dashboard
├── tests/               # Test suite
├── scripts/             # Utility scripts
├── docs/                # Additional documentation
└── docker-compose.yml   # Local development environment
```

## Development Workflow

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit -v

# With coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Development Mode

```bash
# Start all services
docker-compose up

# Watch logs
docker-compose logs -f api

# Restart service
docker-compose restart api
```

## Deployment

See [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) Phase 10 for production deployment instructions.

Quick deploy to AWS:

```bash
cd infrastructure/
terraform init
terraform plan
terraform apply
```

## Usage

### Viewing Recommendations

1. Open dashboard: http://localhost:8501
2. Navigate to "Recommendations" page
3. Review the investment thesis and recommended actions
4. Approve or reject recommendations

### API Examples

```python
import requests

# Get current recommendations
response = requests.get("http://localhost:8000/api/v1/recommendations")
recommendations = response.json()

# Approve a recommendation
requests.post(
    f"http://localhost:8000/api/v1/recommendations/{rec_id}/approve",
    headers={"Authorization": f"Bearer {api_token}"}
)

# Get portfolio status
response = requests.get("http://localhost:8000/api/v1/portfolio/current")
portfolio = response.json()
```

## Configuration

Key environment variables:

```bash
# LLM Provider
LLM_PROVIDER=openai          # or anthropic
LLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/agentic_pm

# QuantConnect
QC_API_USER_ID=123456
QC_API_TOKEN=...
QC_ORGANIZATION_ID=...

# Risk Constraints
MAX_POSITION_SIZE_PCT=0.10
MAX_PORTFOLIO_VOLATILITY=0.15
MAX_DRAWDOWN_PCT=0.20
```

## Agent Configuration

Agents can be configured via environment variables or the database:

```python
# Example: Adjust momentum agent parameters
{
  "agent_id": "momentum_001",
  "lookback_period": 60,
  "signal_threshold": 0.05,
  "trust_score": 75.0,
  "enabled": true
}
```

## Monitoring

- **Prometheus metrics**: http://localhost:9090
- **Grafana dashboards**: http://localhost:3000
- **Application logs**: `docker-compose logs -f`
- **Health check**: http://localhost:8000/api/v1/health

## Troubleshooting

### Common Issues

**Agent not generating recommendations:**
- Check LLM API key is valid
- Verify QuantConnect credentials
- Check agent logs: `docker-compose logs agent-orchestrator`

**Database connection errors:**
- Ensure PostgreSQL is running: `docker-compose ps`
- Check DATABASE_URL in .env
- Run migrations: `python scripts/setup_db.py`

**High LLM costs:**
- Reduce agent polling frequency
- Use smaller models for simple tasks
- Enable caching in config

See [docs/TROUBLESHOOTING.md](./docs/troubleshooting.md) for more.

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests and linting
4. Submit PR with description

## Roadmap

- [x] Phase 0: Project setup
- [x] Phase 1: Core infrastructure
- [x] Phase 2: Base agent framework
- [ ] Phase 3: Strategy agents
- [ ] Phase 4: Risk manager
- [ ] Phase 5: Orchestrator
- [ ] Phase 6: Research agent
- [ ] Phase 7: API layer
- [ ] Phase 8: User interface
- [ ] Phase 9: Testing
- [ ] Phase 10: Production deployment

See [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) for detailed timeline.

## Performance

Current benchmarks (will update as system develops):

- Recommendation latency: TBD
- API response time: TBD
- System uptime: TBD
- Recommendation approval rate: TBD

## License

[Your License]

## Support

For questions or issues:
- Open a GitHub issue
- Contact: your-email@example.com
- Documentation: [Link to docs]

## Acknowledgments

Built on top of:
- [QuantConnect](https://quantconnect.com) - Algorithmic trading platform
- [LangChain](https://langchain.com) / [CrewAI](https://crewai.com) - Agent frameworks
- [FastAPI](https://fastapi.tiangolo.com) - API framework
- [Streamlit](https://streamlit.io) - Dashboard framework

---

**Status**: 🚧 Under Development

**Current Phase**: Phase 0 - Pre-Implementation Setup

**Last Updated**: December 11, 2025
