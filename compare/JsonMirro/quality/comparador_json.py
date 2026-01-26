import json
import difflib
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict


TRADUCOES_CAMPOS = {
    "declaration": "Declaração",
    "taxpayer_identification": "Identificação do Contribuinte",
    "assets_declaration": "Bens e Direitos",
    "debts_and_encumbrances": "Dívidas e Ônus Reais",
    "exempt_income": "Rendimentos Isentos",
    "exclusive_taxation_income": "Tributação Exclusiva",
    "income_from_individual_abroad": "Rendimentos PF/Exterior",
    "income_from_legal_person": "Rendimentos PJ",
    "income_from_legal_person_to_holder": "Rendimentos PJ (Titular)",
    "income_from_legal_person_to_dependents": "Rendimentos PJ (Dependentes)",
    "income_suspended_tax": "Rendimentos com Exigibilidade Suspensa",
    "rra_incomes": "RRA",
    "declaration_summary": "Resumo da Declaração",
    "tax_calculation": "Cálculo do Imposto",
    "tax_paid_withheld": "Imposto Pago/Retido",
    "payments_made": "Pagamentos Efetuados",
    "donations_made": "Doações Efetuadas",
    "political_donations": "Doações Políticas",
    "patrimonial_evolution": "Evolução Patrimonial",
    "complementary_info": "Informações Complementares",
    "estate": "Espólio",
    "rural_activity": "Atividade Rural",
    "capital_gains": "Ganhos de Capital",
    "variable_income": "Renda Variável",
    "total_value": "Valor Total",
    "valid_total": "Total Válido",
    "equity_evolution": "Evolução Patrimonial",
    "items": "Itens",
    "subsections": "Subseções",
    "total_values": "Valores Totais",
    "cpf": "CPF",
    "name": "Nome",
    "description": "Descrição",
    "value": "Valor",
    "amount": "Valor",
    "code": "Código",
    "id": "ID",
    "page": "Página",
    "contact_and_address": "Contato e Endereço",
    "spouse": "Cônjuge",
    "dependents": "Dependentes",
    "alimony": "Alimentandos",
    "occupation_nature": "Natureza da Ocupação",
    "main_occupation": "Ocupação Principal",
    "street_address": "Logradouro",
    "number": "Número",
    "complement": "Complemento",
    "neighborhood": "Bairro",
    "city": "Cidade",
    "uf": "UF",
    "zip_code": "CEP",
    "phone": "Telefone",
    "email": "E-mail",
    "cell_phone": "Celular",
    "birth_date": "Data de Nascimento",
    "asset_group_code": "Grupo do Bem",
    "asset_code": "Código do Bem",
    "asset_description": "Discriminação do Bem",
    "before_year_asset_value": "Situação Ano Anterior",
    "current_year_asset_value": "Situação Ano Atual",
    "country_code": "Código do País",
    "country_name": "Nome do País",
    "payer_name": "Nome da Fonte Pagadora",
    "payer_cnpj": "CNPJ da Fonte Pagadora",
    "beneficiary": "Beneficiário",
    "gross_revenue": "Receita Bruta",
    "funding_expenses": "Despesas de Custeio",
    "month": "Mês",
    "participation": "Participação",
    "exploration_condition": "Condição de Exploração",
    "area": "Área",
    "cib": "CIB",
    "participants": "Participantes",
    "participant_name": "Nome do Participante",
    "foreigner": "Estrangeiro",
    "tax_withheld_at_source": "Imposto Retido na Fonte",
    "official_social_security_contribution": "Contribuição Previdenciária Oficial",
    "thirteenth_salary": "13º Salário",
    "irrf_on_thirteenth_salary": "IRRF sobre 13º Salário",
    "income_from_legal_person": "Rendimentos Recebidos de PJ",
    "tax_base": "Base de Cálculo",
    "calculated_tax": "Imposto Calculado",
    "tax_due": "Imposto Devido",
    "tax_to_refund": "Imposto a Restituir",
    "effective_rate": "Alíquota Efetiva",
    "deductions": "Deduções",
    "quantity": "Quantidade",
    "unit_cost": "Custo Unitário",
    "acquisition_cost": "Custo de Aquisição",
    "sale_value": "Valor de Venda",
    "net_gain": "Ganho Líquido",
    "tax_paid": "Imposto Pago",
    "losses": "Prejuízos",
    "currency_code": "Código da Moeda",
    "currency_name": "Nome da Moeda",
    "variation": "Variação",
    "financial_assets": "Ativos Financeiros",
    "currency_variation": "Variação Cambial",
    "profits_and_dividends": "Lucros e Dividendos",
    "savings_accounts_mortgage_lci_lca_cra_cri": "Poupança/LCI/LCA/CRI/CRA",
    "net_gains_from_variable_income_stocks_futures_and_reits": "Ganhos Líquidos Renda Variável",
    "income_from_financial_investments": "Rendimentos Aplicações Financeiras",
    "normalized_cpf": "CPF Normalizado",
    "exercise_year": "Ano de Exercício",
    "calendar_year": "Ano Calendário",
    "type_ir": "Tipo de Declaração",
    "voter_id": "Título de Eleitor",
    "has_spouse": "Possui Cônjuge",
    "ex_resident": "Ex-Residente",
    "data_change": "Alteração de Dados",
    "serious_disease": "Doença Grave",
    "receipt_number": "Número do Recibo",
    "last_receipt_number": "Número do Recibo Anterior",
    "relationship_description": "Descrição do Relacionamento",
    "date_of_birth": "Data de Nascimento",
    "lives_with_taxpayer": "Mora com o Titular",
    "total_deduction": "Dedução Total",
    "resident": "Residente",
    "process_number": "Número do Processo",
    "court": "Vara",
    "jurisdiction": "Comarca",
    "alimony_from_cpf": "CPF do Alimentante",
    "alimony_from_name": "Nome do Alimentante",
    "decision_date": "Data da Decisão",
    "country_valid": "País Válido",
    "additional_info": "Informações Adicionais",
    "acquisition_date": "Data de Aquisição",
    "registry_office": "Cartório",
    "registration_number": "Matrícula",
    "registration_book": "Livro de Registro",
    "account": "Conta",
    "bank": "Banco",
    "agency": "Agência",
    "bem_ou_direito_pertencente_ao": "Bem Pertencente Ao",
    "year_before_last_total_value": "Valor Total Ano Anterior ao Anterior",
    "last_year_total_value": "Valor Total Ano Anterior",
    "current_year_total_value": "Valor Total Ano Atual",
    "amount_of_codes_equal_to_amount_of_values": "Qtd Códigos Igual Qtd Valores",
    "extraction_method": "Método de Extração",
    "beneficiary_type": "Tipo de Beneficiário",
    "total_tax": "Imposto Total",
    "income_from_individual": "Rendimentos de PF",
    "income_from_abroad": "Rendimentos do Exterior",
    "rra_total": "Total RRA",
    "rra_tax_withheld": "Imposto Retido RRA",
    "total_deductions": "Total de Deduções",
    "dependents_deduction": "Dedução de Dependentes",
    "education_expenses": "Despesas com Instrução",
    "medical_expenses": "Despesas Médicas",
    "alimony_judicial": "Pensão Alimentícia Judicial",
    "alimony_public_deed": "Pensão Alimentícia Escritura Pública",
    "social_security_contributions": "Contribuição Previdenciária",
    "complementary_social_security": "Previdência Complementar",
    "withheld_tax_holder": "Imposto Retido (Titular)",
    "withheld_tax_dependents": "Imposto Retido (Dependentes)",
    "carnet_leao_holder": "Carnê-Leão (Titular)",
    "carnet_leao_dependents": "Carnê-Leão (Dependentes)",
    "complementary_tax": "Imposto Complementar",
    "tax_paid_abroad": "Imposto Pago no Exterior",
    "tax_withheld_abroad": "Imposto Retido no Exterior",
    "installments": "Parcelas",
    "number_of_installments": "Número de Parcelas",
    "installment_value": "Valor da Parcela",
    "debts_previous_year": "Dívidas Ano Anterior",
    "debts_current_year": "Dívidas Ano Atual",
    "other_totals": "Outros Totais",
    "non_taxable_incomes_total": "Total Rendimentos Isentos",
    "exclusive_taxation_incomes_total": "Total Tributação Exclusiva",
    "income_from_individual_total": "Total Rendimentos PF",
    "income_from_abroad_total": "Total Rendimentos Exterior",
    "income_from_legal_person_to_dependents_total": "Total Rendimentos PJ (Dependentes)",
    "total_taxable_incomes": "Total Rendimentos Tributáveis",
    "withheld_tax": "Imposto Retido",
    "sub_items": "Subitens",
    "payments": "Pagamentos",
    "donations": "Doações",
    "patrimonial_difference": "Diferença Patrimonial",
    "name_and_location": "Nome e Localização",
    "year_before_last_value": "Valor Ano Anterior ao Anterior",
    "last_year_value": "Valor Ano Anterior",
    "paid_value_in_last_year": "Valor Pago no Ano Anterior",
    "item": "Item",
    "variable_income_holder": "Renda Variável (Titular)",
    "variable_income_dependents": "Renda Variável (Dependentes)",
    "real_estate_fund_holder": "Fundo Imobiliário (Titular)",
    "real_estate_fund_dependents": "Fundo Imobiliário (Dependentes)",
    "capital_gains_operations": "Operações Ganhos de Capital",
    "total_variation": "Variação Total",
    "spouse_cpf": "CPF do Cônjuge",
    "spouse_name": "Nome do Cônjuge",
    "spouse_birth_date": "Data de Nascimento do Cônjuge",
    "spouse_voter_id": "Título de Eleitor do Cônjuge",
    "canonical_block": "Bloco Canônico",
    "canonical_block_code": "Código do Bloco Canônico",
    "canonical_session": "Sessão Canônica",
    "canonical_session_code": "Código da Sessão Canônica",
    "canonical_subsession": "Subsessão Canônica",
    "canonical_subsession_code": "Código da Subsessão Canônica",
    "canonical_priority": "Prioridade Canônica",
    "canonical_description": "Descrição Canônica",
    "section_name": "Nome da Seção",
    "pages_with_problems": "Páginas com Problemas",
    "raw_text": "Texto Bruto",
    "extraction_metrics": "Métricas de Extração",
    "items_extracted": "Itens Extraídos",
    "items_expected": "Itens Esperados",
    "extraction_score": "Pontuação de Extração",
    "completeness_score": "Pontuação de Completude",
    "validation_score": "Pontuação de Validação",
    "valid": "Válido"
}


