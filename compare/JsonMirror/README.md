# JsonMirror 🕵️‍♂️

**JsonMirror** é uma poderosa ferramenta Python projetada para realizar uma comparação profunda entre dois arquivos JSON: um arquivo de referência (o "gabarito" ou versão "esperada") e um arquivo real que está sendo analisado. Ele gera um relatório HTML detalhado e interativo que destaca cada discrepância, tornando-o um excelente utilitário para tarefas de QA, testes e validação de dados.

O relatório agrupa as diferenças de forma inteligente, atribui prioridades e fornece visualizações claras, permitindo que desenvolvedores e testadores identifiquem e entendam rapidamente problemas que vão desde simples divergências de valores até bugs críticos estruturais ou de tipo de dados.

 
*(Nota: Substitua esta imagem por uma captura de tela real do seu relatório)*

---

## ✨ Principais Funcionalidades

- **Comparação Recursiva Profunda**: Analisa objetos e arrays aninhados para encontrar todas as diferenças.
- **Comparação Inteligente de Listas**: Compara listas de objetos por uma chave `id` comum, se presente; caso contrário, compara elemento por elemento.
- **Diferenças Categorizadas**: Identifica claramente vários tipos de discrepâncias:
    - **Chaves/Itens Faltantes**: Elementos presentes no JSON de referência, mas não no atual.
    - **Chaves/Itens Extras**: Elementos encontrados no JSON atual, mas não esperados.
    - **Valores Divergentes**: Valores diferentes para a mesma chave.
    - **Tipos de Dados Incompatíveis**: Sinaliza possíveis bugs onde o tipo de dado de um campo está incorreto (ex: esperava-se um número, mas foi encontrada uma string).
- **Agrupamento e Priorização Inteligente**:
    - Agrupa diferenças relacionadas sob seu caminho JSON comum (ex: `root.user.address`).
    - Atribui uma prioridade (Alta, Média, Baixa) a cada grupo com base na gravidade das diferenças contidas nele.
- **Relatório HTML Interativo**:
    - Interface limpa, moderna e de fácil leitura.
    - Painel de resumo com detalhes dos arquivos e estatísticas.
    - Seções expansíveis e recolhíveis para uma análise focada.
    - Botões "Expandir Todos" / "Recolher Todos" para fácil navegação.
- **Configurável**: Ignore campos facilmente nomeando-os com o prefixo `_comment`.

---

## 🚀 Como Começar

### Pré-requisitos

- Python 3.6+
- Nenhuma biblioteca externa é necessária para a funcionalidade principal.

### Estrutura de Diretórios

Para usar o JsonMirror, você precisa organizar seus arquivos JSON em uma estrutura de diretórios específica. O script processa subdiretórios dentro de uma pasta `quality/fixtures/`.

Cada subdiretório deve conter exatamente dois arquivos JSON:
1.  **O Arquivo de Referência**: Seu nome deve incluir a palavra `GABARITO` (sem diferenciar maiúsculas de minúsculas). Este é o JSON "gabarito" ou "esperado".
2.  **O Arquivo Atual**: O outro arquivo JSON no diretório, que será comparado com o de referência.

Aqui está um exemplo da estrutura:

```
JsonMirro/
├── quality/
|   ├── comparador_json.py  (Your script)
|   └── fixtures/
|       ├── test_case_1/
|       |   ├── user_profile_GABARITO.json
|       |   └── user_profile_from_api.json
|       |
|       ├── test_case_2/
|       |   ├── product_list_GABARITO.json
|       |   └── product_list_from_db.json
|       |
|       └── ... (other test cases)
|
└── README.md
```

### How to Run

1.  Navigate to the `quality` directory in your terminal.
2.  Run the Python script:

    ```bash
    python comparador_json.py
    ```

The script will automatically find the test case directories inside `fixtures/`, perform the comparisons, and generate a `relatorio_comparacao.html` file inside each test case directory.

```
🔎 Analisando diretórios em: c:\Projetos\Repo-IA-QA\JsonMirro\quality\fixtures

--- Processando: test_case_1 ---
✅ Comparação concluída. 5 diferença(s) encontrada(s).
   Relatório salvo em: 'quality\fixtures\test_case_1\relatorio_comparacao.html'

--- Processando: test_case_2 ---
✅ Comparação concluída. 0 diferença(s) encontrada(s).
   Relatório salvo em: 'quality\fixtures\test_case_2\relatorio_comparacao.html'
```

3.  Open the generated `.html` file in your web browser to view the results.

---

## 🤝 How to Contribute

Contributions are welcome! If you have ideas for improvements or want to fix a bug, feel free to:

1.  **Fork the repository.**
2.  **Create a new branch** for your feature or bugfix (`git checkout -b feature/my-new-feature`).
3.  **Make your changes** and commit them (`git commit -am 'Add some feature'`).
4.  **Push to the branch** (`git push origin feature/my-new-feature`).
5.  **Create a new Pull Request.**

---

## 📄 License

© 2025 ASA. Todos os direitos reservados.