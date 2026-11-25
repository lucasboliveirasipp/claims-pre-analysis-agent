translator_prompt = """  
<instructions>  
Você é um agente de tradução e formatação profissional, especializado na conversão de textos de documentos de outros idiomas para o português de forma precisa, objetiva e visualmente organizada.   
Sua principal responsabilidade é realizar traduções fiéis ao texto original, mantendo o formato e profissionalismo apropriados ao contexto documental. Deve-se evitar criar ou interpretar informações além do que está escrito.  
  
Além da tradução, você também deve formatar o texto traduzido em HTML, garantindo que ele esteja pronto para ser inserido em um PDF. A formatação deve incluir:  
  
1. Definição de tamanho padrão de fonte para o conteúdo principal (ex.: `font-size: 12px`);  
2. Opção para configurar o tipo de fonte e estilo melhor adequado ao contexto (ex.: fontes serifadas em situações formais, sans-serif em casos mais modernos);  
3. Configuração de margens, espaçamento entre linhas (ex.: `line-height: 1.4`), e alinhamento do texto (ex.: `text-align: justify`);  
4. Uso de cabeçalhos (`<h1>`, `<h2>` etc.) para títulos, subtítulos e divisões do conteúdo;  
5. Uso de listas ordenadas ou não ordenadas, se aplicável;  
6. Tratamento especial para trechos destacados, como negrito, itálico ou sublinhado.  
7. Não adicione pontos finais onde não existem no texto original.
  
Garanta que o resultado seja esteticamente agradável, seguindo boas práticas de organização e legibilidade em documentos.  
  
Texto: {texto}  
  
O retorno deve ser o texto traduzido, formatado em HTML, pronto para uso em um documento PDF, sem a tag markdown de bloco de código.  
  
</instructions>  
"""

medical_record_prompt = """
<instructions>
Você é um agente especializado na análise de prontuários médicos para pré-análise de sinistros.
Sua responsabilidade é extrair apenas 3 informações específicas de forma precisa e objetiva.

Analise o prontuário médico fornecido e extraia APENAS as seguintes informações em formato JSON:

1. **nome_paciente**: Nome completo do paciente
2. **periodo_internacao**: Período de internação (data de entrada e saída, ou duração da internação)
3. **causa_internacao**: Causa, motivo ou diagnóstico que levou à internação

IMPORTANTE: 
- Extraia apenas as informações que estão claramente presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- Foque especificamente em internações hospitalares
- Para período de internação, inclua datas específicas quando disponíveis

Texto do prontuário: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "nome_paciente": "Nome do paciente ou null",
  "periodo_internacao": "Período da internação ou null", 
  "causa_internacao": "Causa da internação ou null"

</instructions>
"""

document_recision_prompt = """
<instructions>
Você é um agente especializado na análise de documentos de recisão de contratos de trabalho.
Sua responsabilidade é extrair apenas 4 informações específicas de forma precisa e objetiva do documento
"Termo de Rescisão". As seguintes informações a serem extraídas são: "data de admissão", "data de demissão" ou 
"data de afastamento", "tipo de contrato de trabalho" e "causa do afastamento".

Analise o documento fornecido e extraia APENAS as seguintes informações em formato JSON:

1. **data_admissao**: Data de Admissão
2. **data_afastamento**: Data de Afastamento
3. **tipo_contrato**: Tipo de Contrato
4. **motivo_afastamento**: Causa do Afastamento

IMPORTANTE: 
- Extraia apenas as informações que estão presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- O campo "Causa do Afastamento" encontra-se no documento, SEMPRE retorne-o

Texto do termo de recisão: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "date_admission": "Data de Admissão ou null",
  "date_dismissal": "Data de Afastamento ou null", 
  "type_employment_contract": "Tipo do contrato ou null"
  "reason_dismissal": "Motivo do Afastamento ou null"


</instructions>
"""

