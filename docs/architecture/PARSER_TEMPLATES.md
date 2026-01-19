# 🔄 Parser e Sistema de Templates

**Versão:** 1.0  
**Data:** 2026-01-16  
**Status:** Design

---

## 1. Visão Geral

O sistema de parsing é dividido em duas etapas distintas:

1. **Extração** — Extrair dados brutos do XML NFe para um modelo interno completo
2. **Transformação** — Aplicar um Template para gerar o JSON no formato esperado pelo consumidor

```mermaid
flowchart LR
    XML[XML NFe] --> PARSER[Parser/Extractor]
    PARSER --> RAW[NFeRaw<br/>Dados Completos]
    RAW --> ENGINE[Template Engine]
    TEMPLATE[Template Config] --> ENGINE
    ENGINE --> OUTPUT[JSON Output<br/>Formato do Cliente]
```

---

## 2. Por que Templates?

| Problema | Solução com Templates |
|----------|----------------------|
| Diferentes clientes esperam formatos diferentes | Cada cliente pode ter seu próprio template |
| Formato do fornecedor anterior precisa ser mantido | Template replica o formato exato |
| Novos campos precisam ser adicionados | Edita apenas o template, não o código |
| Campos precisam ser renomeados | Mapeamento no template |
| Transformações de dados (datas, CNPJs) | Funções de transformação no template |

---

## 3. Arquitetura do Parser

### 3.1 Diagrama de Componentes

```mermaid
flowchart TB
    subgraph Input["📥 Entrada"]
        XML[XML NFe<br/>Qualquer versão]
    end

    subgraph Parser["🔍 Parser Layer"]
        VALIDATOR[XSD Validator]
        EXTRACTOR[NFe Extractor]
        RAW_MODEL[NFeRaw Model<br/>Todos os campos possíveis]
    end

    subgraph Templates["📋 Template Layer"]
        REGISTRY[Template Registry]
        T1[Template: Legacy API]
        T2[Template: New Format]
        T3[Template: Minimal]
    end

    subgraph Engine["⚙️ Template Engine"]
        MAPPER[Field Mapper]
        TRANSFORMER[Transformers]
        RENDERER[JSON Renderer]
    end

    subgraph Output["📤 Saída"]
        JSON1[JSON Legacy]
        JSON2[JSON New]
        JSON3[JSON Minimal]
    end

    XML --> VALIDATOR
    VALIDATOR --> EXTRACTOR
    EXTRACTOR --> RAW_MODEL
    
    RAW_MODEL --> ENGINE
    REGISTRY --> ENGINE
    T1 --> REGISTRY
    T2 --> REGISTRY
    T3 --> REGISTRY
    
    ENGINE --> JSON1
    ENGINE --> JSON2
    ENGINE --> JSON3
```

### 3.2 Diagrama de Classes

```mermaid
classDiagram
    direction TB

    class INFeExtractor {
        <<interface>>
        +extract(xml_bytes) NFeRaw
        +validate(xml_bytes) ValidationResult
    }

    class ITemplateEngine {
        <<interface>>
        +render(nfe_raw, template_id) dict
        +register_template(template) None
        +get_template(template_id) Template
    }

    class ITransformer {
        <<interface>>
        +transform(value, params) Any
    }

    class NFeRaw {
        +chave: str
        +versao: str
        +ide: IdeRaw
        +emit: ParticipanteRaw
        +dest: ParticipanteRaw
        +det: List~ItemRaw~
        +total: TotalRaw
        +transp: TranspRaw
        +cobr: CobrRaw
        +pag: PagRaw
        +infAdic: InfAdicRaw
        +infRespTec: InfRespTecRaw
        +protNFe: ProtNFeRaw
        +raw_xml: str
    }

    class Template {
        +id: str
        +name: str
        +version: str
        +description: str
        +mappings: List~FieldMapping~
        +transforms: dict
        +defaults: dict
    }

    class FieldMapping {
        +target_path: str
        +source_path: str
        +transformer: str?
        +transformer_params: dict?
        +default: Any?
        +required: bool
    }

    class LxmlNFeExtractor {
        -xsd_schemas: dict
        +extract(xml_bytes) NFeRaw
        +validate(xml_bytes) ValidationResult
        -parse_ide(node) IdeRaw
        -parse_emit(node) ParticipanteRaw
        -parse_dest(node) ParticipanteRaw
        -parse_det(nodes) List~ItemRaw~
        -parse_total(node) TotalRaw
    }

    class JinjaTemplateEngine {
        -templates: dict
        -transformers: dict
        +render(nfe_raw, template_id) dict
        +register_template(template) None
        +get_template(template_id) Template
        -apply_mappings(nfe_raw, mappings) dict
    }

    class DateTransformer {
        +transform(value, params) str
    }

    class CnpjTransformer {
        +transform(value, params) str
    }

    class CurrencyTransformer {
        +transform(value, params) str
    }

    class ConcatTransformer {
        +transform(value, params) str
    }

    INFeExtractor <|.. LxmlNFeExtractor
    ITemplateEngine <|.. JinjaTemplateEngine
    ITransformer <|.. DateTransformer
    ITransformer <|.. CnpjTransformer
    ITransformer <|.. CurrencyTransformer
    ITransformer <|.. ConcatTransformer

    JinjaTemplateEngine --> Template
    Template --> FieldMapping
    JinjaTemplateEngine --> ITransformer
    LxmlNFeExtractor --> NFeRaw
```