def carregar_json(caminho_arquivo):
    """Carrega um arquivo JSON e retorna seu conteúdo."""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo não encontrado em '{caminho_arquivo}'")
        return None
    except json.JSONDecodeError:
        print(f"Erro: Falha ao decodificar o JSON em '{caminho_arquivo}'. Verifique se o formato é válido.")
        return None


def extrair_dados_relevantes(obj):
    """Tenta extrair o objeto 'declaration' de estruturas conhecidas para focar a comparação."""
    if not isinstance(obj, dict):
        return obj
        
    # Caminhos possíveis para a declaração (prioridade para estruturas conhecidas)
    caminhos = [
        ['data', 'ir_response', 'declaration'],
        ['raw', 'ir_response', 'declaration'],
        ['ir_response', 'declaration'],
        ['declaration']
    ]
    
    for caminho in caminhos:
        temp = obj
        encontrou = True
        for chave in caminho:
            if isinstance(temp, dict) and chave in temp:
                temp = temp[chave]
            else:
                encontrou = False
                break
        if encontrou:
            return temp
            
    return obj


def normalizar_estrutura_declaracao(decl):
    """
    Normaliza a estrutura da declaração.
    Se estiver no formato de blocos/sessões (JsonMirro raw), achata para o formato simplificado
    compatível com o Gabarito.
    """
    if not isinstance(decl, dict):
        return decl
    
    # Verifica se é a estrutura complexa com 'blocks'
    if 'blocks' in decl:
        flat_decl = {}
        
        # Preserva campos raiz que não são blocos (ex: total_value, valid_total)
        for k, v in decl.items():
            if k != 'blocks':
                flat_decl[k] = v
                
        # Função auxiliar para percorrer a árvore de blocos/sessões
        def coletar_secoes(obj):
            if isinstance(obj, dict):
                # Se encontrou 'sections', extrai o conteúdo delas
                if 'sections' in obj and isinstance(obj['sections'], dict):
                    for sec_key, sec_val in obj['sections'].items():
                        # Prioridade para o conteúdo da seção
                        flat_decl[sec_key] = sec_val
                
                # Continua descendo em 'blocks', 'sessions', 'subsessions'
                for key in ['blocks', 'sessions', 'subsessions']:
                    if key in obj and isinstance(obj[key], dict):
                        for sub_key, sub_val in obj[key].items():
                            coletar_secoes(sub_val)
                            
        coletar_secoes(decl)
        return flat_decl
        
    return decl


