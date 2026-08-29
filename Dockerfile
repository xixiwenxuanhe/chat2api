FROM node:22-alpine AS admin-build

WORKDIR /build

COPY admin/package.json admin/package-lock.json ./
RUN npm ci

COPY admin/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
COPY --from=admin-build /build/dist /app/admin_dist

EXPOSE 5005

CMD ["python", "app.py"]