---

## 4. Modelo NFeRaw (Extração Completa)

O `NFeRaw` contém **todos os campos possíveis** do XML NFe, servindo como fonte única de dados.

```mermaid
classDiagram
    class NFeRaw {
        +chave: str
        +versao: str
        +ide: IdeRaw
        +emit: ParticipanteRaw
        +dest: ParticipanteRaw
        +det: List~ItemRaw~
        +total: TotalRaw
        +transp: TranspRaw
        +cobr: CobrRaw
        +pag: PagRaw
        +infAdic: InfAdicRaw
        +protNFe: ProtNFeRaw
    }

    class IdeRaw {
        +cUF: str
        +cNF: str
        +natOp: str
        +mod: str
        +serie: str
        +nNF: str
        +dhEmi: datetime
        +dhSaiEnt: datetime
        +tpNF: str
        +idDest: str
        +cMunFG: str
        +tpImp: str
        +tpEmis: str
        +cDV: str
        +tpAmb: str
        +finNFe: str
        +indFinal: str
        +indPres: str
        +indIntermed: str
        +procEmi: str
        +verProc: str
    }

    class ParticipanteRaw {
        +CNPJ: str
        +CPF: str
        +xNome: str
        +xFant: str
        +IE: str
        +IEST: str
        +IM: str
        +CNAE: str
        +CRT: str
        +endereco: EnderecoRaw
    }

    class EnderecoRaw {
        +xLgr: str
        +nro: str
        +xCpl: str
        +xBairro: str
        +cMun: str
        +xMun: str
        +UF: str
        +CEP: str
        +cPais: str
        +xPais: str
        +fone: str
    }

    class ItemRaw {
        +nItem: int
        +prod: ProdutoRaw
        +imposto: ImpostoRaw
        +infAdProd: str
    }

    class ProdutoRaw {
        +cProd: str
        +cEAN: str
        +xProd: str
        +NCM: str
        +CEST: str
        +CFOP: str
        +uCom: str
        +qCom: Decimal
        +vUnCom: Decimal
        +vProd: Decimal
        +cEANTrib: str
        +uTrib: str
        +qTrib: Decimal
        +vUnTrib: Decimal
        +vFrete: Decimal
        +vSeg: Decimal
        +vDesc: Decimal
        +vOutro: Decimal
        +indTot: str
    }

    class TotalRaw {
        +vBC: Decimal
        +vICMS: Decimal
        +vICMSDeson: Decimal
        +vFCP: Decimal
        +vBCST: Decimal
        +vST: Decimal
        +vFCPST: Decimal
        +vFCPSTRet: Decimal
        +vProd: Decimal
        +vFrete: Decimal
        +vSeg: Decimal
        +vDesc: Decimal
        +vII: Decimal
        +vIPI: Decimal
        +vIPIDevol: Decimal
        +vPIS: Decimal
        +vCOFINS: Decimal
        +vOutro: Decimal
        +vNF: Decimal
        +vTotTrib: Decimal
    }

    class ProtNFeRaw {
        +tpAmb: str
        +verAplic: str
        +chNFe: str
        +dhRecbto: datetime
        +nProt: str
        +digVal: str
        +cStat: str
        +xMotivo: str
    }

    NFeRaw --> IdeRaw
    NFeRaw --> ParticipanteRaw
    NFeRaw --> ItemRaw
    NFeRaw --> TotalRaw
    NFeRaw --> ProtNFeRaw
    ParticipanteRaw --> EnderecoRaw
    ItemRaw --> ProdutoRaw
```

---

## 5. Sistema de Templates

### 5.1 Estrutura de um Template

