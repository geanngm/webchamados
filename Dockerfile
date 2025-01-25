# Use a imagem oficial do Python como base
FROM python:3.10-slim

# Instalar dependências para o rclone
RUN apt-get update && apt-get install -y curl unzip

# Instalar rclone
RUN curl https://rclone.org/install.sh | bash

# Instalar dependências do projeto
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Definir o diretório de trabalho
WORKDIR /app

# Copiar o código da aplicação para o contêiner
COPY . /app

# Expor a porta para o Flask
EXPOSE 8000

# Definir o comando para rodar a aplicação
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
