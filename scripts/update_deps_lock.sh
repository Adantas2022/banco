#!/bin/bash
# =============================================================================
# Script para atualizar requirements.lock
# 
# Uso:
#   ./scripts/update_deps_lock.sh
#
# Requer pip-tools instalado: pip install pip-tools
# =============================================================================

set -e

echo "📦 Atualizando requirements.lock..."

# Verifica se pip-tools está instalado
if ! command -v pip-compile &> /dev/null; then
    echo "⚠️  pip-tools não encontrado. Instalando..."
    pip install pip-tools
fi

# Gera requirements.lock a partir do pyproject.toml
pip-compile \
    --output-file=requirements.lock \
    --resolver=backtracking \
    --strip-extras \
    --no-header \
    pyproject.toml

# Adiciona cabeçalho personalizado
HEADER="# =============================================================================
# IRPF Processor - Locked Dependencies
# Generated: $(date +%Y-%m-%d)
# 
# This file contains pinned versions for production deployments.
# To update: ./scripts/update_deps_lock.sh
# =============================================================================
"

echo "$HEADER" | cat - requirements.lock > temp && mv temp requirements.lock

echo "✅ requirements.lock atualizado com sucesso!"
echo ""
echo "📋 Próximos passos:"
echo "   1. Revise as mudanças: git diff requirements.lock"
echo "   2. Teste localmente: pip install -r requirements.lock"
echo "   3. Commit: git add requirements.lock && git commit -m 'chore(deps): update locked dependencies'"