def normalizar_texto_para_comparacao(texto):
    """Normaliza espaçamento ao redor de pontuação para comparação.
    
    Isso permite ignorar diferenças de formatação como:
    - ' , ' vs ','
    - ' . ' vs '.'
    - ' / ' vs '/'
    - 'R $ ' vs 'R$'
    - '( ' vs '('
    - OCR: '4O' vs '40' (letra O vs zero)
    """
    if not isinstance(texto, str):
        return texto
    
    # Normaliza espaços ao redor de ponto-e-vírgula para "; "
    texto = re.sub(r'\s*;\s*', '; ', texto)
    
    # Remove espaço ANTES de pontuação (exceto ponto-e-vírgula já tratado)
    texto = re.sub(r'\s+([,.:%)!\]])', r'\1', texto)
    
    # Remove espaço DEPOIS de parêntese/colchete de abertura
    texto = re.sub(r'([\[(])\s+', r'\1', texto)
    
    # Normaliza espaços ao redor de barra e hífen
    texto = re.sub(r'\s*/\s*', '/', texto)
    texto = re.sub(r'\s*-\s*', '-', texto)
    
    # Normaliza R $ para R$
    texto = re.sub(r'R\s*\$', 'R$', texto)
    
    # OCR: Normaliza O (letra) para 0 (zero) em contextos numéricos
    # Padrões como "4O" -> "40", "2O" -> "20" (dígito seguido de O)
    texto = re.sub(r'(\d)O\b', r'\g<1>0', texto)
    texto = re.sub(r'\bO(\d)', r'0\1', texto)
    
    # Múltiplos espaços para um
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto.lower()


def valores_equivalentes(val1, val2):
    """Verifica se dois valores são equivalentes (considera null == 'N/A' == {} == false para campos opcionais)."""
    # null e "N/A" são considerados equivalentes
    if val1 is None and val2 == "N/A":
        return True
    if val2 is None and val1 == "N/A":
        return True
    if val1 == "N/A" and val2 == "N/A":
        return True
    if val1 is None and val2 is None:
        return True
    # null e {} (objeto vazio) são considerados equivalentes
    if val1 is None and val2 == {}:
        return True
    if val2 is None and val1 == {}:
        return True
    # "N/A" e {} são considerados equivalentes
    if val1 == "N/A" and val2 == {}:
        return True
    if val2 == "N/A" and val1 == {}:
        return True
    # "N/A" e False são considerados equivalentes (campos booleanos opcionais)
    if val1 == "N/A" and val2 is False:
        return True
    if val2 == "N/A" and val1 is False:
        return True
    return False


def normalizar_valor(valor, chave=None):
    """Normaliza valores para comparação (strings, números, telefones)."""
    if isinstance(valor, str):
        # Normalização específica para campos numéricos formatados (CPF, CNPJ, Telefone, CEP)
        if chave and any(k in chave.lower() for k in ['phone', 'cep', 'zip', 'cpf', 'cnpj']):
             # Remove tudo que não é dígito
             digits = "".join(filter(str.isdigit, valor))
             if digits: # Se sobrou algo, retorna apenas os dígitos
                 return digits
        # Aplica normalização de pontuação e espaçamento
        return normalizar_texto_para_comparacao(valor)
    return valor


def calcular_similaridade(item1, item2):
    """Calcula um score de similaridade entre dois dicionários para pareamento inteligente."""
    if not isinstance(item1, dict) or not isinstance(item2, dict):
        return 1.0 if item1 == item2 else 0.0
    
    chaves1 = set(item1.keys())
    chaves2 = set(item2.keys())
    todas_chaves = chaves1 | chaves2
    chaves_comuns = chaves1 & chaves2
    
    if not todas_chaves: return 1.0
    
    matches = 0
    # Chaves que geralmente são geradas e não servem para matching de conteúdo
    chaves_ignoradas = {'id', '_id', 'uuid', 'pk', 'page', 'created_at', 'updated_at'}
    
    chaves_relevantes = [k for k in todas_chaves if k not in chaves_ignoradas]
    if not chaves_relevantes: return 0.0 

    for chave in chaves_relevantes:
        if chave in chaves_comuns:
            val1 = item1[chave]
            val2 = item2[chave]
            
            # Comparação relaxada para strings e números
            if val1 == val2:
                matches += 1
            elif isinstance(val1, str) and isinstance(val2, str):
                if normalizar_valor(val1, chave) == normalizar_valor(val2, chave):
                    matches += 1
            elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                 if abs(val1 - val2) < 0.01:
                     matches += 1
            # Tenta converter string numérica para float
            elif str(val1).replace(',','.').replace(' ','') == str(val2).replace(',','.').replace(' ',''):
                 matches += 1

    return matches / len(chaves_relevantes)


