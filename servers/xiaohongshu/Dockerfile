# ---- 阶段 1: 构建器 (Builder) ----
# 使用一个功能完整的镜像，它包含编译工具或可以轻松安装它们
FROM python:3.12-slim-bookworm

WORKDIR /app

# 安装编译 uvloop 和 httptools 所需的系统依赖 (C编译器等)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libmariadb-dev \
    pkg-config \
    python3-dev \
    openssl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# 复制需求文件
COPY requirements.txt .

# 在这个具备编译环境的阶段安装所有 Python 依赖
# 安装到一个独立的目录 /install 中，以便后续复制
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# ---- 阶段 2: 最终镜像 (Final Image) ----
# 使用轻量级 slim 镜像作为最终的运行环境
# 从构建器阶段，将已经安装好的依赖包复制到最终镜像的系统路径中

# 复制项目代码和相关文件
COPY locale /app/locale
COPY source /app/source
COPY static/XHS-Downloader.tcss /app/static/XHS-Downloader.tcss
COPY LICENSE /app/LICENSE
COPY main.py /app/main.py

# 暴露端口
EXPOSE 5556

# 创建挂载点
VOLUME /app/Volume

# 设置容器启动命令
CMD ["python", "main.py"]
