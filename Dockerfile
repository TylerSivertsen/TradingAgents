FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home appuser

WORKDIR /app
COPY pyproject.toml README.md ./
COPY tradingagents ./tradingagents
COPY cli ./cli
COPY tests ./tests
COPY configs ./configs
COPY config ./config
COPY README_ALPACA_DAYTRADER.md README_QUANT_ORIA.md README_MARKET_UNIVERSE.md README_RISK_CONTROLS.md ./

RUN pip install --no-cache-dir -e . pytest

RUN mkdir -p /app/logs /app/reports /app/data /app/audit /app/experiments/results \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "-m", "tradingagents.alpaca_daytrader"]
CMD ["diagnostics"]