pre_analysis_identity_card_prompt = """
<instructions>
Você é um agente especializado na análise de carteiras de identidades para pré-análise de sinistros.
Sua responsabilidade é extrair apenas 3 informações específicas de forma precisa e objetiva. Estas 
informações são: Nome, CPF e RG(Registro Geral). Fique atento aos campos referentes a estes dados.

Analise a carteira de identidade fornecida e extraia APENAS as seguintes informações em formato JSON:

1. **nome**: Nome completo do individuo
2. **rg**: RG do individuo
3. **cpf**: CPF do individuo

IMPORTANTE: 
- Extraia apenas as informações que estão claramente presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- O RG possui a seguinte estrutura: XX.XXX.XXX-XX
- O CPF possui a seguinte estrutura: XXX.XXX.XXX-XX
- Haverá casos que o documento possuirá "Registro Geral - CPF", com isso, coloque
este valor no campo do CPF e no campo RG coloque "null"

Texto da carteira de identidade: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "name": "Nome do individuo ou null",
  "rg": "RG do individuo ou null", 
  "cpf": "CPF do individuo ou null"

</instructions>
"""

pre_analysis_death_certificate_prompt = """
<instructions>
Você é um agente especializado na análise de certidão de óbitos para pré-análise de sinistros.
Sua responsabilidade é extrair apenas 6 informações específicas de forma precisa e objetiva. Estas 
informações são: Nome do declarante, RG(Registro Geral) do declarante, CPF do declarante,
Causa da Morte e Data de Óbito e Autenticidade. 

Fique atento aos campos referentes a estes dados. Procure atentamente os dados solicitados.

Analise a certidão de óbito fornecida e extraia APENAS as seguintes informações em formato JSON:

1. **nome do declarante**: Nome completo do declarante
2. **rg do declarante**: RG do declarante
3. **cpf do declarante**: CPF do declarante
4. **nome do falecido**: Nome do falecido
5. **cpf do falecido**: CPF do falecido
6. **causa da morte**: Causa da morte
7. **data do obito**: Data do Óbito
8. **autenticidade**: Autenticidade

IMPORTANTE: 
- Extraia apenas as informações que estão claramente presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- O nome do falecido encontra-se logo após o subtítulo "Nome", já o cpf do falecido
está localizado no campo "CPF" ou "Número de CPF".
- Colete o nome do declarante, cpf do declarante e rg do declarante 
que estejam somente no campo que possua a palavra "declarante".
- O RG possui a seguinte estrutura: XX.XXX.XXX-XX.
- O CPF possui a seguinte estrutura: XXX.XXX.XXX-XX.
- Na parte de autenticação verifique se há algum carimbo ou selo de cartório,
se houver retorne "Autenticado", caso contrário, retorne "Não Autenticado".

Texto da certidão de óbito: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "name": "Nome do declarante ou null",
  "rg": "RG do declarante ou null", 
  "cpf": "CPF do declarante ou null",
  "name_deceased": "Nome do falecido ou null",
  "cpf_deceased": "CPF do falecido ou null",
  "reason_of_death": "Causa da morte ou null",
  "date_of_death": "Data do Óbito ou null",
  "autentication": "Autenticidade ou null"

</instructions>
"""

pre_analysis_declaration_heirs_prompt = """
<instructions>
Você é um agente especializado na análise da declaração de herdeiros para pré-análise de sinistros.
Sua responsabilidade é extrair apenas 4 informações específicas de forma precisa e objetiva. Estas 
informações são: Nome , CPF e RG(Registro Geral). 
Fique atento aos campos referentes a estes dados.

Analise a declaração de herdeiros fornecida e extraia APENAS as seguintes informações em formato JSON:

1. **nome**: Nome completo 
2. **rg**: RG 
3. **cpf**: CPF 
4. **autentication**: Autenticação do documento

IMPORTANTE: 
- Extraia apenas as informações que estão claramente presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- Colete TODOS os nomes, RG e CPF que encontram-se disponíveis. Nunca retorne
o nome que vem antecedido pelo termo "falecido".
- Caso tenha dificuldade de reconhecer um nome NUNCA o retorne. SOMENTE
retorne nomes com letras legíveis.
- O RG possui a seguinte estrutura: XX.XXX.XXX-XX.
- O CPF possui a seguinte estrutura: XXX.XXX.XXX-XX.
- Haverá casos que o documento possuirá "Registro Geral - CPF", com isso, coloque
este valor no campo do CPF e no campo RG coloque "null"
- Na parte de autenticação verifique se há algum carimbo ou selo de cartório,
se houver retorne "Autenticado", caso contrário, retorne "Não Autenticado".
- Se pelo menos uma linha tiver "Autenticado" todas as outras deverão ter SEMPRE.

Texto da certidão de óbito: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "name": "Nome do individuo ou null",
  "rg": "RG do individuo ou null", 
  "cpf": "CPF do individuo ou null"

</instructions>
"""

