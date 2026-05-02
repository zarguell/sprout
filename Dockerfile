FROM node:22-slim AS css-build

WORKDIR /build

COPY package.json ./
COPY tailwind.config.js ./
COPY src/input.css ./src/input.css
COPY templates/ ./templates/

RUN npm install
RUN npm run build:css

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY templates/ ./templates/
COPY entrypoint.sh ./
COPY --from=css-build /build/static/css/output.css ./static/css/output.css

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
