FROM python:3.10-slim
WORKDIR /app
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8503
CMD ["streamlit", "run", "app.py", "--server.port=8503", "--server.address=0.0.0.0"]