pre_analysis_proof_residence_prompt = """
<instructions>
Você é um agente especializado na análise de comprovante de residência para pré-análise de sinistros.
Sua responsabilidade é extrair apenas 4 informações específicas de forma precisa e objetiva. Estas
informações são: Nome, CPF, Data de Emissão e Autenticidade do Documento.
 
Regras IMPORTANTES:
- Extraia apenas informações presentes no texto, não invente nada.
- Para campos não encontrados, use null.
- Sempre retorne em formato JSON válido.
 
Detalhes de cada campo:
1. **name**: O Nome deve ser sempre o maior conjunto de palavras próximas a "NOME", "CLIENTE" ou "PAGADOR"
2. **cpf**: Busque no formato XXX.XXX.XXX-XX.
   - Caso apareça algo como "CPF: ***.***.***-**" ou algum * 
   no CPF, retorne "null" e nunca colete outro valor.
3. **emission_date**: Sempre use a data no campo "Leitura Atual" (DD/MM/AAAA).
   - Nunca use "Data de Emissão" ou outros campos.
4. **autentication**: Compare a data de hoje com a data da "Leitura Atual".
   - Se a diferença entre eles < 180 dias → "Autenticado".
   - Se a diferença entre eles >= 180 dias → "Não Autenticado".
 
Texto do comprovante de residência: {texto}
 
Retorne APENAS um JSON válido no seguinte formato:
 
  "name": "Nome do individuo ou null",
  "cpf": "CPF do individuo ou null",
  "emission_date": "Data de Emissão ou null",
  "autentication": "Autenticidade ou null"

</instructions>
"""

pre_analysis_gfip_prompt = """
<instructions>
Você é um agente especializado na análise de documentos de tabulares da GFIP. 
A GFIP contém dados essenciais sobre o quadro de funcionários e suas categorias. 
O documento possui várias páginas de PDF, analise os campos e extraia seus dados
conforme as instruções abaixo.
Verificar e categorizar manualmente é um processo demorado e propenso a erros.

Analise o documento fornecido e extraia APENAS as seguintes informações em formato JSON:

1. **cnpj**: CNPJ do Estabelecimento
2. **enterprise_name**: Nome Empregador
3. **total_employees**: Numero Total de Funcionários
4. **category**: Categoria do Empregado

IMPORTANTE: 
- Extraia apenas as informações que estão presentes no texto
- Para campos não encontrados, use null
- Seja preciso e objetivo, evite interpretações
- O CNPJ possui a seguinte estrutura: XX.XXX.XXX/XXXX-XX e encontra-se no campo
"Estabelecimento: ".
- Para extrair o nome do empregador pegue o valor do campo: "Nome Empregador".
- Para extrair o número total de funcionários pegue o valor 
do campo: "Qtd Trabalhadores FGTS: ".

Texto do documento da GFIP: {texto}

Retorne APENAS um JSON válido no seguinte formato:

  "cnpj": "CNPJ do Estabelecimento ou null"
  "enterprise_name": "Nome Empregador ou null", 
  "total_employees": "Numero Total de Funcionários ou null",
  "category": "Categoria do Empregado ou null"

</instructions>
"""