def parear_listas(lista_esperada, lista_atual):
    """
    Parea itens de duas listas baseado em similaridade de conteúdo.
    Retorna: (pares_correspondentes, itens_ausentes, itens_extras)
    """
    # 1. Tenta parear por ID se ambos tiverem e houver interseção significativa
    ids_esperados = {item.get('id') for item in lista_esperada if isinstance(item, dict) and 'id' in item}
    ids_atuais = {item.get('id') for item in lista_atual if isinstance(item, dict) and 'id' in item}
    
    usar_id = False
    if ids_esperados and ids_atuais:
        intersecao = ids_esperados.intersection(ids_atuais)
        # Se pelo menos 30% dos IDs batem, assumimos que o ID é confiável
        if len(intersecao) / max(len(ids_esperados), 1) > 0.3:
            usar_id = True

    if usar_id:
        mapa_esperado = {item['id']: item for item in lista_esperada if 'id' in item}
        mapa_atual = {item['id']: item for item in lista_atual if 'id' in item}
        
        pares = []
        ausentes = [item for item in lista_esperada if 'id' not in item or item['id'] not in mapa_atual]
        extras = [item for item in lista_atual if 'id' not in item or item['id'] not in mapa_esperado]
        
        for id_val, item_exp in mapa_esperado.items():
            if id_val in mapa_atual:
                pares.append((item_exp, mapa_atual[id_val]))
        
        return pares, ausentes, extras

    # 2. Fallback: Pareamento por similaridade (Best Match)
    nao_pareados_exp = list(enumerate(lista_esperada))
    nao_pareados_atl = list(enumerate(lista_atual))
    candidatos = []
    
    for i, exp in nao_pareados_exp:
        for j, atl in nao_pareados_atl:
            score = calcular_similaridade(exp, atl)
            if score > 0.6: # Limiar de similaridade para considerar o mesmo item modificado
                candidatos.append((score, i, j))
    
    # Ordena pelos pares mais similares primeiro
    candidatos.sort(key=lambda x: x[0], reverse=True)
    
    usados_exp = set()
    usados_atl = set()
    pares = []
    
    for _, i, j in candidatos:
        if i not in usados_exp and j not in usados_atl:
            pares.append((lista_esperada[i], lista_atual[j]))
            usados_exp.add(i)
            usados_atl.add(j)
            
    ausentes = [lista_esperada[i] for i, _ in nao_pareados_exp if i not in usados_exp]
    extras = [lista_atual[j] for j, _ in nao_pareados_atl if j not in usados_atl]
    
    return pares, ausentes, extras


def comparar_objetos(obj1, obj2, caminho_atual, diferencas):
    """Compara recursivamente dois objetos Python (dicionários, listas, etc.)."""
    
    # Compara dicionários
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        # Chaves para ignorar na comparação direta (metadados que variam)
        chaves_ignoradas = {
            '_comment', 'created_at', 'updated_at', 'executionId', 'fileSize', 'filename', 'raw_text',
            'canonical_block', 'canonical_block_code', 'canonical_session', 'canonical_session_code',
            'canonical_subsession', 'canonical_subsession_code', 'canonical_priority', 'canonical_description',
            'extraction_metrics'
        }

        todas_chaves = list(obj1.keys()) + [k for k in obj2.keys() if k not in obj1]
        
        for chave in todas_chaves:
            if chave in chaves_ignoradas or chave.startswith('_'):
                continue
            
            novo_caminho = f"{caminho_atual}.{chave}"

            if chave not in obj2:
                diferencas.append({
                    "caminho": novo_caminho,
                    "tipo": "Chave Ausente no JSON Atual",
                    "esperado": obj1[chave],
                    "atual": "N/A"
                })
            elif chave not in obj1:
                # Ignora chaves extras quando o valor é "N/A" ou False (campos opcionais não preenchidos)
                valor_extra = obj2[chave]
                if valor_extra not in ("N/A", False):
                    diferencas.append({
                        "caminho": novo_caminho,
                        "tipo": "Chave Extra no JSON Atual",
                        "esperado": "N/A",
                        "atual": valor_extra
                    })
            else:
                comparar_objetos(obj1[chave], obj2[chave], novo_caminho, diferencas)

    # Compara listas
    elif isinstance(obj1, list) and isinstance(obj2, list):
        pares, ausentes, extras = parear_listas(obj1, obj2)
        
        # Compara os pares encontrados
        for i, (item_exp, item_atl) in enumerate(pares):
            # Tenta criar um label legível para o caminho
            label = f"item_{i}"
            if isinstance(item_exp, dict):
                # Usa campos identificadores se existirem
                label = item_exp.get('code') or item_exp.get('name') or item_exp.get('description') or label
                label = str(label)[:30] # Limita tamanho
                # Remove caracteres inválidos para caminho
                label = re.sub(r'[^a-zA-Z0-9_-]', '_', label)
            
            comparar_objetos(item_exp, item_atl, f"{caminho_atual}[{label}]", diferencas)
            
        for item in ausentes:
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Item de Lista Ausente",
                "esperado": item,
                "atual": "N/A"
            })
            
        for item in extras:
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Item de Lista Extra",
                "esperado": "N/A",
                "atual": item
            })

    # Compara valores
    else:
        campo_atual_nome = caminho_atual.split('.')[-1]
        
        # Ignora ID se for diferente (geralmente UUID vs Hash)
        if caminho_atual.endswith('.id') or caminho_atual.endswith('._id'):
            return
        
        # Verifica equivalência null/N/A primeiro
        if valores_equivalentes(obj1, obj2):
            return

        # Normalização para comparação
        val1 = normalizar_valor(obj1, campo_atual_nome)
        val2 = normalizar_valor(obj2, campo_atual_nome)

        # Validação de Tipo (Bug Crítico)
        # Se um é número e o outro é string que não parece número
        if isinstance(obj1, (int, float)) and isinstance(obj2, str) and not re.match(r'^[\d\.,\s]+$', obj2):
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "BUG: Tipo de Dado Inválido",
                "esperado": obj1,
                "atual": f"{obj2} (String)"
            })
            return

        # Comparação Numérica Flexível
        if isinstance(val1, (int, float)) or isinstance(val2, (int, float)):
            try:
                # Tenta converter ambos para float para comparar
                v1_float = float(str(obj1).replace(',', '.')) if obj1 is not None else 0
                v2_float = float(str(obj2).replace(',', '.')) if obj2 is not None else 0
                if abs(v1_float - v2_float) < 0.01:
                    return # São iguais numericamente
            except ValueError:
                pass # Falha na conversão, segue para comparação padrão

        if val1 != val2:
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Valor Divergente",
                "esperado": obj1,
                "atual": obj2
            })

def gerar_diff_html(texto1, texto2):
    """Gera HTML com highlight das diferenças entre duas strings."""
    if not isinstance(texto1, str) or not isinstance(texto2, str):
        return f"<span class='val-old'>{texto1}</span> <br>⬇️<br> <span class='val-new'>{texto2}</span>"
    
    seqm = difflib.SequenceMatcher(None, texto1, texto2)
    html = []
    for opcode, a0, a1, b0, b1 in seqm.get_opcodes():
        if opcode == 'equal':
            html.append(texto1[a0:a1])
        elif opcode == 'insert':
            html.append(f"<span class='diff-add'>{texto2[b0:b1]}</span>")
        elif opcode == 'delete':
            html.append(f"<span class='diff-del'>{texto1[a0:a1]}</span>")
        elif opcode == 'replace':
            html.append(f"<span class='diff-del'>{texto1[a0:a1]}</span><span class='diff-add'>{texto2[b0:b1]}</span>")
    return "".join(html)