```yaml
# templates/legacy_api.yaml
id: "legacy_api"
name: "Legacy API Format"
version: "1.0"
description: "Formato compatível com API do fornecedor anterior"

mappings:
  # Campos simples
  - target: "numero_nota"
    source: "ide.nNF"
    
  - target: "serie"
    source: "ide.serie"
    
  - target: "data_emissao"
    source: "ide.dhEmi"
    transformer: "date"
    params:
      format: "%d/%m/%Y"
      
  - target: "chave_acesso"
    source: "chave"
    
  # Emitente
  - target: "emitente.cnpj"
    source: "emit.CNPJ"
    transformer: "cnpj"
    params:
      format: "raw"  # ou "formatted" para XX.XXX.XXX/XXXX-XX
      
  - target: "emitente.razao_social"
    source: "emit.xNome"
    
  - target: "emitente.nome_fantasia"
    source: "emit.xFant"
    default: null
    
  - target: "emitente.inscricao_estadual"
    source: "emit.IE"
    
  - target: "emitente.endereco.logradouro"
    source: "emit.endereco.xLgr"
    
  - target: "emitente.endereco.numero"
    source: "emit.endereco.nro"
    
  - target: "emitente.endereco.cidade"
    source: "emit.endereco.xMun"
    
  - target: "emitente.endereco.uf"
    source: "emit.endereco.UF"
    
  - target: "emitente.endereco.cep"
    source: "emit.endereco.CEP"
    transformer: "cep"
    
  # Destinatário
  - target: "destinatario.cnpj"
    source: "dest.CNPJ"
    transformer: "cnpj"
    
  - target: "destinatario.cpf"
    source: "dest.CPF"
    transformer: "cpf"
    
  - target: "destinatario.razao_social"
    source: "dest.xNome"
    
  # Itens (lista)
  - target: "itens"
    source: "det"
    type: "list"
    item_mappings:
      - target: "numero_item"
        source: "nItem"
        
      - target: "codigo_produto"
        source: "prod.cProd"
        
      - target: "descricao"
        source: "prod.xProd"
        
      - target: "ncm"
        source: "prod.NCM"
        
      - target: "cfop"
        source: "prod.CFOP"
        
      - target: "unidade"
        source: "prod.uCom"
        
      - target: "quantidade"
        source: "prod.qCom"
        transformer: "decimal"
        params:
          precision: 4
          
      - target: "valor_unitario"
        source: "prod.vUnCom"
        transformer: "currency"
        
      - target: "valor_total"
        source: "prod.vProd"
        transformer: "currency"
        
  # Totais
  - target: "totais.valor_produtos"
    source: "total.vProd"
    transformer: "currency"
    
  - target: "totais.valor_frete"
    source: "total.vFrete"
    transformer: "currency"
    
  - target: "totais.valor_desconto"
    source: "total.vDesc"
    transformer: "currency"
    
  - target: "totais.valor_nota"
    source: "total.vNF"
    transformer: "currency"
    
  - target: "totais.base_icms"
    source: "total.vBC"
    transformer: "currency"
    
  - target: "totais.valor_icms"
    source: "total.vICMS"
    transformer: "currency"

# Valores default quando campo não existe no XML
defaults:
  emitente.nome_fantasia: null
  destinatario.cpf: null
```

### 5.2 Exemplo de Output

Dado o template acima, o output seria:

```json
{
  "numero_nota": "123456",
  "serie": "1",
  "data_emissao": "16/01/2026",
  "chave_acesso": "35260112345678000199550010001234561123456789",
  "emitente": {
    "cnpj": "12345678000199",
    "razao_social": "EMPRESA EXEMPLO LTDA",
    "nome_fantasia": "EXEMPLO",
    "inscricao_estadual": "123456789012",
    "endereco": {
      "logradouro": "RUA EXEMPLO",
      "numero": "100",
      "cidade": "SAO PAULO",
      "uf": "SP",
      "cep": "01234567"
    }
  },
  "destinatario": {
    "cnpj": "98765432000188",
    "cpf": null,
    "razao_social": "CLIENTE EXEMPLO S/A"
  },
  "itens": [
    {
      "numero_item": 1,
      "codigo_produto": "PROD001",
      "descricao": "PRODUTO EXEMPLO",
      "ncm": "12345678",
      "cfop": "5102",
      "unidade": "UN",
      "quantidade": 10.0000,
      "valor_unitario": 100.00,
      "valor_total": 1000.00
    }
  ],
  "totais": {
    "valor_produtos": 1000.00,
    "valor_frete": 50.00,
    "valor_desconto": 0.00,
    "valor_nota": 1050.00,
    "base_icms": 1000.00,
    "valor_icms": 180.00
  }
}
```

