FROM python:3.12-slim

WORKDIR /src
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml README.md requirements.txt ./
COPY wbr ./wbr
RUN pip install --no-cache-dir -e ".[llm]"

COPY studio/backend /src/studio/backend
RUN pip install --no-cache-dir -e /src/studio/backend

WORKDIR /src/studio/backend
RUN chmod +x /src/studio/backend/entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "wbr_studio.main:app", "--host", "0.0.0.0", "--port", "8000"]
