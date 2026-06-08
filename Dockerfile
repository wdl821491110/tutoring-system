FROM python:3.11-slim

WORKDIR /app

# 复制必要文件
COPY app.py database.py requirements.txt run.py cloud_backup.py ./
COPY templates/ templates/
COPY static/ static/

# 安装依赖（使用国内镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.tencent.com/pypi/simple/

# 创建数据目录
RUN mkdir -p data

# CloudBase 云存储 API 密钥（仅环境变量，不再写入文件）
# 部署时通过 --env TCB_API_KEY=<your_key> 传入

# CloudBase CloudRun 默认使用 80 端口
EXPOSE 80

# 启动服务 
CMD ["python", "run.py"]
