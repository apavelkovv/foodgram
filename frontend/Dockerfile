FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json .npmrc ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build
FROM alpine:3.22
COPY --from=build /app/build /app/build
CMD ["sh", "-c", "cp -r /app/build/. /frontend/"]