def gerar_relatorio_html(diferencas, arquivo_esperado, arquivo_atual, secoes_analisadas=None):
    """Gera um relatório de diferenças em formato HTML."""
    from collections import defaultdict
    from os.path import basename

    nome_arquivo_esperado = basename(arquivo_esperado)
    nome_arquivo_atual = basename(arquivo_atual)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def traduzir_campo(texto):
        """Traduz uma chave ou caminho de chaves para Português."""
        if not isinstance(texto, str):
            return str(texto)
        
        partes = texto.split('.')
        partes_traduzidas = []
        
        for parte in partes:
            match = re.match(r'(\w+)(\[\d+\])', parte)
            if match:
                chave, indice = match.groups()
                chave_trad = TRADUCOES_CAMPOS.get(chave, chave.replace('_', ' ').title())
                partes_traduzidas.append(f"{chave_trad}{indice}")
            else:
                chave_trad = TRADUCOES_CAMPOS.get(parte, parte.replace('_', ' ').title())
                partes_traduzidas.append(chave_trad)
                
        return " > ".join(partes_traduzidas)

    # Estilos CSS para o relatório
    estilos_css = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 0; background-color: #f8f9fa; color: #212529; }
        .container { max-width: 1200px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }
        h1, h2, h3 { color: #343a40; }
        h1 { border-bottom: 2px solid #dee2e6; padding-bottom: 10px; }
        h1 + h2 { border-top: none; margin-top: -10px; font-size: 1.5em; color: #6c757d; }
        .summary { background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 15px; }
        .summary-item { display: flex; align-items: center; font-size: 0.95em; color: #495057; }
        .summary-item strong { margin-right: 8px; }
        .summary-item code { background-color: #e9ecef; padding: 3px 6px; border-radius: 4px; }
        .summary-file { padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; background-color: #fff; }
        .summary-file strong { display: block; margin-bottom: 8px; color: #343a40; font-size: 0.9em; }
        .summary-file code { font-size: 0.9em; word-break: break-all; cursor: help; }
        .summary-icon { margin-right: 10px; font-size: 1.2em; }
        
        /* Diff Highlighting */
        .diff-add { background-color: #d4edda; color: #155724; text-decoration: none; }
        .diff-del { background-color: #f8d7da; color: #721c24; text-decoration: line-through; opacity: 0.7; }
        .actions { margin-bottom: 20px; }
        .actions button { padding: 8px 15px; font-size: 0.9em; cursor: pointer; border: 1px solid #ced4da; border-radius: 5px; background-color: #f8f9fa; margin-right: 10px; }
        .actions button:hover { background-color: #e2e6ea; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-top: 15px; }
        
        /* --- Section Status List --- */
        .section-status-list ul {
            list-style-type: none;
            margin: 0;
            padding: 0;
        }
        .section-status-list li {
            padding: 0;
        }
        /* Indentation for nested levels, removing the old border */
        .section-status-list ul ul {
            padding-left: 25px;
        }
        .tree-toggle {
            cursor: pointer;
            margin-right: 5px;
            color: #6c757d;
            font-size: 0.8em;
            width: 20px;
            text-align: center;
            display: inline-block;
        }
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            margin: 4px 0;
            background-color: #fff;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            transition: background-color 0.2s ease, box-shadow 0.2s ease;
        }
        .section-header:hover {
            background-color: #f8f9fa;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        }
        .section-status-list a .section-header:hover {
            cursor: pointer;
            background-color: #e9ecef;
            box-shadow: 0 3px 6px rgba(0,0,0,0.08);
        }
        .section-header.ok {
            border-left: 5px solid #28a745;
        }
        .section-header.error {
            border-left: 5px solid #dc3545;
        }
        .section-name {
            font-weight: 500;
            font-size: 0.95em;
            color: #343a40;
        }
        .section-badge {
            font-size: 0.75em;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 15px;
            color: #fff;
            min-width: 90px;
            text-align: center;
        }
        .badge-ok { background-color: #28a745; }
        .badge-error { background-color: #dc3545; }
        /* --- End Section Status List --- */

        /* --- Copy Button --- */
        .copy-btn {
            background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 4px;
            cursor: pointer; padding: 5px 8px; font-size: 0.9em;
        }
        .copy-btn:hover { background-color: #e0e0e0; }
        .copy-btn.copied { background-color: #28a745; color: white; border-color: #28a745; }

        .group-header {
            background-color: #f2f2f2;
            padding: 10px 15px;
            margin-top: 20px;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .group-header:hover { background-color: #e9ecef; }
        .group-title { font-weight: bold; }
        .group-priority { font-size: 0.85em; font-weight: bold; margin-left: 10px; }
        .group-summary { font-weight: normal; font-size: 0.9em; color: #495057; }
        .group-content { display: none; padding-left: 20px; border-left: 2px solid #dee2e6; }
        .stat-card { background-color: #fff; padding: 15px; border-radius: 5px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stat-card h3 { margin: 0 0 5px 0; font-size: 1.5em; }
        .stat-card p { margin: 0; color: #6c757d; }
        .diff-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .diff-table th, .diff-table td { border: 1px solid #dee2e6; padding: 12px; text-align: left; vertical-align: top; }
        .diff-table th { background-color: #f2f2f2; font-weight: 600; }
        .diff-table tr:nth-child(even) { background-color: #f8f9fa; }
        pre { background-color: #f1f3f5; padding: 8px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; font-size: 0.85em; margin: 0; }
        code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace; }
        .diff-type { font-weight: bold; padding: 5px; border-radius: 4px; color: #fff; text-align: center; }
        .missing { background-color: #dc3545; }
        .extra { background-color: #28a745; }
        .divergent { background-color: #ffc107; color: #212529; }
        .bug { background-color: #6f42c1; color: white; }
        .no-diff { color: #28a745; font-weight: bold; }
        .total-diff { color: #dc3545; font-weight: bold; margin-bottom: 10px; display: block; }
        .priority-high { background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; }
        .priority-medium { background-color: #ffc107; color: #212529; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; }
        .priority-low { background-color: #007bff; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; }
        .bug-marker { display: block; margin-top: 8px; font-size: 0.8em; color: #dc3545; font-weight: bold; }
        .group-header-title { display: flex; align-items: center; gap: 10px; }
        footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
    <script>
        function toggleGroup(element) {
            const content = element.nextElementSibling;
            if (content.style.display === "block") {
                content.style.display = "none";
                element.querySelector('.toggle-icon').innerHTML = '&#x25B6; '; // Seta para a direita
            } else {
                content.style.display = "block";
                element.querySelector('.toggle-icon').innerHTML = '&#x25BC; '; // Seta para baixo
            }
        }

        function toggleAll(expand) {
            const groups = document.querySelectorAll('.group-header');
            groups.forEach(group => {
                const content = group.nextElementSibling;
                const icon = group.querySelector('.toggle-icon');
                if (expand) {
                    content.style.display = 'block';
                    icon.innerHTML = '&#x25BC; ';
                } else {
                    content.style.display = 'none';
                    icon.innerHTML = '&#x25B6; ';
                }
            });
        }

        function copyEvidence(button) {
            const path = button.dataset.path;
            const type = button.dataset.type;
            const expected = JSON.parse(button.dataset.expected);
            const actual = JSON.parse(button.dataset.actual);

            const evidenceText = `
**Tipo de Divergência:** ${type}
**Caminho do Campo:** \`${path}\`

**Valor Esperado:**
\`\`\`json
${JSON.stringify(expected, null, 2)}
\`\`\`

**Valor Atual:**
\`\`\`json
${JSON.stringify(actual, null, 2)}
\`\`\`
---
*Relatório gerado por JsonMirror*`.trim();

            navigator.clipboard.writeText(evidenceText).then(() => {
                const originalText = button.innerHTML;
                button.innerHTML = 'Copiado!';
                button.classList.add('copied');
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.classList.remove('copied');
                }, 1500);
            });
        }

        function toggleTree(element, event) {
            const li = element.closest('li');
            const ul = li.querySelector('ul');
            if (ul) {
                if (ul.style.display === 'none') {
                    ul.style.display = 'block';
                    element.innerHTML = '&#x25BC;';
                } else {
                    ul.style.display = 'none';
                    element.innerHTML = '&#x25B6;';
                }
            }
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
        }
    </script>
    """

    # Cabeçalho do HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JsonMirror</title>
        {estilos_css}
    </head>
    <body>
        <div class="container">
            <h1>JsonMirror</h1><h2>Relatório de Comparação de JSON</h2>
            
            <div class="summary">
                <div class="summary-item">
                    <span class="summary-icon">🗓️</span><strong>Data da Geração:</strong> <code>{timestamp}</code>
                </div>
                <div class="summary-grid">
                    <div class="summary-file">
                        <strong><span class="summary-icon">📄</span>Arquivo de Referência (Esperado)</strong>
                        <code title="{arquivo_esperado}">{nome_arquivo_esperado}</code>
                    </div>
                    <div class="summary-file">
                        <strong><span class="summary-icon">📑</span>Arquivo Analisado (Atual)</strong>
                        <code title="{arquivo_atual}">{nome_arquivo_atual}</code>
                    </div>
                </div>
            </div>
    """
    
    if not diferencas:
        html += '<h2><span class="no-diff">✅ Nenhuma diferença encontrada.</span></h2>'
    else:
        # Calcula as estatísticas
        stats = {
            "missing": 0,
            "extra": 0,
            "divergent": 0,
            "bug": 0
        }
        for diff in diferencas:
            if "Ausente" in diff['tipo']:
                stats["missing"] += 1
            elif "Extra" in diff['tipo']:
                stats["extra"] += 1
            elif "BUG" in diff['tipo']:
                stats["bug"] += 1
            else:
                stats["divergent"] += 1

        html += f"""
            <h2 style="border-top: 2px solid #dee2e6; margin-top: 20px;"><span class="total-diff">❌ Foram encontradas {len(diferencas)} diferenças</span></h2>
            <div class="stats-grid">
                <div class="stat-card"><h3 class="missing">{stats['missing']}</h3><p>Ausentes</p></div>
                <div class="stat-card"><h3 class="extra">{stats['extra']}</h3><p>Extras</p></div>
                <div class="stat-card"><h3 class="divergent">{stats['divergent']}</h3><p>Divergentes</p></div>
                <div class="stat-card"><h3 class="bug" style="color: #6f42c1;">{stats['bug']}</h3><p>Bugs Potenciais</p></div>
            </div>
        
                <div class="actions">
                    <button onclick="toggleAll(true)">Expandir Todos</button>
                    <button onclick="toggleAll(false)">Recolher Todos</button>
                </div>
        """

        # Adiciona o resumo das seções analisadas
        if secoes_analisadas:
            # 1. Construir uma árvore a partir das chaves das seções
            secoes_tree = {}
            for secao_key in sorted(secoes_analisadas):
                partes = secao_key.split('.')
                node = secoes_tree
                for parte in partes:
                    if parte not in node:
                        node[parte] = {'children': {}}
                    node = node[parte]['children']

            # 2. Função recursiva para gerar o HTML da lista aninhada
            def build_section_html(tree, path_prefix=''):
                # Não renderiza um <ul> vazio se não houver filhos
                if not tree:
                    return ''
                
                html_list = '<ul>'
                for key, value in tree.items():
                    current_path = f"{path_prefix}.{key}" if path_prefix else key
                    nome_exibicao = TRADUCOES_CAMPOS.get(key, key.replace('_', ' ').title())
                    
                    # Conta diferenças que começam com o caminho desta seção
                    diffs_count = sum(1 for d in diferencas if d['caminho'].startswith(f"Declaração.{current_path}"))
                    
                    status_class = "error" if diffs_count > 0 else "ok"
                    badge_class = "badge-error" if diffs_count > 0 else "badge-ok"
                    status_text = f"{diffs_count} diferença(s)" if diffs_count > 0 else "OK"

                    # Identifica a chave da seção pai (top-level) para o link da âncora
                    top_level_key = current_path.split('.')[0]
                    anchor_id = f"details-{top_level_key}"

                    has_children = bool(value['children'])
                    toggle_icon = '&#x25BC;' # Seta para baixo (expandido)
                    toggle_style = '' if has_children else 'visibility: hidden;'
                    onclick_attr = 'onclick="toggleTree(this, event)"' if has_children else ''

                    header_html = f"""
                    <div class="section-header {status_class}">
                        <div style="display:flex; align-items:center;">
                            <span class="tree-toggle" style="{toggle_style}" {onclick_attr}>{toggle_icon}</span>
                            <span class="section-name">{nome_exibicao}</span>
                        </div>
                        <span class="section-badge {badge_class}">{status_text}</span>
                    </div>
                    """

                    html_list += '<li>'
                    if diffs_count > 0:
                        onclick_js = f"const el = document.getElementById('{anchor_id}'); if(el && el.nextElementSibling.style.display !== 'block') {{ el.click(); }}"
                        html_list += f'<a href="#{anchor_id}" onclick="{onclick_js}" style="text-decoration: none; color: inherit;">{header_html}</a>'
                    else:
                        html_list += header_html
                    
                    # Chamada recursiva para os filhos (renderizados abaixo do cabeçalho)
                    html_list += build_section_html(value['children'], current_path)
                    
                    html_list += '</li>'
                html_list += '</ul>'
                return html_list

            html += '<div class="content-box"><h3>Status das Seções</h3><div class="section-status-list">'
            html += build_section_html(secoes_tree)
            html += '</div></div>'

        # Define a prioridade para cada tipo de diferença
        priority_map = {
            "BUG: Tipo de Dado Inválido": (0, "Crítica", "bug"),
            "Chave Ausente no JSON Atual": (1, "Alta", "priority-high"),
            "Item de Lista Ausente": (1, "Alta", "priority-high"),
            "Valor Divergente": (2, "Média", "priority-medium"),
            "Chave Extra no JSON Atual": (3, "Baixa", "priority-low"),
            "Item de Lista Extra": (3, "Baixa", "priority-low"),
        }

        # Agrupa as diferenças por Seção (Sessão)
        grouped_diffs = defaultdict(list)
        for diff in diferencas:
            partes = diff['caminho'].split('.')
            if len(partes) >= 2:
                secao_chave_raw = partes[1].split('[')[0]
                secao_titulo = TRADUCOES_CAMPOS.get(secao_chave_raw, secao_chave_raw.replace('_', ' ').title())
            else:
                secao_chave_raw = "estrutura_geral"
                secao_titulo = "Estrutura Geral"
            
            grouped_diffs[(secao_chave_raw, secao_titulo)].append(diff)

        # Calcula a prioridade de cada grupo e prepara para ordenação
        sorted_groups = []
        for (key_raw, parent_path), diffs_in_group in grouped_diffs.items():
            max_priority_level = 3 # Inicia com a menor prioridade
            priority_label = "Baixa"
            priority_class = "priority-low"

            for diff in diffs_in_group:
                level, label, p_class = priority_map.get(diff['tipo'], (2, "Média", "priority-medium"))
                if level < max_priority_level:
                    max_priority_level = level
                    priority_label = label
                    priority_class = p_class
            
            sorted_groups.append({
                "key_raw": key_raw,
                "path": parent_path,
                "priority_level": max_priority_level,
                "priority_label": priority_label,
                "priority_class": priority_class,
                "diffs": diffs_in_group
            })
        
        # A ordenação foi removida para respeitar a ordem de aparição no JSON (estrutura)

        html += '<div class="content-box">'
        html += '<h3>Detalhes das Diferenças</h3>'

        for group in sorted_groups:
            parent_path = group['path']
            diffs_in_group = group['diffs']
            priority_label = group['priority_label']
            priority_class = group['priority_class']
            key_raw = group['key_raw']
            
            anchor_id = f"details-{key_raw}"

            html += f"""
                <div id="{anchor_id}" class="group-header" onclick="toggleGroup(this)">
                    <div class="group-header-title">
                        <span class="toggle-icon">&#x25B6; </span>
                        <span>{parent_path}</span>
                        <span class="{priority_class}">{priority_label} Prioridade</span>
                    </div>
                    <div class="group-summary">{len(diffs_in_group)} diferença(s)</div>
                </div>
                <div class="group-content">
                    <table class="diff-table">
                        <thead>
                            <tr>
                                <th style="width: 30%;">Caminho / Campo</th>
                                <th style="width: 15%;">Tipo da Diferença</th>
                                <th>Valor Esperado</th>
                                <th>Valor Atual</th>
                                <th style="width: 10%;">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            tipo_map = {
                "Chave Ausente no JSON Atual": ("missing", "Ausente"),
                "Item de Lista Ausente": ("missing", "Item Ausente"),
                "Chave Extra no JSON Atual": ("extra", "Extra"),
                "Item de Lista Extra": ("extra", "Item Extra"),
                "Valor Divergente": ("divergent", "Divergente"),
                "BUG: Tipo de Dado Inválido": ("bug", "BUG DE TIPO")
            }

            for diff in diffs_in_group:
                # Exibe o caminho relativo dentro da seção para facilitar a identificação
                partes_caminho = diff['caminho'].split('.')
                if len(partes_caminho) > 2:
                    campo_raw = ".".join(partes_caminho[2:])
                else:
                    campo_raw = partes_caminho[-1]
                
                campo = traduzir_campo(campo_raw)
                tipo_classe, tipo_texto = tipo_map.get(diff['tipo'], ('divergent', diff['tipo']))
                
                # Função auxiliar para formatar os valores
                def format_value(value):
                    if isinstance(value, (dict, list)):
                        return f"<pre><code>{json.dumps(value, indent=2, ensure_ascii=False)}</code></pre>"
                    return f"<code>{json.dumps(value, ensure_ascii=False)}</code>"

                esperado_fmt = format_value(diff['esperado'])
                
                # Se for divergência de valor, mostra diff visual
                if diff['tipo'] == "Valor Divergente" and isinstance(diff['esperado'], str) and isinstance(diff['atual'], str):
                    # Se for muito longo, usa diff visual
                    if len(diff['esperado']) > 20 or len(diff['atual']) > 20:
                        atual_fmt = gerar_diff_html(diff['esperado'], diff['atual'])
                    else:
                        atual_fmt = format_value(diff['atual'])
                else:
                    atual_fmt = format_value(diff['atual'])

                # Prepara os dados brutos para o botão de cópia
                data_path = diff['caminho']
                data_type = diff['tipo']
                # Usa json.dumps para garantir que os dados sejam strings JSON válidas
                data_expected = json.dumps(diff['esperado'], ensure_ascii=False)
                data_actual = json.dumps(diff['atual'], ensure_ascii=False)


                html += f"""
                    <tr>
                        <td><code>{campo}</code></td>
                        <td><div class="diff-type {tipo_classe}">{tipo_texto}</div></td>
                        <td>{esperado_fmt}</td>
                        <td>{atual_fmt}</td>
                        <td>
                            <button class="copy-btn" 
                                    data-path="{data_path}" 
                                    data-type="{data_type}" 
                                    data-expected='{data_expected}' 
                                    data-actual='{data_actual}'
                                    onclick="copyEvidence(this)">📋 Copiar</button>
                        </td>
                    </tr>
                """
            
            html += "</tbody></table></div>"
        
        html += "</div>" # Fecha content-box dos detalhes

    html += """
            <footer>
                <p>Gerado por JsonMirror v1.0.0 | © 2025 ASA. Todos os direitos reservados.</p>
            </footer>
        </div>
    </body>
    </html>
    """
    return html

def main():
    """Função principal para executar a comparação."""
    fixtures_path = Path(__file__).parent / "fixtures"
    print(f"🔎 Analisando diretórios em: {fixtures_path}\n")

    # Itera sobre cada subdiretório dentro de 'fixtures'
    for sub_dir in fixtures_path.iterdir():
        if not sub_dir.is_dir():
            continue

        print(f"--- Processando: {sub_dir.name} ---")

        # Encontra os arquivos JSON no subdiretório
        json_files = list(sub_dir.glob("*.json"))
        if len(json_files) != 2:
            print(f"⚠️  Aviso: Esperado 2 arquivos JSON em '{sub_dir.name}', mas foram encontrados {len(json_files)}. Pulando este diretório.\n")
            continue

        # Identifica o arquivo de referência (esperado) e o atual
        caminho_esperado = next((f for f in json_files if "GABARITO" in f.name.upper()), None)
        caminho_atual = next((f for f in json_files if "GABARITO" not in f.name.upper()), None)

        if not caminho_esperado or not caminho_atual:
            print(f"❌ Erro: Não foi possível identificar os arquivos de referência e atual em '{sub_dir.name}'. Verifique a convenção de nomes.\n")
            continue

        # Carrega os arquivos
        json_esperado = carregar_json(caminho_esperado)
        json_atual = carregar_json(caminho_atual)

        if json_esperado is None or json_atual is None:
            print(f"❌ Erro ao carregar JSONs em '{sub_dir.name}'. Pulando.\n")
            continue

        # Extrai a declaração para alinhar a comparação por seções
        dados_esperado = extrair_dados_relevantes(json_esperado)
        dados_atual = extrair_dados_relevantes(json_atual)
        
        # Normaliza a estrutura para garantir que ambos estejam no formato plano (seções na raiz)
        dados_esperado = normalizar_estrutura_declaracao(dados_esperado)
        dados_atual = normalizar_estrutura_declaracao(dados_atual)

        diferencas_totais = []
        secoes_lista = []

        # Garante que a comparação seja feita em um dicionário
        if not isinstance(dados_esperado, dict) or not isinstance(dados_atual, dict):
            print(f"⚠️  Aviso: A estrutura extraída não é um dicionário. Realizando comparação direta.")
            comparar_objetos(dados_esperado, dados_atual, "Declaração", diferencas_totais)
            secoes_lista = ["Estrutura Geral"]
        else:
            # Lógica explícita para comparar seção por seção, garantindo que não haja "mistura" de dados entre seções.
            secoes_esperadas = dados_esperado.keys()
            secoes_atuais = dados_atual.keys()
            
            secoes_extras = [k for k in secoes_atuais if k not in secoes_esperadas]

            # 1. Itera sobre as seções na ordem do arquivo de referência (Gabarito)
            for secao in secoes_esperadas:
                caminho_secao = f"Declaração.{secao}"
                if secao in secoes_atuais:
                    # Seção comum: chama a comparação recursiva para validar o conteúdo interno.
                    comparar_objetos(dados_esperado[secao], dados_atual[secao], caminho_secao, diferencas_totais)
                else:
                    # Seção ausente: reporta que a seção inteira está faltando no JSON atual.
                    diferencas_totais.append({
                        "caminho": caminho_secao, "tipo": "Chave Ausente no JSON Atual",
                        "esperado": dados_esperado[secao], "atual": "N/A (Seção inteira ausente)"
                    })
            
            # 2. Adiciona seções que existem no JSON atual mas não no de referência.
            for secao in sorted(secoes_extras):
                diferencas_totais.append({
                    "caminho": f"Declaração.{secao}", "tipo": "Chave Extra no JSON Atual",
                    "esperado": "N/A (Seção inteira extra)", "atual": dados_atual[secao]
                })
            
            # Cria lista base de seções
            secoes_lista = sorted(list(set(secoes_esperadas) | set(secoes_atuais)))

            # --- Lógica para destacar subseções importantes (como contact_and_address) ---
            subsecoes_destaque = ['contact_and_address']
            secoes_expandidas = []
            
            for secao in secoes_lista:
                secoes_expandidas.append(secao)
                # Verifica se há subseções de destaque dentro desta seção
                obj_esp = dados_esperado.get(secao) if isinstance(dados_esperado, dict) else None
                obj_atl = dados_atual.get(secao) if isinstance(dados_atual, dict) else None
                
                for sub in subsecoes_destaque:
                    if (isinstance(obj_esp, dict) and sub in obj_esp) or \
                       (isinstance(obj_atl, dict) and sub in obj_atl):
                        secoes_expandidas.append(f"{secao}.{sub}")
            
            secoes_lista = secoes_expandidas

        # Gera e salva o relatório dentro do subdiretório
        relatorio_html = gerar_relatorio_html(diferencas_totais, str(caminho_esperado), str(caminho_atual), secoes_lista)
        caminho_relatorio = sub_dir / "relatorio_comparacao.html"
        with open(caminho_relatorio, 'w', encoding='utf-8') as f:
            f.write(relatorio_html)

        print(f"✅ Comparação concluída. {len(diferencas_totais)} diferença(s) encontrada(s).")
        print(f"   Relatório salvo em: '{caminho_relatorio}'\n")

if __name__ == "__main__":
    main()
