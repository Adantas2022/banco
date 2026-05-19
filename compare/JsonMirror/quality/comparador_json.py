import json
import difflib
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def normalizar_texto_semantico(texto: str) -> str:
    """
    Normaliza texto para comparação semântica, ignorando:
    - Acentuação (é -> e, ç -> c, etc.)
    - Diferenças de espaçamento (múltiplos espaços, tabs, etc.)
    - Pontuação (vírgulas, pontos, hífens, etc.)
    - Case (maiúsculas/minúsculas)
    
    Usado para determinar se dois textos são semanticamente equivalentes.
    
    Exemplos:
    - "EMPREGADOR - TITULAR" -> "empregador titular"
    - "EMPREGADOR-TITULAR" -> "empregador titular"  (ambos ficam iguais)
    """
    if not isinstance(texto, str):
        return str(texto) if texto is not None else ""
    
    # 1. Remove acentos (NFD decompõe, então removemos os combining characters)
    texto_sem_acento = unicodedata.normalize('NFD', texto)
    texto_sem_acento = ''.join(c for c in texto_sem_acento if unicodedata.category(c) != 'Mn')
    
    # 2. Converte para minúsculas
    texto_lower = texto_sem_acento.lower()
    
    # 3. SUBSTITUI pontuação por espaço (não remove, para não juntar palavras)
    # Assim "EMPREGADOR-TITULAR" vira "empregador titular" (não "empregadortitular")
    texto_sem_pontuacao = re.sub(r'[^\w\s]', ' ', texto_lower)
    
    # 4. Normaliza espaços (múltiplos espaços -> um espaço, trim)
    texto_normalizado = ' '.join(texto_sem_pontuacao.split())
    
    return texto_normalizado


def textos_semanticamente_iguais(texto1, texto2) -> bool:
    """
    Verifica se dois textos são semanticamente equivalentes,
    ignorando acentuação, espaçamento e pontuação.
    """
    return normalizar_texto_semantico(texto1) == normalizar_texto_semantico(texto2)


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


def normalizar_valor(valor, chave=None):
    """Normaliza valores para comparação (strings, números, telefones)."""
    if isinstance(valor, str):
        valor = valor.strip()

        # Normalização específica para campos numéricos formatados (CPF, CNPJ, Telefone, CEP)
        if chave and any(k in chave.lower() for k in ['phone', 'cep', 'zip', 'cpf', 'cnpj']):
             # Remove tudo que não é dígito
             digits = "".join(filter(str.isdigit, valor))
             if digits: # Se sobrou algo, retorna apenas os dígitos
                 return digits
        elif chave and any(k in chave.lower() for k in ['rate', 'aliquota', 'percentage']):
             valor = valor.replace('%', '').strip()
             
        # Remove espaços repetidos e espaços nas pontas, converte para minúsculo
        return " ".join(valor.split()).lower()
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
    total_validos = 0  # Denominador dinâmico (apenas campos não-nulos em pelo menos um lado)

    # Chaves que geralmente são geradas e não servem para matching de conteúdo
    chaves_ignoradas = {'id', '_id', 'uuid', 'pk', 'page', 'created_at', 'updated_at'}
    
    chaves_relevantes = [k for k in todas_chaves if k not in chaves_ignoradas]
    if not chaves_relevantes: return 0.0 

    for chave in chaves_relevantes:
        val1 = item1.get(chave)
        val2 = item2.get(chave)

        # Normaliza vazio para None para facilitar verificação
        # CORREÇÃO: Zero (0) é um valor válido em finanças, não deve ser tratado como None.
        if val1 in ["", [], {}]: val1 = None
        if val2 in ["", [], {}]: val2 = None

        # REGRA DE NEGÓCIO: Ignora campo se ambos forem nulos/vazios
        if val1 is None and val2 is None:
            continue
        
        total_validos += 1
        
        # Comparação relaxada para strings e números
        if val1 == val2:
            matches += 1
        elif val1 is None or val2 is None:
            pass # Um é valor e o outro é None, não é match
        elif str(val1) == str(val2): # Comparação direta de string
            matches += 1
        # NOVA: Comparação semântica (ignora acentuação, espaçamento, pontuação)
        elif textos_semanticamente_iguais(str(val1), str(val2)):
            matches += 1
        elif isinstance(val1, str) and isinstance(val2, str):
            if normalizar_valor(val1, chave) == normalizar_valor(val2, chave):
                matches += 1
            else:
                # Fuzzy match para strings (OCR pode ter pequenos erros)
                if difflib.SequenceMatcher(None, normalizar_valor(val1, chave), normalizar_valor(val2, chave)).ratio() > 0.8:
                    matches += 1
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                if abs(val1 - val2) < 0.01:
                    matches += 1
        # Tenta converter string numérica para float
        elif str(val1).replace(',','.').replace(' ','') == str(val2).replace(',','.').replace(' ',''):
                matches += 1

    if total_validos == 0:
        return 0.0

    return matches / total_validos


