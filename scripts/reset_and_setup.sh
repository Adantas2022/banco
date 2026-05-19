#!/bin/bash

set -e

echo "🔄 Parando containers e removendo volumes..."
docker compose down -v --remove-orphans 2>/dev/null || true

echo "🧹 Removendo TODOS os containers irpf-processor..."
docker ps -a --filter "name=irpf-processor" -q | xargs -r docker rm -f 2>/dev/null || true

echo "🗑️ Removendo TODOS os volumes irpf-processor..."
docker volume ls --filter "name=irpf-processor" -q | xargs -r docker volume rm 2>/dev/null || true

echo "🔨 Fazendo build (sem cache) e subindo containers..."
docker compose build --no-cache
docker compose up -d

echo "⏳ Aguardando serviços iniciarem..."
sleep 15

echo "🧹 Limpando banco de dados..."
docker compose exec -T mongo mongosh irpf_processor --eval 'db.documents.deleteMany({}); db.extraction_results.deleteMany({}); db.api_keys.deleteMany({});'

echo "🔑 Gerando API Key de administrador..."
API_KEY_OUTPUT=$(docker compose exec -T worker-digital python -m irpf_processor.cli.create_api_key \
  --tenant-id meu-tenant \
  --name "Admin Key" \
  --admin 2>&1)

echo "$API_KEY_OUTPUT"

# Extrair a API Key da saída (formato: irpf_ak_... com hífens)
export API_KEY=$(echo "$API_KEY_OUTPUT" | grep -oE 'irpf_ak_[A-Za-z0-9_-]+' | head -1)

if [ -n "$API_KEY" ]; then
  echo ""
  echo "✅ Setup completo! Projeto rodando e API Key criada."
  echo ""
  echo "🔐 API_KEY: $API_KEY"
  echo ""
  
  # Salvar em arquivo para uso posterior
  echo "$API_KEY" > /tmp/irpf_api_key.txt
  
  # Verificar se existe o script processar_pdfs.sh e executar
  PROCESSAR_SCRIPT="/Users/camilooscargirardellibaptista/asa/ASA.IRPF.JSON.MIRROR/JsonMirro/quality/processar_pdfs.sh"
  if [ -f "$PROCESSAR_SCRIPT" ]; then
    echo "🚀 Executando processar_pdfs.sh..."
    echo ""
    cd "$(dirname "$PROCESSAR_SCRIPT")"
    API_KEY="$API_KEY" ./processar_pdfs.sh
  else
    echo "⚠️ Script processar_pdfs.sh não encontrado em: $PROCESSAR_SCRIPT"
    echo "📝 Execute manualmente com: API_KEY='$API_KEY' ./processar_pdfs.sh"
  fi
else
  echo "⚠️ Não foi possível extrair a API Key da saída"
fi