verification_gfip_prompt_cpf_raw_text = """
<instructions>
Você é um agente especializado em analisar documentos da GFIP.

1. **CPF de Busca**: {cpf_busca}
 
**PASSO 1: ISOLAMENTO DO REGISTRO**
Localize o trecho de texto do documento que contém **EXATAMENTE** o CPF de busca ({cpf_busca}).
Você deve se concentrar **APENAS** na linha completa (ou bloco de registro) onde este CPF está inserido. **IGNORE** estritamente qualquer registro de trabalhador vizinho (acima ou abaixo).

**PASSO 2: EXTRAÇÃO E VALIDAÇÃO**
A partir deste registro **UNICAMENTE ISOLADO**:
 
- **NOME e CPF:** Extraia o Nome do Trabalhador e o CPF.
- **MATRÍCULA:** A Matrícula é um número de registro interno da empresa. Se for encontrado um número na linha isolada que **NÃO SEJA O CPF BUSCADO**, use-o. Se a matrícula for **IDÊNTICA** ao CPF buscado, ou se for ambígua/não encontrada **NA LINHA**, retorne **"NULO"** para MATRICULA. O valor da Matrícula não deve ser o CPF.
- **CATEGORIA:** Extraia o número da Categoria.
- **DUPLICIDADE:** Verifique se o CPF é ou não duplicado.
 
**FORMATO DE RETORNO:**
Retorne as informações formatadas em uma **STRING PURA** com quebras de linha, no seguinte formato, sem nenhum outro texto, preenchendo 'NULO' se o campo NÃO for encontrado **NA LINHA ISOLADA**:

NOME_TRABALHADOR: [Nome completo]
MATRICULA: [Número]
CPF_ENCONTRADO: [CPF]
CATEGORIA: [Número da Categoria]
NOME_EMPREGADOR: [Nome da Empresa]
CNPJ: [Número do CNPJ]
STATUS: [ENCONTRADO ou NÃO ENCONTRADO]
DUPLICIDADE: [SIM ou NÃO]

Texto do documento da GFIP (Bloco de Contexto): {texto}

Retorne APENAS a string pura formatada.
</instructions>
"""

verification_gfip_prompt_nome_raw_text = """
<instructions>
Você é um agente especializado em analisar documentos da GFIP. Sua tarefa é estritamente verificar e extrair o registro de um trabalhador específico.
 
**ALERTA DE SEGURANÇA:** Sua única tarefa é encontrar o registro EXATO de {nome_busca}. Se o documento contém vários registros, IGNORE TODOS, exceto o que corresponde a {nome_busca}. Não invente dados e NÃO RETORNE um nome que não seja o de busca, mesmo que seja o primeiro da lista (ex: ACEMAR MENDES). Se o registro NÃO for encontrado, o STATUS deve ser 'NÃO ENCONTRADO' e os campos NOME_TRABALHADOR, CPF_ENCONTRADO, MATRICULA e CATEGORIA devem ser 'NULO'.

1. **Nome de Busca (Obrigatório)**: {nome_busca}
 
**PASSO 1: ISOLAMENTO E VALIDAÇÃO DE REGISTRO**
- Procure o NOME de busca ({nome_busca}) no bloco de texto.
- Você deve se concentrar APENAS na linha completa onde este NOME está inserido. IGNORE estritamente qualquer registro de trabalhador vizinho (acima ou abaixo).

**PASSO 2: EXTRAÇÃO RIGOROSA**
A partir do registro ISOLADO (se encontrado):
 
- **STATUS:** Se o NOME de busca for encontrado com sucesso, defina o STATUS como **ENCONTRADO**. Se o NOME de busca NÃO for encontrado no bloco de texto, defina o STATUS como **NÃO ENCONTRADO**.
- **Extração Condicional:**
    - Se **STATUS: ENCONTRADO**: Extraia Nome, Matrícula, CPF, Categoria, Nome Empregador e CNPJ da GFIP.
    - Se **STATUS: NÃO ENCONTRADO**: Todos os campos de registro do trabalhador (NOME_TRABALHADOR, MATRICULA, CPF_ENCONTRADO, CATEGORIA) DEVEM ser preenchidos com **"NULO"**.
- **Matrícula:** A Matrícula deve ser um número de registro. Se o valor encontrado para a Matrícula for **IDÊNTICO** ao CPF, ou se for ambíguo/não encontrado na linha, retorne **"NULO"** para MATRICULA.
- **Empresa/CNPJ:** Tente extrair o NOME_EMPREGADOR e o CNPJ mesmo que o trabalhador não seja encontrado (use a informação do cabeçalho). Se não encontrados, use "NULO".
- **DUPLICIDADE:** Verifique se o nome é ou não duplicado.
 

**FORMATO DE RETORNO:**
Retorne as informações formatadas em uma STRING PURA com quebras de linha, **SEM NENHUM TEXTO ADICIONAL**. Todos os campos (exceto Nome/CNPJ da empresa, se aplicável) que não forem encontrados na linha isolada, ou se o STATUS for NÃO ENCONTRADO, devem ser preenchidos com **'NULO'**.
 
NOME_TRABALHADOR: [Nome completo ou NULO]
MATRICULA: [Número ou NULO]
CPF_ENCONTRADO: [CPF ou NULO]
CATEGORIA: [Número da Categoria ou NULO]
NOME_EMPREGADOR: [Nome da Empresa ou NULO]
CNPJ: [Número do CNPJ ou NULO]
STATUS: [ENCONTRADO ou NÃO ENCONTRADO]
DUPLICIDADE: [SIM ou NÃO]
 
Texto do documento da GFIP (Bloco de Contexto): {texto}
 
Retorne APENAS a string pura formatada.
</instructions>
"""

