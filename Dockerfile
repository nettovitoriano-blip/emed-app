# Dockerfile
FROM python:3.11-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o código para o container
COPY . /app

# Instala as dependências
RUN pip install --no-cache-dir streamlit qrcode[pil] pillow

# Diretório persistente onde vamos montar os arquivos JSON
RUN mkdir /data && \
    ln -s /data/users.json users.json && \
    ln -s /data/config.json config.json && \
    ln -s /data/devices.json devices.json

# Exponha a porta que o Streamlit usará
EXPOSE 8502

# Variáveis de ambiente (o domínio será resolvido via Cloudflare)
ENV STREAMLIT_SERVER_BASE_URL=https://emedservice.med.br
ENV PORT=8502

# Inicia a aplicação
CMD ["streamlit", "run", "app_emed.py", "--server.port", "8502", "--server.headless", "true"]