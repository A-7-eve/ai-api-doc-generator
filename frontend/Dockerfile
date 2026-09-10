# 前端镜像：多阶段构建
#   阶段1 builder：node 构建 vite 产物
#   阶段2 nginx：托管静态文件
# 构建上下文为 frontend/ 目录（nginx.conf 由 compose 以挂载方式注入，见 docker-compose.yml）

# ---- 阶段 1：构建 ----
FROM node:20-alpine AS builder
WORKDIR /app

# 先复制依赖清单（利用层缓存）
COPY package.json package-lock.json ./
RUN npm ci

# 构建产物
COPY . .
RUN npm run build

# ---- 阶段 2：运行 ----
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
