# 🤝 Guia de Contribuição

Obrigado por considerar contribuir com o **IRPF Processor**!

## 📋 Índice

- [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Commits](#commits)
- [Pull Requests](#pull-requests)

---

## 🔧 Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- Git

### Setup

```bash
# Clonar repositório
git clone https://github.com/AsaBank/asa-nfe-process.git
cd asa-nfe-process

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Subir infraestrutura
docker compose up -d mongo redis minio prometheus pushgateway grafana

# Rodar API localmente
uvicorn irpf_processor.main:app --reload --port 8000
```

### Ferramentas de Desenvolvimento

```bash
# Linting
ruff check src/

# Formatação
ruff format src/

# Type checking
mypy src/

# Testes
pytest tests/ -v
```

---

## 📝 Padrões de Código

### Regras Fundamentais

| Regra | Descrição |
|-------|-----------|
| **Zero comentários inline** | Código deve ser autodocumentável |
| **Zero TODOs** | Tarefas devem estar no backlog |
| **Zero código comentado** | Usar controle de versão |
| **Type hints obrigatórios** | Em todas as funções públicas |

### Exemplo de Código Correto

```python
from typing import Optional
from pydantic import BaseModel

class TaxpayerData(BaseModel):
    cpf: str
    name: str
    occupation: Optional[str] = None


def extract_cpf(text: str) -> Optional[str]:
    pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    match = re.search(pattern, text)
    if not match:
        return None
    return match.group()


def validate_cpf(cpf: str) -> bool:
    digits = re.sub(r"\D", "", cpf)
    if len(digits) != 11:
        return False
    return _check_verifier_digits(digits)
```

### Exemplo de Código INCORRETO

```python
# NÃO FAÇA ISSO:

def extract_cpf(text):  # Falta type hint!
    # Busca o CPF no texto  <-- COMENTÁRIO PROIBIDO!
    pattern = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    match = re.search(pattern, text)
    # TODO: tratar CPFs inválidos  <-- TODO PROIBIDO!
    return match.group() if match else None
    # return text.split()[0]  <-- CÓDIGO COMENTADO PROIBIDO!
```

### Estrutura de Arquivos

```
src/irpf_processor/
├── domain/              # Entidades, Value Objects, Enums
├── application/         # Use Cases, Services, Interfaces
├── infrastructure/      # Implementações (MongoDB, MinIO, Parser)
├── presentation/        # API Routes, Workers
├── shared/              # Utilitários compartilhados
└── templates/           # Templates YAML
```

### Nomenclatura

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Classes | PascalCase | `TaxpayerExtractor` |
| Funções/Métodos | snake_case | `extract_cpf()` |
| Constantes | UPPER_SNAKE | `MAX_RETRY_ATTEMPTS` |
| Arquivos | snake_case | `taxpayer_extractor.py` |
| Variáveis | snake_case | `document_id` |

---

## 🧪 Testes

### Estrutura

```
tests/
├── unit/                # Testes unitários (sem I/O)
├── integration/         # Testes com MongoDB, Redis
└── fixtures/            # Dados de teste
```

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Apenas unitários
pytest tests/unit/ -v

# Com cobertura
pytest tests/ --cov=src/irpf_processor --cov-report=html

# Testes específicos
pytest tests/unit/test_irpf_parser.py -v
```

### Requisitos de Cobertura

- Mínimo **80%** de cobertura total
- Novos módulos devem ter **90%+**
- Extractors devem ter **85%+**

### Exemplo de Teste

```python
import pytest
from irpf_processor.infrastructure.extraction.field_extractors import extract_cpf


class TestExtractCpf:
    def test_extract_valid_cpf(self):
        text = "CPF: 123.456.789-00"
        result = extract_cpf(text)
        assert result == "123.456.789-00"

    def test_extract_cpf_not_found(self):
        text = "Sem CPF aqui"
        result = extract_cpf(text)
        assert result is None

    @pytest.mark.parametrize("cpf", [
        "123.456.789-00",
        "000.000.000-00",
        "999.999.999-99",
    ])
    def test_extract_various_cpfs(self, cpf: str):
        text = f"O CPF é {cpf}"
        result = extract_cpf(text)
        assert result == cpf
```

---

## 📌 Commits

### Formato

```
<tipo>: <descrição curta>

[corpo opcional]

[footer opcional]
```

### Tipos de Commit

| Tipo | Uso |
|------|-----|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Documentação |
| `test` | Testes |
| `refactor` | Refatoração (sem mudança de comportamento) |
| `perf` | Melhoria de performance |
| `chore` | Manutenção (deps, configs) |

### Exemplos

```bash
feat: adiciona extrator de criptoativos

fix: corrige parsing de valores negativos em Bens e Direitos

docs: atualiza README com novos endpoints de busca

test: adiciona testes para rural_assets_extractor

refactor: separa lógica de validação de CPF em módulo próprio

perf: otimiza query de busca por CPF com índice composto

chore: atualiza pdfplumber para 0.11.0
```

---

## 🔀 Pull Requests

### Checklist

Antes de abrir um PR, verifique:

- [ ] Código segue os padrões (sem comentários, type hints)
- [ ] Testes passando localmente
- [ ] Cobertura de testes >= 80%
- [ ] Linting passou (`ruff check src/`)
- [ ] Documentação atualizada (se necessário)

### Template de PR

```markdown
## Descrição

Breve descrição do que foi feito.

## Tipo de Mudança

- [ ] Bug fix
- [ ] Nova feature
- [ ] Refatoração
- [ ] Documentação

## Como Testar

1. Subir ambiente: `docker compose up -d`
2. Executar: `curl ...`
3. Verificar: ...

## Screenshots (se aplicável)

## Checklist

- [ ] Testes adicionados/atualizados
- [ ] Documentação atualizada
- [ ] Sem breaking changes (ou documentado)
```

### Processo de Review

1. Abra o PR contra `main`
2. Aguarde CI passar (testes, lint)
3. Solicite review de pelo menos 1 pessoa
4. Após aprovação, faça squash merge

---

## 🚫 O Que Evitar

| Prática | Motivo |
|---------|--------|
| Comentários no código | Código deve ser autodocumentável |
| TODOs | Use o backlog de issues |
| Código morto/comentado | Controle de versão existe pra isso |
| Magic numbers | Use constantes nomeadas |
| Funções muito longas | Quebre em funções menores |
| Múltiplas responsabilidades | SRP - Single Responsibility |

---

## 📚 Recursos

- [Clean Code - Robert Martin](https://www.amazon.com.br/C%C3%B3digo-limpo-Robert-C-Martin/dp/8576082675)
- [Domain-Driven Design - Eric Evans](https://www.amazon.com.br/Domain-Driven-Design-Eric-Evans/dp/8550800651)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2](https://docs.pydantic.dev/latest/)

---

<div align="center">

**Dúvidas? Abra uma issue ou pergunte no Slack #irpf-processor**

</div>
