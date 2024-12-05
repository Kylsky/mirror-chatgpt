# 使用ARM兼容的Python基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

RUN apt-get update && apt-get install -y --fix-missing \
    wget \
    curl \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 运行应用
CMD ["python", "mirror.py"]