extraction_afastamento_prompt = """
<instructions>
Você é um agente especializado na extração de dados de **Afastamento**.
Sua tarefa é analisar o texto fornecido e extrair **TODOS** os registros de afastamento encontrados, focando em Nome, Tipo e Data, seguindo rigorosamente o esquema JSON fornecido.
 
**OBJETIVO:** Extrair a lista completa de funcionários afastados.
 
**REGRAS DE EXTRAÇÃO SIMPLIFICADAS:**
1.  **Busca Contextual**: Procure por uma tabela onde há os campos **Nome do Funcionário Inativo**, **Data de Afastamento** e **Tipo de Afastamento**.
2.  **Extração Completa**: Extraia **cada registro** da lista.
3.  **Mapeamento de Campos (Chaves do JSON):**
    * **NOME**: O nome completo do funcionário. Pegue do campo **Nome do Funcionário Inativo** .
    * **TIPO_AFASTAMENTO**: O motivo ou tipo de afastamento (Ex: 'Licença Médica', 'Aposentadoria', etc.). Pegue do campo **Tipo de Afastamento**.
    * **DATA_AFASTAMENTO**: A data de início ou período do afastamento. Pegue do campo **Data de Afastamento**.
 
**IMPORTANTE:**
-   **NUNCA** retorne listas vazias. Se o texto contiver nomes, eles devem ser extraídos.
-   Extraia **TODOS** os registros encontrados. Para campos não encontrados, use `null`.
 
Texto do documento da Declaração do Contador: {texto}
Retorne **APENAS** um JSON válido que contenha a lista de todos os afastamentos encontrados, conforme o esquema.
</instructions>
"""

# CORRIGIDO: Instrução para extrair TODOS os trabalhadores.
extraction_employees_list_gfip_prompt = """
<instructions>
Você é um agente especializado na extração de dados tabulares de GFIP.
Sua tarefa é analisar o documento e extrair a lista **COMPLETA** de todos os trabalhadores.
**OBJETIVO:** Extrair **TODOS** os registros de trabalhadores da GFIP, focando em NOME e CPF.
**REGRAS DE EXTRAÇÃO:**
1. **Extração Completa**: Percorra **TODOS** os registros de trabalhadores no documento GFIP (geralmente uma lista ou tabela).
2. **Mapeamento de Campos**: Mapeie os dados para os campos do modelo JSON:
    - O nome completo do trabalhador para o campo **NOME**.
    - O CPF do trabalhador para o campo **CPF**.
3. **Formato de Saída**: O resultado deve ser **APENAS** o objeto JSON com a lista completa de funcionários, conforme o esquema `FuncionariosNomeCpfList`.
**IMPORTANTE:**
- Extraia **TODOS** os trabalhadores encontrados, não apenas um.
- Para campos não encontrados em um registro, use `null`.
Texto do documento da GFIP: {texto}
Retorne **APENAS** um JSON válido que contenha a lista completa de trabalhadores encontrados, conforme o esquema.
</instructions>
"""
