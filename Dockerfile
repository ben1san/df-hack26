# ---- フロント。Node でビルドして web/ を作る
FROM node:22-slim AS web
WORKDIR /b
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build          # 出力は /web（vite.config.ts の outDir）

# ---- 本体。CP-SAT が要るので Python。コンテナは1つのまま
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" ortools pydantic \
    google-cloud-firestore google-genai
COPY app/ app/
COPY solver/ solver/
# seed/ は /api/ward/{wid}/import/sample が実行時に読む。入れないと段階0が落ちる
COPY seed/ seed/
COPY --from=web /web ./web
ENV PORT=8080 REPO=firestore GOOGLE_GENAI_USE_VERTEXAI=1 SOLVE_SECONDS=10
# Cloud Run は $PORT を listen する。1リクエスト内で同期的に解く
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