---

## 6. Transformers Disponíveis

| Transformer | Descrição | Parâmetros |
|-------------|-----------|------------|
| `date` | Formata datetime | `format`: strftime format |
| `cnpj` | Formata CNPJ | `format`: "raw" ou "formatted" |
| `cpf` | Formata CPF | `format`: "raw" ou "formatted" |
| `cep` | Formata CEP | `format`: "raw" ou "formatted" |
| `currency` | Formata valor monetário | `precision`, `locale` |
| `decimal` | Formata decimal | `precision` |
| `uppercase` | Converte para maiúsculas | - |
| `lowercase` | Converte para minúsculas | - |
| `trim` | Remove espaços | - |
| `concat` | Concatena campos | `fields`, `separator` |
| `default` | Valor default se nulo | `value` |
| `map` | Mapeia valores | `mapping`: dict de/para |

---

## 7. Fluxo Completo de Processamento

```mermaid
sequenceDiagram
    autonumber
    participant W as xml_parser_worker
    participant E as NFeExtractor
    participant V as XSD Validator
    participant T as TemplateEngine
    participant R as Template Registry
    participant DB as MongoDB

    W->>E: extract(xml_bytes)
    E->>V: validate(xml_bytes)
    V-->>E: ValidationResult (ok)
    E->>E: parse XML nodes
    E-->>W: NFeRaw (dados completos)

    W->>R: get_template(tenant_template_id)
    R-->>W: Template config

    W->>T: render(nfe_raw, template)
    T->>T: apply_mappings()
    T->>T: apply_transformers()
    T-->>W: JSON output (formato cliente)

    W->>DB: save nfe_canonical (NFeRaw)
    W->>DB: save nfe_autofill (JSON output)
```

---

## 8. Configuração por Tenant

Cada tenant pode ter seu próprio template configurado:

```mermaid
erDiagram
    TENANT {
        string tenant_id PK
        string name
        string default_template_id FK
    }

    TEMPLATE {
        string template_id PK
        string name
        string version
        json mappings
        json transforms
        json defaults
        datetime created_at
        datetime updated_at
    }

    TENANT_TEMPLATE {
        string tenant_id FK
        string template_id FK
        bool is_default
    }

    TENANT ||--o{ TENANT_TEMPLATE : has
    TEMPLATE ||--o{ TENANT_TEMPLATE : used_by
```

---

## 9. Estrutura de Pastas

```
src/nfe_processor/
├── parsers/
│   ├── __init__.py
│   ├── extractor.py          # INFeExtractor interface
│   ├── lxml_extractor.py     # Implementação lxml
│   ├── xsd_validator.py      # Validação XSD
│   └── xsd/                   # Arquivos XSD
│       ├── nfe_v4.00.xsd
│       └── ...
├── templates/
│   ├── __init__.py
│   ├── engine.py             # ITemplateEngine interface
│   ├── jinja_engine.py       # Implementação com Jinja2
│   ├── registry.py           # Template Registry
│   ├── transformers/
│   │   ├── __init__.py
│   │   ├── base.py           # ITransformer interface
│   │   ├── date.py
│   │   ├── document.py       # CNPJ, CPF, CEP
│   │   ├── currency.py
│   │   └── string.py
│   └── definitions/          # Templates YAML
│       ├── legacy_api.yaml
│       ├── minimal.yaml
│       └── full.yaml
├── schemas/
│   ├── __init__.py
│   ├── nfe_raw.py            # NFeRaw e sub-models
│   ├── template.py           # Template, FieldMapping
│   └── ...
```

---

## 10. Próximos Passos

1. **Definir o JSON esperado** — Você precisa me passar o formato que o consumidor atual espera
2. **Criar o primeiro Template** — Baseado no formato existente
3. **Implementar NFeRaw** — Modelo completo de extração
4. **Implementar TemplateEngine** — Motor de transformação
5. **Implementar Transformers** — Funções de conversão

---

## 11. Perguntas Pendentes

Para criar o template correto:

1. **Qual o formato JSON atual?** (exemplo completo)
2. **Há campos calculados?** (ex: total = soma dos itens)
3. **Há campos que vêm de fora do XML?** (ex: ID interno, timestamp de processamento)
4. **Formatos de data/número?** (ex: "DD/MM/YYYY" ou "YYYY-MM-DD", decimal com "." ou ",")
5. **Como são os campos opcionais?** (null, string vazia, ou omitidos?)
