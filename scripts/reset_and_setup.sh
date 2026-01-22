#!/bin/bash

set -e

echo "🔄 Parando containers e removendo volumes..."
docker compose down -v

echo "🔨 Fazendo build e subindo containers..."
docker compose up -d --build

echo "⏳ Aguardando serviços iniciarem..."
sleep 15

echo "🧹 Limpando banco de dados..."
docker compose exec -T mongo mongosh irpf_processor --eval 'db.documents.deleteMany({}); db.extraction_results.deleteMany({}); db.api_keys.deleteMany({});'

echo "🔑 Gerando API Key de administrador..."
docker compose exec -T worker-digital python -m irpf_processor.cli.create_api_key \
  --tenant-id meu-tenant \
  --name "Admin Key" \
  --admin

echo ""
echo "✅ Setup completo! Projeto rodando e API Key criada."
echo ""
echo "📋 Mostrando logs dos workers (Ctrl+C para sair)..."
docker compose logs -f worker-digital worker-router