def parear_listas(lista_esperada, lista_atual):
    """
    Parea itens de duas listas baseado em similaridade de conteúdo.
    Retorna: (pares_correspondentes, itens_ausentes, itens_extras)
    
    Estratégias (em ordem de prioridade):
    1. Pareamento por ID (se IDs coincidem)
    2. Pareamento por índice (se listas têm mesmo tamanho - RÁPIDO)
    3. Pareamento por código + descrição (para itens com 'code')
    4. Fallback: similaridade O(n²) - apenas para listas pequenas
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
                item_atl = mapa_atual[id_val]
                score = calcular_similaridade(item_exp, item_atl)
                pares.append((item_exp, item_atl, score))
        
        return pares, ausentes, extras

    # 2. OTIMIZAÇÃO: Se listas têm mesmo tamanho, pareia por índice (muito mais rápido)
    if len(lista_esperada) == len(lista_atual):
        pares = []
        for i in range(len(lista_esperada)):
            exp = lista_esperada[i]
            atl = lista_atual[i]
            score = calcular_similaridade(exp, atl) if isinstance(exp, dict) and isinstance(atl, dict) else (1.0 if exp == atl else 0.0)
            pares.append((exp, atl, score))
        return pares, [], []  # Sem ausentes ou extras quando pareado por índice

    # 3. OTIMIZAÇÃO: Pareamento por código (para itens com campo 'code')
    tem_code_exp = all(isinstance(item, dict) and 'code' in item for item in lista_esperada[:10]) if lista_esperada else False
    tem_code_atl = all(isinstance(item, dict) and 'code' in item for item in lista_atual[:10]) if lista_atual else False
    
    if tem_code_exp and tem_code_atl and len(lista_esperada) > 50:
        # Agrupa por código para reduzir espaço de busca
        from collections import defaultdict
        grupos_exp = defaultdict(list)
        grupos_atl = defaultdict(list)
        
        for i, item in enumerate(lista_esperada):
            grupos_exp[item.get('code')].append((i, item))
        for j, item in enumerate(lista_atual):
            grupos_atl[item.get('code')].append((j, item))
        
        usados_exp = set()
        usados_atl = set()
        pares = []
        
        # Pareia dentro de cada grupo de código
        for code in grupos_exp:
            if code not in grupos_atl:
                continue
            
            items_exp = grupos_exp[code]
            items_atl = grupos_atl[code]
            
            # Pareamento simples por ordem dentro do grupo
            for idx, (i, exp) in enumerate(items_exp):
                if idx < len(items_atl):
                    j, atl = items_atl[idx]
                    if i not in usados_exp and j not in usados_atl:
                        score = calcular_similaridade(exp, atl)
                        pares.append((exp, atl, score))
                        usados_exp.add(i)
                        usados_atl.add(j)
        
        ausentes = [lista_esperada[i] for i in range(len(lista_esperada)) if i not in usados_exp]
        extras = [lista_atual[j] for j in range(len(lista_atual)) if j not in usados_atl]
        
        return pares, ausentes, extras

    # 4. Fallback: Pareamento por similaridade O(n²) - apenas para listas pequenas
    if len(lista_esperada) * len(lista_atual) > 10000:
        # Para listas muito grandes, usa pareamento por índice parcial
        pares = []
        min_len = min(len(lista_esperada), len(lista_atual))
        for i in range(min_len):
            exp = lista_esperada[i]
            atl = lista_atual[i]
            score = calcular_similaridade(exp, atl) if isinstance(exp, dict) and isinstance(atl, dict) else (1.0 if exp == atl else 0.0)
            pares.append((exp, atl, score))
        
        ausentes = lista_esperada[min_len:]
        extras = lista_atual[min_len:]
        return pares, ausentes, extras
    
    nao_pareados_exp = list(enumerate(lista_esperada))
    nao_pareados_atl = list(enumerate(lista_atual))
    candidatos = []
    
    for i, exp in nao_pareados_exp:
        for j, atl in nao_pareados_atl:
            score = calcular_similaridade(exp, atl)
            if score > 0.4: # Limiar reduzido para capturar mais pares com erros de OCR
                candidatos.append((score, i, j))
    
    # Ordena pelos pares mais similares primeiro
    candidatos.sort(key=lambda x: x[0], reverse=True)
    
    usados_exp = set()
    usados_atl = set()
    pares = []
    
    for score, i, j in candidatos:
        if i not in usados_exp and j not in usados_atl:
            pares.append((lista_esperada[i], lista_atual[j], score))
            usados_exp.add(i)
            usados_atl.add(j)
            
    ausentes = [lista_esperada[i] for i, _ in nao_pareados_exp if i not in usados_exp]
    extras = [lista_atual[j] for j, _ in nao_pareados_atl if j not in usados_atl]
    
    return pares, ausentes, extras


def comparar_objetos(obj1, obj2, caminho_atual, diferencas, metricas=None, igualdades=None):
    """Compara recursivamente dois objetos Python (dicionários, listas, etc.)."""
    if metricas is None:
        metricas = {'matches': 0}
    
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
                # Se o valor no obj1 é null/None, considerar equivalente a não existir
                if obj1[chave] is None:
                    continue  # Ambos são efetivamente "sem valor"
                diferencas.append({
                    "caminho": novo_caminho,
                    "tipo": "Chave Ausente no JSON Atual",
                    "esperado": obj1[chave],
                    "atual": "N/A",
                    "similarity": 0.0
                })
            elif chave not in obj1:
                # Se o valor no obj2 é null/None, considerar equivalente a não existir
                if obj2[chave] is None:
                    continue  # Ambos são efetivamente "sem valor"
                diferencas.append({
                    "caminho": novo_caminho,
                    "tipo": "Chave Extra no JSON Atual",
                    "esperado": "N/A",
                    "atual": obj2[chave],
                    "similarity": 0.0
                })
            else:
                comparar_objetos(obj1[chave], obj2[chave], novo_caminho, diferencas, metricas, igualdades)

    # Compara listas
    elif isinstance(obj1, list) and isinstance(obj2, list):
        pares, ausentes, extras = parear_listas(obj1, obj2)
        
        # Compara os pares encontrados
        for i, (item_exp, item_atl, score) in enumerate(pares):
            # Tenta criar um label legível para o caminho
            label = f"item_{i}"
            if isinstance(item_exp, dict):
                # Usa campos identificadores se existirem
                label = item_exp.get('code') or item_exp.get('name') or item_exp.get('description') or label
                label = str(label)[:30] # Limita tamanho
                # Remove caracteres inválidos para caminho
                label = re.sub(r'[^a-zA-Z0-9_-]', '_', label)
            
            comparar_objetos(item_exp, item_atl, f"{caminho_atual}[{label}]", diferencas, metricas, igualdades)
            
        for item in ausentes:
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Item de Lista Ausente",
                "esperado": item,
                "atual": "N/A",
                "similarity": 0.0
            })
            
        for item in extras:
            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Item de Lista Extra",
                "esperado": "N/A",
                "atual": item,
                "similarity": 0.0
            })

    # Compara valores
    else:
        campo_atual_nome = caminho_atual.split('.')[-1]
        # Normalização para comparação
        val1 = normalizar_valor(obj1, campo_atual_nome)
        val2 = normalizar_valor(obj2, campo_atual_nome)
        
        # Ignora ID se for diferente (geralmente UUID vs Hash)
        if caminho_atual.endswith('.id') or caminho_atual.endswith('._id'):
            return

        # Validação de Tipo (Bug Crítico)
        # Se um é número e o outro é string que não parece número
        if isinstance(obj1, (int, float)) and isinstance(obj2, str) and not re.match(r'^[\d\.,\s%\-]+$', obj2):
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
                    metricas['matches'] += 1
                    return # São iguais numericamente
            except ValueError:
                pass # Falha na conversão, segue para comparação padrão

        if val1 != val2:
            # Calcula similaridade para valores divergentes (ignora nulos na comparação textual)
            sim_score = 0.0
            s1 = str(val1) if val1 is not None else ""
            s2 = str(val2) if val2 is not None else ""
            
            # OTIMIZAÇÃO: Se a representação textual for idêntica, ignora (falso positivo de tipo int vs str)
            if s1 == s2:
                metricas['matches'] += 1
                return
            
            # NOVA OTIMIZAÇÃO: Se os textos são semanticamente iguais (ignorando acentuação, espaçamento e pontuação)
            if textos_semanticamente_iguais(s1, s2):
                metricas['matches'] += 1
                return

            if s1 and s2:
                sim_score = difflib.SequenceMatcher(None, s1, s2).ratio()
                # Se a similaridade for 100% (ou muito próxima), considera como igual e não reporta
                if sim_score > 0.995:
                    metricas['matches'] += 1
                    return

            diferencas.append({
                "caminho": caminho_atual,
                "tipo": "Valor Divergente",
                "esperado": obj1,
                "atual": obj2,
                "similarity": sim_score
            })
        else:
            metricas['matches'] += 1
            if igualdades is not None:
                igualdades.append({'caminho': caminho_atual, 'valor': obj1})

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


def gerar_relatorio_html(diferencas, arquivo_esperado, arquivo_atual, secoes_analisadas=None, dados_esperado=None, dados_atual=None, metricas=None, igualdades=None):
    """Gera um relatório de diferenças em formato HTML."""
    from collections import defaultdict
    from os.path import basename

    nome_arquivo_esperado = basename(arquivo_esperado)
    nome_arquivo_atual = basename(arquivo_atual)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def traduzir_campo(texto):
        """Formata uma chave ou caminho de chaves para exibição."""
        if not isinstance(texto, str):
            return str(texto)
        return texto.replace('.', ' > ')

    # Scripts e Estilos (Tailwind + Custom)
    head_content = """
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        gray: { 900: '#1a202c', 800: '#2d3748', 700: '#4a5568' }
                    }
                }
            }
        }
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; }
        ::-webkit-scrollbar-thumb { background: #c1c1c1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #a8a8a8; }
        .dark ::-webkit-scrollbar-track { background: #2d3748; }
        .dark ::-webkit-scrollbar-thumb { background: #4a5568; }
        
        /* Diff Highlighting */
        .diff-add { background-color: #dcfce7; color: #166534; text-decoration: none; padding: 0 2px; border-radius: 2px; }
        .diff-del { background-color: #fee2e2; color: #991b1b; text-decoration: line-through; opacity: 0.8; padding: 0 2px; border-radius: 2px; }
        .dark .diff-add { background-color: #064e3b; color: #86efac; }
        .dark .diff-del { background-color: #7f1d1d; color: #fca5a5; }

        /* Transitions */
        body { transition: background-color 0.3s, color 0.3s; }
        
        /* Tree View Lines */
        .tree-line { position: absolute; left: 14px; top: 0; bottom: 0; width: 1px; background-color: #e2e8f0; }
        .dark .tree-line { background-color: #4a5568; }
    </style>
    <script>
        // Dark Mode Logic
        function toggleDarkMode() {
            document.documentElement.classList.toggle('dark');
            localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
        }
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        // Toggle Accordion
        function toggleGroup(element) {
            const content = element.nextElementSibling;
            const icon = element.querySelector('.toggle-icon');
            if (content.classList.contains('hidden')) {
                content.classList.remove('hidden');
                icon.classList.add('rotate-90');
            } else {
                content.classList.add('hidden');
                icon.classList.remove('rotate-90');
            }
        }

        // Expand/Collapse All
        function toggleAll(expand) {
            document.querySelectorAll('.group-content').forEach(el => {
                if (expand) {
                    el.classList.remove('hidden');
                    el.previousElementSibling.querySelector('.toggle-icon').classList.add('rotate-90');
                } else {
                    el.classList.add('hidden');
                    el.previousElementSibling.querySelector('.toggle-icon').classList.remove('rotate-90');
                }
            });
        }

        // Copy to Clipboard
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

        // Tree View Toggle
        function toggleTree(element, event) {
            const li = element.closest('li');
            const ul = li.querySelector('ul');
            const icon = element.querySelector('i');
            if (ul) {
                if (ul.classList.contains('hidden')) {
                    ul.classList.remove('hidden');
                    icon.classList.remove('fa-chevron-right');
                    icon.classList.add('fa-chevron-down');
                } else {
                    ul.classList.add('hidden');
                    icon.classList.remove('fa-chevron-down');
                    icon.classList.add('fa-chevron-right');
                }
            }
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
        }
        
        // Modal Logic
        function openModal(id) {
            document.getElementById(id).classList.remove('hidden');
            document.body.style.overflow = "hidden";
        }
        function closeModal(id) {
            document.getElementById(id).classList.add('hidden');
            document.body.style.overflow = "auto";
        }
        window.onclick = function(event) {
            if (event.target.classList.contains('modal-overlay')) {
                event.target.classList.add('hidden');
                document.body.style.overflow = "auto";
            }
        }

        // Search & Filter Logic
        function filterTable(criteria) {
            const rows = document.querySelectorAll('.diff-row');
            const searchVal = document.getElementById('searchInput').value.toLowerCase();

            rows.forEach(row => {
                const type = row.dataset.type;
                const sim = parseFloat(row.dataset.similarity);
                const text = row.innerText.toLowerCase();
                let show = true;

                // Filter Buttons
                if (criteria === 'critical' && !(type.includes('BUG') || type.includes('Ausente'))) show = false;
                if (criteria === 'low_sim' && sim >= 50) show = false;

                // Search Input
                if (searchVal && !text.includes(searchVal)) show = false;

                // Apply visibility
                if (show) row.classList.remove('hidden');
                else row.classList.add('hidden');
            });

            // Hide empty groups
            document.querySelectorAll('.group-container').forEach(group => {
                const visibleRows = group.querySelectorAll('.diff-row:not(.hidden)').length;
                if (visibleRows === 0) group.classList.add('hidden');
                else group.classList.remove('hidden');
            });
        }

        function searchTable() {
            // Re-apply current active filter logic if needed, or just default to 'all' logic combined with search
            // For simplicity, we trigger the 'all' filter which includes search check
            filterTable('all'); 
        }

        // Back to Top Logic
        window.onscroll = function() {
            const btn = document.getElementById('backToTop');
            if (btn) {
                if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
                    btn.classList.remove('hidden');
                } else {
                    btn.classList.add('hidden');
                }
            }
        };

        function scrollToTop() {
            window.scrollTo({top: 0, behavior: 'smooth'});
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
        <title>Relatório de Similaridade - JsonMirror</title>
        {head_content}
    </head>
    <body class="bg-gray-50 text-gray-800 dark:bg-gray-900 dark:text-gray-200 transition-colors duration-300">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            
            <!-- Header -->
            <div class="flex justify-between items-center mb-8 border-b border-gray-200 dark:border-gray-700 pb-4">
                <div>
                    <h1 class="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">JsonMirror <span class="text-blue-600 text-lg font-normal">v1.0</span></h1>
                    <p class="text-gray-500 dark:text-gray-400 mt-1">Relatório de Comparação e Similaridade</p>
                </div>
                <button onclick="toggleDarkMode()" class="p-2 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-yellow-400 hover:bg-gray-300 dark:hover:bg-gray-600 transition">
                    <i class="fas fa-moon dark:hidden"></i>
                    <i class="fas fa-sun hidden dark:inline"></i>
                </button>
            </div>
            
            <!-- Summary Card -->
            <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-6 mb-8 border border-gray-100 dark:border-gray-700">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="flex items-start space-x-3">
                        <div class="flex-shrink-0"><i class="fas fa-file-contract text-blue-500 text-xl mt-1"></i></div>
                        <div class="overflow-hidden">
                            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Arquivo Esperado (Gabarito)</p>
                            <p class="text-sm font-mono font-bold text-gray-900 dark:text-white truncate" title="{arquivo_esperado}">{nome_arquivo_esperado}</p>
                        </div>
                    </div>
                    <div class="flex items-start space-x-3">
                        <div class="flex-shrink-0"><i class="fas fa-file-code text-purple-500 text-xl mt-1"></i></div>
                        <div class="overflow-hidden">
                            <p class="text-sm font-medium text-gray-500 dark:text-gray-400">Arquivo Atual (Extraído)</p>
                            <p class="text-sm font-mono font-bold text-gray-900 dark:text-white truncate" title="{arquivo_atual}">{nome_arquivo_atual}</p>
                        </div>
                    </div>
                </div>
                <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-400 flex justify-between">
                    <span><i class="far fa-clock mr-1"></i> Gerado em: {timestamp}</span>
                </div>
            </div>
    """
    
    if not diferencas:
        html += """
        <div class="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg p-8 text-center">
            <i class="fas fa-check-circle text-green-500 text-5xl mb-4"></i>
            <h2 class="text-2xl font-bold text-green-700 dark:text-green-400">Perfeito!</h2>
            <p class="text-green-600 dark:text-green-300 mt-2">Nenhuma diferença encontrada entre os arquivos.</p>
        </div>
        """
    else:
        # Calcula as estatísticas
        stats = {
            "missing": 0,
            "extra": 0,
            "divergent": 0,
            "bug": 0
        }
        sim_values = []

        for diff in diferencas:
            if "Ausente" in diff['tipo']:
                stats["missing"] += 1
            elif "Extra" in diff['tipo']:
                stats["extra"] += 1
            elif "BUG" in diff['tipo']:
                stats["bug"] += 1
            else:
                stats["divergent"] += 1
                # Coleta similaridade apenas de valores divergentes para a média
                if diff['tipo'] == "Valor Divergente" and 'similarity' in diff:
                    sim_values.append(diff['similarity'])

        # Cálculo da Similaridade Global Ponderada
        # Fórmula: (Matches * 1.0 + Soma(Similaridade Divergentes)) / Total de Itens
        matches_count = metricas['matches'] if metricas else 0
        total_items = matches_count + stats['missing'] + stats['extra'] + stats['divergent'] + stats['bug']
        
        weighted_sum = matches_count * 1.0
        weighted_sum += sum(sim_values) # Soma as similaridades parciais dos divergentes
        
        avg_sim = weighted_sum / total_items if total_items > 0 else 1.0
        
        # Cores para a média geral
        if avg_sim > 0.90:
            avg_color = "text-green-600 dark:text-green-400"
            avg_bg = "bg-green-100 dark:bg-green-900/30"
            avg_icon = "fa-smile"
        elif avg_sim > 0.70:
            avg_color = "text-yellow-600 dark:text-yellow-400"
            avg_bg = "bg-yellow-100 dark:bg-yellow-900/30"
            avg_icon = "fa-meh"
        else:
            avg_color = "text-red-600 dark:text-red-400"
            avg_bg = "bg-red-100 dark:bg-red-900/30"
            avg_icon = "fa-frown"

        # Helper para criar cards de KPI
        def kpi_card(title, value, icon, color_class):
            return f"""
            <div class="bg-white dark:bg-gray-800 overflow-hidden shadow-sm rounded-lg border border-gray-100 dark:border-gray-700">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <i class="fas {icon} {color_class} text-2xl"></i>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <dl>
                                <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">{title}</dt>
                                <dd class="text-2xl font-bold text-gray-900 dark:text-white">{value}</dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
            """

        html += f"""
            <div class="mb-8">
                <h2 class="text-xl font-bold text-gray-800 dark:text-white mb-4 flex items-center"><i class="fas fa-chart-pie mr-2 text-blue-500"></i> Resumo da Análise</h2>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                    {kpi_card("Ausentes", stats['missing'], "fa-minus-circle", "text-red-500")}
                    {kpi_card("Extras", stats['extra'], "fa-plus-circle", "text-green-500")}
                    {kpi_card("Divergentes", stats['divergent'], "fa-exchange-alt", "text-yellow-500")}
                    {kpi_card("Bugs Potenciais", stats['bug'], "fa-bug", "text-purple-500")}
                    
                    <div class="{avg_bg} overflow-hidden shadow-sm rounded-lg border border-transparent">
                        <div class="p-5">
                            <div class="flex items-center">
                                <div class="flex-shrink-0">
                                    <i class="fas {avg_icon} {avg_color} text-2xl"></i>
                                </div>
                                <div class="ml-5 w-0 flex-1">
                                    <dl>
                                        <dt class="text-sm font-medium {avg_color} opacity-80 truncate">Similaridade Global</dt>
                                        <dd class="text-2xl font-bold {avg_color}">{avg_sim*100:.1f}%</dd>
                                    </dl>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        """

        # Seção de Igualdades (Nova)
        if igualdades:
            html += f"""
            <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-6 mb-8 border border-gray-100 dark:border-gray-700">
                <div class="flex justify-between items-center cursor-pointer" onclick="toggleGroup(this)">
                     <h3 class="text-lg font-bold text-gray-800 dark:text-white flex items-center">
                        <i class="fas fa-check-double mr-2 text-green-500"></i> Detalhes de Igualdades (100%)
                     </h3>
                     <div class="flex items-center gap-2">
                         <span class="text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 px-2 py-1 rounded-full">{len(igualdades)} itens</span>
                         <i class="fas fa-chevron-right toggle-icon text-gray-400 text-sm transition-transform duration-200"></i>
                     </div>
                </div>
                <div class="group-content hidden mt-4">
                    <div class="overflow-x-auto max-h-96 overflow-y-auto">
                        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-900 sticky top-0">
                                <tr>
                                    <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-1/3">Campo</th>
                                    <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Valor</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            """
            
            igualdades_sorted = sorted(igualdades, key=lambda x: x['caminho'])
            
            for item in igualdades_sorted:
                caminho_limpo = item['caminho'].replace('Declaração.', '')
                campo_traduzido = traduzir_campo(caminho_limpo)
                valor_json = json.dumps(item['valor'], ensure_ascii=False)
                valor_fmt = f'<code class="text-sm font-mono bg-gray-50 dark:bg-gray-900 px-1 py-0.5 rounded text-gray-800 dark:text-gray-200 break-all">{valor_json}</code>'
                
                html += f"""
                                <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition">
                                    <td class="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 font-medium break-words">{campo_traduzido}</td>
                                    <td class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">{valor_fmt}</td>
                                </tr>
                """
            
            html += """
                            </tbody>
                        </table>
                    </div>
                </div>
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
            
            modals_html = []

            def get_value_by_path(data, path):
                if data is None: return None
                if path == "Estrutura Geral": return data
                keys = path.split('.')
                val = data
                for k in keys:
                    if isinstance(val, dict) and k in val:
                        val = val[k]
                    else:
                        return None
                return val

            # 2. Função recursiva para gerar o HTML da lista aninhada
            def build_section_html(tree, path_prefix=''):
                # Não renderiza um <ul> vazio se não houver filhos
                if not tree:
                    return ''
                
                html_list = '<ul>'
                for key, value in tree.items():
                    current_path = f"{path_prefix}.{key}" if path_prefix else key
                    nome_exibicao = key
                    
                    # Recupera valores para verificar se está vazio
                    val_exp = get_value_by_path(dados_esperado, current_path)
                    val_act = get_value_by_path(dados_atual, current_path)
                    
                    is_empty = False
                    if val_exp is None or (isinstance(val_exp, (dict, list, str)) and len(val_exp) == 0):
                        is_empty = True

                    # Conta diferenças que começam com o caminho desta seção
                    # CORREÇÃO: Garante que o match é exato ou seguido de ponto/colchete para evitar falsos positivos em prefixos
                    prefixo_busca = f"Declaração.{current_path}"
                    diffs_count = sum(1 for d in diferencas if d['caminho'] == prefixo_busca or d['caminho'].startswith(f"{prefixo_busca}.") or d['caminho'].startswith(f"{prefixo_busca}["))
                    
                    if diffs_count > 0:
                        status_class = "border-l-4 border-red-500"
                        badge_class = "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                        status_text = f"{diffs_count} diferença(s)"
                    elif val_exp is not None and val_act is None:
                        status_class = "border-l-4 border-red-500"
                        badge_class = "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                        status_text = "Ausente/Nulo"
                    elif is_empty:
                        status_class = "border-l-4 border-blue-400"
                        badge_class = "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                        status_text = "Vazio"
                    else:
                        status_class = "border-l-4 border-green-500"
                        badge_class = "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                        status_text = "OK"

                    # Identifica a chave da seção pai (top-level) para o link da âncora
                    top_level_key = current_path.split('.')[0]
                    anchor_id = f"details-{top_level_key}"

                    has_children = bool(value['children'])
                    toggle_icon = '<i class="fas fa-chevron-down text-xs"></i>' if has_children else ''
                    toggle_class = 'cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 rounded w-6 h-6 flex items-center justify-center mr-2' if has_children else 'w-6 mr-2'
                    onclick_attr = 'onclick="toggleTree(this, event)"' if has_children else ''
                    
                    # Prepare Modal
                    
                    modal_id = f"modal-{current_path.replace('.', '-').replace(' ', '_')}"
                    
                    # Only show button if there is data to show
                    btn_html = ""
                    if val_exp is not None or val_act is not None:
                        btn_html = f'<button class="text-gray-400 hover:text-blue-500 transition mr-3" onclick="openModal(\'{modal_id}\'); event.preventDefault(); event.stopPropagation();" title="Inspecionar JSON"><i class="far fa-eye"></i></button>'
                        
                        json_exp_str = json.dumps(val_exp, indent=2, ensure_ascii=False) if val_exp is not None else "null"
                        json_act_str = json.dumps(val_act, indent=2, ensure_ascii=False) if val_act is not None else "null"
                        
                        modal_html = f"""
                        <div id="{modal_id}" class="modal-overlay hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
                          <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] flex flex-col">
                            <div class="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
                                <div>
                                    <h3 class="text-lg font-bold text-gray-900 dark:text-white">Inspeção: {nome_exibicao}</h3>
                                    <p class="text-xs text-gray-500 font-mono mt-1">{current_path}</p>
                                </div>
                                <button onclick="closeModal('{modal_id}')" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-2xl">&times;</button>
                            </div>
                            <div class="flex-1 overflow-auto p-4">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
                                    <div class="bg-gray-50 dark:bg-gray-900 p-4 rounded border border-gray-200 dark:border-gray-700 overflow-auto">
                                        <h4 class="font-bold text-gray-700 dark:text-gray-300 mb-2 sticky top-0 bg-gray-50 dark:bg-gray-900 pb-2 border-b">📄 Esperado</h4>
                                        <pre class="text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{json_exp_str}</pre>
                                    </div>
                                    <div class="bg-gray-50 dark:bg-gray-900 p-4 rounded border border-gray-200 dark:border-gray-700 overflow-auto">
                                        <h4 class="font-bold text-gray-700 dark:text-gray-300 mb-2 sticky top-0 bg-gray-50 dark:bg-gray-900 pb-2 border-b">📑 Atual</h4>
                                        <pre class="text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{json_act_str}</pre>
                                    </div>
                                </div>
                            </div>
                          </div>
                        </div>
                        """
                        modals_html.append(modal_html)

                    header_html = f"""
                    <div class="flex items-center justify-between p-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded mb-1 hover:bg-gray-50 dark:hover:bg-gray-700 transition {status_class}">
                        <div class="flex items-center flex-grow">
                            <div class="{toggle_class}" {onclick_attr}>{toggle_icon}</div>
                            <span class="text-sm font-medium text-gray-700 dark:text-gray-200">{nome_exibicao}</span>
                        </div>
                        <div class="flex items-center">
                            {btn_html}
                            <span class="text-xs font-bold px-2 py-1 rounded-full {badge_class}">{status_text}</span>
                        </div>
                    </div>
                    """

                    html_list += '<li class="relative">'
                    if path_prefix: # Add indentation line for children
                         html_list += '<div class="tree-line"></div>'
                         
                    if diffs_count > 0:
                        # Script para expandir o grupo e rolar até ele
                        onclick_js = (
                            f"const container = document.getElementById('{anchor_id}'); "
                            f"if (container) {{ "
                            f"  const header = container.firstElementChild; "
                            f"  const content = header.nextElementSibling; "
                            f"  if (content && content.classList.contains('hidden')) {{ header.click(); }} "
                            f"  setTimeout(() => container.scrollIntoView({{behavior: 'smooth', block: 'start'}}), 50); "
                            f"}}"
                        )
                        html_list += f'<a href="javascript:void(0)" onclick="{onclick_js}" style="text-decoration: none; color: inherit;">{header_html}</a>'
                    else:
                        html_list += header_html
                    
                    # Chamada recursiva para os filhos (renderizados abaixo do cabeçalho)
                    if has_children:
                        html_list += f'<div class="ml-6 border-l border-gray-200 dark:border-gray-700 pl-2 hidden">{build_section_html(value["children"], current_path)}</div>'
                    
                    html_list += '</li>'
                html_list += '</ul>'
                return html_list

            html += '<div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-6 mb-8 border border-gray-100 dark:border-gray-700">'
            html += '<div class="flex justify-between items-center cursor-pointer" onclick="toggleGroup(this)">'
            html += '<h3 class="text-lg font-bold text-gray-800 dark:text-white"><i class="fas fa-sitemap mr-2 text-gray-500"></i> Estrutura e Status</h3>'
            html += '<i class="fas fa-chevron-right toggle-icon text-gray-400 text-sm transition-transform duration-200"></i>'
            html += '</div>'
            html += '<div class="group-content hidden mt-4">'
            html += build_section_html(secoes_tree)
            html += '</div></div>'

        # Define a prioridade para cada tipo de diferença
        priority_map = {
            "BUG: Tipo de Dado Inválido": (0, "Crítica", "bg-purple-600 text-white"),
            "Tipo de Dado Inválido": (0, "Crítica", "bg-purple-600 text-white"),
            "Chave Ausente no JSON Atual": (1, "Alta", "bg-red-600 text-white"),
            "Item de Lista Ausente": (1, "Alta", "bg-red-600 text-white"),
            "Valor Divergente": (2, "Média", "bg-yellow-500 text-white"),
            "Chave Extra no JSON Atual": (3, "Baixa", "bg-blue-500 text-white"),
            "Item de Lista Extra": (3, "Baixa", "bg-blue-500 text-white"),
        }

        # Agrupa as diferenças por Seção (Sessão)
        grouped_diffs = defaultdict(list)
        for diff in diferencas:
            partes = diff['caminho'].split('.')
            if len(partes) >= 2:
                secao_chave_raw = partes[1].split('[')[0]
                secao_titulo = secao_chave_raw
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

        html += '<div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg p-6 border border-gray-100 dark:border-gray-700">'
        html += """
            <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4">
                <h3 class="text-xl font-bold text-gray-800 dark:text-white"><i class="fas fa-list-ul mr-2 text-gray-500"></i> Detalhes das Diferenças</h3>
                
                <div class="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                    <div class="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
                        <button onclick="filterTable('all')" class="px-3 py-1.5 text-sm rounded-md hover:bg-white dark:hover:bg-gray-600 shadow-sm transition">Todos</button>
                        <button onclick="filterTable('critical')" class="px-3 py-1.5 text-sm rounded-md hover:bg-white dark:hover:bg-gray-600 shadow-sm transition text-red-600 dark:text-red-400">Críticos</button>
                        <button onclick="filterTable('low_sim')" class="px-3 py-1.5 text-sm rounded-md hover:bg-white dark:hover:bg-gray-600 shadow-sm transition text-yellow-600 dark:text-yellow-400">Sim. < 50%</button>
                    </div>
                    <div class="relative">
                        <input type="text" id="searchInput" onkeyup="searchTable()" placeholder="Buscar..." class="pl-9 pr-4 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white w-full">
                        <i class="fas fa-search absolute left-3 top-2.5 text-gray-400 text-xs"></i>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="toggleAll(true)" class="text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 px-3 py-2 rounded transition">Expandir</button>
                        <button onclick="toggleAll(false)" class="text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 px-3 py-2 rounded transition">Recolher</button>
                    </div>
                </div>
            </div>
        """

        for group in sorted_groups:
            parent_path = group['path']
            diffs_in_group = group['diffs']
            priority_label = group['priority_label']
            priority_class = group['priority_class']
            key_raw = group['key_raw']
            
            anchor_id = f"details-{key_raw}"

            html += f"""
                <div id="{anchor_id}" class="group-container mb-4 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    <div class="bg-gray-50 dark:bg-gray-700/50 p-3 cursor-pointer flex justify-between items-center hover:bg-gray-100 dark:hover:bg-gray-700 transition" onclick="toggleGroup(this)">
                        <div class="flex items-center gap-2">
                            <i class="fas fa-chevron-right toggle-icon text-gray-400 text-sm transition-transform duration-200"></i>
                            <span class="font-semibold text-gray-700 dark:text-gray-200">{parent_path}</span>
                            <span class="text-xs px-2 py-0.5 rounded-full {priority_class} bg-opacity-90">{priority_label}</span>
                        </div>
                        <span class="text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded border border-gray-200 dark:border-gray-600">{len(diffs_in_group)} itens</span>
                    </div>
                    <div class="group-content hidden bg-white dark:bg-gray-800">
                        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-900">
                                <tr>
                                    <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-1/3">Campo</th>
                                    <th scope="col" class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-28">Tipo</th>
                                    <th scope="col" class="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-24">Simil.</th>
                                    <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Esperado</th>
                                    <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Atual</th>
                                    <th scope="col" class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-20">Ação</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            """
            
            tipo_map = {
                "Chave Ausente no JSON Atual": ("bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200", "Ausente"),
                "Item de Lista Ausente": ("bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200", "Item Ausente"),
                "Chave Extra no JSON Atual": ("bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", "Extra"),
                "Item de Lista Extra": ("bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", "Item Extra"),
                "Valor Divergente": ("bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200", "Divergente"),
                "BUG: Tipo de Dado Inválido": ("bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200", "BUG TIPO"),
                "Tipo de Dado Inválido": ("bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200", "ERRO TIPO")
            }

            for diff in diffs_in_group:
                # Exibe o caminho relativo dentro da seção para facilitar a identificação
                partes_caminho = diff['caminho'].split('.')
                if len(partes_caminho) > 2:
                    campo_raw = ".".join(partes_caminho[2:])
                else:
                    campo_raw = partes_caminho[-1]
                
                campo = traduzir_campo(campo_raw)
                tipo_classe, tipo_texto = tipo_map.get(diff['tipo'], ('bg-gray-100 text-gray-800', diff['tipo']))
                
                # Lógica de exibição da similaridade
                similarity = diff.get('similarity', 0.0)
                sim_pct = int(similarity * 100)
                
                if sim_pct >= 90:
                    sim_color = "text-green-600 dark:text-green-400"
                    sim_bar = "bg-green-500"
                elif sim_pct >= 50:
                    sim_color = "text-yellow-600 dark:text-yellow-400"
                    sim_bar = "bg-yellow-500"
                else:
                    sim_color = "text-red-600 dark:text-red-400"
                    sim_bar = "bg-red-500"
                
                sim_html = f"""
                <div class="flex flex-col items-center justify-center">
                    <span class="text-xs font-bold {sim_color}">{sim_pct}%</span>
                    <div class="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full mt-1 overflow-hidden">
                        <div class="h-full {sim_bar}" style="width: {sim_pct}%"></div>
                    </div>
                </div>
                """
                
                # Função auxiliar para formatar os valores
                def format_value(value):
                    if isinstance(value, (dict, list)):
                        return f'<pre class="text-xs font-mono bg-gray-50 dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 overflow-x-auto max-w-xs">{json.dumps(value, indent=2, ensure_ascii=False)}</pre>'
                    return f'<code class="text-sm font-mono bg-gray-50 dark:bg-gray-900 px-1 py-0.5 rounded text-gray-800 dark:text-gray-200 break-all">{json.dumps(value, ensure_ascii=False)}</code>'

                esperado_fmt = format_value(diff['esperado'])
                
                # Se for divergência de valor, mostra diff visual
                if diff['tipo'] == "Valor Divergente" and isinstance(diff['esperado'], str) and isinstance(diff['atual'], str):
                    # Usa diff visual para destacar caracteres faltantes ou extras
                    # Compara as representações JSON (com aspas) para manter consistência visual
                    val_exp_str = json.dumps(diff['esperado'], ensure_ascii=False)
                    val_atl_str = json.dumps(diff['atual'], ensure_ascii=False)
                    diff_html = gerar_diff_html(val_exp_str, val_atl_str)
                    atual_fmt = f'<code class="text-sm font-mono bg-gray-50 dark:bg-gray-900 px-1 py-0.5 rounded text-gray-800 dark:text-gray-200 break-all">{diff_html}</code>'
                else:
                    atual_fmt = format_value(diff['atual'])

                # Prepara os dados brutos para o botão de cópia
                data_path = diff['caminho']
                data_type = diff['tipo']
                # Usa json.dumps para garantir que os dados sejam strings JSON válidas
                data_expected = json.dumps(diff['esperado'], ensure_ascii=False)
                data_actual = json.dumps(diff['atual'], ensure_ascii=False)


                html += f"""
                    <tr class="diff-row hover:bg-gray-50 dark:hover:bg-gray-700/50 transition" data-type="{diff['tipo']}" data-similarity="{sim_pct}">
                        <td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-medium break-words">{campo}</td>
                        <td class="px-4 py-3 text-center"><span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {tipo_classe}">{tipo_texto}</span></td>
                        <td class="px-4 py-3 text-center">{sim_html}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{esperado_fmt}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{atual_fmt}</td>
                        <td class="px-4 py-3 text-right">
                            <button class="text-gray-400 hover:text-blue-500 transition copy-btn" 
                                    title="Copiar Evidência"
                                    data-path="{data_path}" 
                                    data-type="{data_type}" 
                                    data-expected='{data_expected}' 
                                    data-actual='{data_actual}'
                                    onclick="copyEvidence(this)"><i class="far fa-copy"></i></button>
                        </td>
                    </tr>
                """
            
            html += "</tbody></table></div></div>"
        
        html += "</div>" # Fecha content-box dos detalhes

    # Adiciona os modais ao final do corpo
    if 'modals_html' in locals() and modals_html:
        html += "".join(modals_html)

    html += """
            <footer class="mt-12 pt-6 border-t border-gray-200 dark:border-gray-700 text-center">
                <p class="text-sm text-gray-500 dark:text-gray-400">Gerado por <span class="font-bold text-gray-700 dark:text-gray-300">JsonMirror</span> v1.0.0 | © 2025 ASA. Todos os direitos reservados.</p>
            </footer>
            
            <button id="backToTop" onclick="scrollToTop()" class="fixed bottom-8 right-8 hidden bg-blue-600 hover:bg-blue-700 text-white w-12 h-12 rounded-full shadow-lg transition-all duration-300 z-50 flex items-center justify-center" title="Voltar ao Topo">
                <i class="fas fa-arrow-up"></i>
            </button>
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
            print(f"❌ Erro crítico: Falha ao carregar arquivos JSON em '{sub_dir.name}'. Pulando diretório.\n")
            continue

        # Extrai a declaração para alinhar a comparação por seções
        dados_esperado = extrair_dados_relevantes(json_esperado)
        dados_atual = extrair_dados_relevantes(json_atual)
        
        # Normaliza a estrutura para garantir que ambos estejam no formato plano (seções na raiz)
        dados_esperado = normalizar_estrutura_declaracao(dados_esperado)
        dados_atual = normalizar_estrutura_declaracao(dados_atual)

        diferencas_totais = []
        igualdades_totais = []
        metricas_globais = {'matches': 0}
        secoes_lista = []

        # Garante que a comparação seja feita em um dicionário
        if not isinstance(dados_esperado, dict) or not isinstance(dados_atual, dict):
            print(f"⚠️  Aviso: A estrutura extraída não é um dicionário. Realizando comparação direta.")
            comparar_objetos(dados_esperado, dados_atual, "Declaração", diferencas_totais, metricas_globais, igualdades_totais)
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
                    comparar_objetos(dados_esperado[secao], dados_atual[secao], caminho_secao, diferencas_totais, metricas_globais, igualdades_totais)
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
        relatorio_html = gerar_relatorio_html(diferencas_totais, str(caminho_esperado), str(caminho_atual), secoes_lista, dados_esperado, dados_atual, metricas_globais, igualdades_totais)
        caminho_relatorio = sub_dir / "relatorio_comparacao.html"
        with open(caminho_relatorio, 'w', encoding='utf-8') as f:
            f.write(relatorio_html)

        print(f"✅ Comparação concluída. {len(diferencas_totais)} diferença(s) encontrada(s).")
        print(f"   Relatório salvo em: '{caminho_relatorio}'\n")

if __name__ == "__main__":
    main()
