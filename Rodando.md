# 🚀 Guia de Execução dos Exercícios (AT DR2)

Este documento contém todas as instruções necessárias para configurar o ambiente e executar os exercícios do Assessment.

---

## 1. 📋 Pré-requisitos

- **Python 3.10** ou superior instalado.
- Terminal Linux / WSL / macOS ou Prompt de Comando / PowerShell no Windows.

---

## 2. 🛠️ Configuração do Ambiente Virtual (`venv`)

Na raiz do projeto (`/home/jowlt/AT_DR2`), execute:

### No Linux / WSL / macOS:
```bash
# 1. Criar o ambiente virtual venv
python3 -m venv venv

# 2. Ativar o ambiente virtual
source venv/bin/activate

# 3. Instalar todas as dependências
pip install -r requirements.txt
```

### No Windows (PowerShell / Prompt):
```powershell
# 1. Criar o ambiente virtual venv
python -m venv venv

# 2. Ativar o ambiente virtual
.\venv\Scripts\activate

# 3. Instalar todas as dependências
pip install -r requirements.txt
```

---

## 3. 🔑 Configuração das Variáveis de Ambiente (`.env`)

Verifique se o seu arquivo `.env` na raiz do projeto está configurado corretamente:

```env
OPENAI_API_KEY=sk-proj-...
OPENAI_BASE_URL=http://localhost:20128/v1 (URL do 9router)
OPENAI_MODEL=ag/gemini-3.6-flash-high
```

*(Obs: Se estiver usando a API oficial da OpenAI diretamente, defina `OPENAI_BASE_URL=https://api.openai.com/v1` e seu modelo preferido como `gpt-4o-mini`).*

---

## 4. 🏃‍♂️ Como Executar Cada Exercício

Certifique-se de que o ambiente virtual `venv` está **ativado** antes de rodar os comandos abaixo.

### 📌 Exercício 1 - Ambiente e Primeiro Agente
```bash
python3 exercicio_01.py
```
- **O que observar no terminal:** O agente inicializará, fará a chamada assíncrona usando as credenciais do `.env` e imprimirá a resposta formatada dentro de uma caixa estilizada.

---

### 📌 Exercício 2 - Protocolo de Conversa do Agente
```bash
python3 exercicio_02.py
```
- **O que observar no terminal:**
  1. A conversa multi-turno demonstrando o acúmulo de histórico (`system`, `user`, `assistant`), onde a 2ª pergunta ("Quais são os óleos lubrificantes recomendados para ele?") é respondida contextualizando o Compressor CP-500 citado no 1º turno.
  2. Os testes comparativos de hiperparâmetros (`temperature`, `top_p`, `max_tokens` e `frequency_penalty`).

---

### 📌 Exercício 3 - Primitivos do SDK e Agente de Diagnóstico
```bash
python3 exercicio_03.py
```
- **O que observar no terminal:**
  1. A chamada assíncrona (`Runner.run`) processando uma dúvida técnica sobre caldeira e motor a 90°C, gerando a saída estruturada Pydantic com a aplicação das regras de segurança `SEG-01` e `SEG-02`.
  2. A chamada síncrona (`Runner.run_sync`) processando uma pergunta administrativa (férias/reembolso), ativando a recusa de escopo.

---

### 📌 Exercício 4 - Seleção de Modelo, Streaming e Monitoramento
```bash
python3 exercicio_04.py
```
- **O que observar no terminal:**
  1. Injeção transparente do identificador da filial (`FILIAL-SP-07`) na tool via `RunContextWrapper`.
  2. A saída progressiva em tempo real token por token (`run_streamed`) respeitando os parâmetros do `ModelSettings`.
  3. O dicionário de métricas de telemetria (tempo e tokens consumidos) com a chave `"status": "done"`.

---

### 📌 Exercício 5 - Primeira Ferramenta: Consulta ao Manual do Equipamento
```bash
python3 exercicio_05.py
```
- **O que observar no terminal:**
  1. A geração (ou leitura) do arquivo `manual_equipamentos.json` (seed 42).
  2. A detecção do `Tool Calling` chamando a função `consultar_manual_equipamento(codigo_equipamento='EQ-103')`.
  3. A resposta final do agente informando a causa do erro `ERR-05` extraída diretamente do arquivo JSON real.

---

### 📌 Exercício 6 - Controle de Seleção de Tool e Histórico de Execução
```bash
python3 exercicio_06.py
```
- **O que observar no terminal:**
  1. Invocação forçada de ferramenta com `tool_choice` para testes automatizados.
  2. Demonstração de economia de chamadas à API com `stop_on_first_tool=True` (1 chamada vs 2 chamadas).
  3. Impressão da estrutura padronizada de histórico persistido no formato `TResponseInputItem` (role, content, timestamp, tool_call_id).

---

### 📌 Exercício 7 - Erros Seguros, Saída Estruturada e SQLite Session
```bash
python3 exercicio_07.py
```
- **O que observar no terminal:**
  1. O tratamento gracioso da exceção `EquipamentoNaoEncontradoError` pelo `failure_error_function` para o equipamento `EQ-999` sem quebrar o programa.
  2. A geração da saída estruturada no modelo Pydantic `DiagnosticoEquipamento`.
  3. A persistência em banco de dados `SQLiteSession` respondendo à 2ª pergunta contextual ("e qual a ação recomendada mesmo?") sem repetir o código da máquina.

---

### 📌 Exercício 8 - Modelos Aninhados e Agente de Diagnóstico Completo
```bash
python3 exercicio_08.py
```
- **O que observar no terminal:**
  1. Teste com código válido (`EQ-101`) gerando o objeto Pydantic aninhado acessado via `result.final_output` (com a lista de peças `PecaRecomendada`).
  2. Teste com código inválido (`EQ-999`) acionando a função assíncrona `failure_error_function_async`.

---

### 📌 Exercício 9 - Histórico de Conversa e Sessão Persistente
```bash
python3 exercicio_09.py
```
- **O que observar no terminal:**
  1. Primeira Execução (Dia 1): Processamento e gravação de 3 turnos de conversa sobre o Compressor `EQ-102` no banco `persisted_agent_sessions.db` em formato `TResponseInputItem`.
  2. Segunda Execução (Dia 2 / Novo Processo): Recarregamento do histórico persistido no disco e resposta contextualizada para a pergunta 4 ("resumo dos códigos ERR-03 e ERR-04 que discutimos ontem").

---

### 📌 Exercício 10 - Pipeline de RAG sobre Manuais Técnicos
```bash
python3 exercicio_10.py
```
- **O que observar no terminal:**
  1. A geração do manual extenso de 22 parágrafos e o seu fatiamento (`chunking`) pelo `TextChunker`.
  2. A execução da busca semântica RAG recuperando o Chunk 11 (localizado no meio do documento, com score de relevância destacado).
  3. A resposta do agente informando o torque exato de 340 Nm e lubrificação com graxa fluorada a cada 6 meses.

---

### 📌 Exercício 11 - Agente Integrador com Memória e Avaliação de Estratégia
```bash
python3 exercicio_11.py
```
- **O que observar no terminal:**
  1. Execução do Cenário A (Atendimento Multi-turno em Sequência com `SQLiteSession` e RAG), resolvendo perguntas anafóricas contextuais ("nesse mesmo procedimento").
  2. Execução do Cenário B (Consulta Única Pontual sobre procedimento raro de economizador), recuperando dados semânticos com RAG.

---

### 📌 Exercício 12 - Expondo o Agente via FastAPI
```bash
python3 exercicio_12.py
```
- **O que observar no terminal:**
  1. Execução do teste do endpoint `GET /agent/test` retornando os dados fixos validados por Pydantic (`AgentTestResponse`).
  2. Execução do endpoint `POST /agent/diagnostico` demonstrando resposta imediata (HTTP 202 Accepted em milissegundos) enquanto a tarefa é enfileirada via `BackgroundTasks`.

---

### 📌 Exercício 13 - Padrão de Submissão e Consulta Assíncrona
```bash
python3 exercicio_13.py
```
- **O que observar no terminal:**
  1. Submissão da pergunta via `POST /agent/run` retornando resposta imediata (HTTP 202 Accepted) com o `task_id` gerado.
  2. Consulta imediata via `GET /agent/status/{task_id}` exibindo o estado `"pending"`.
  3. Consulta final via `GET /agent/status/{task_id}` exibindo a transição do estado para `"done"` com a resposta completa e o tempo de execução.

---

### 📌 Exercício 14 - Síntese: O Agente como Serviço REST Completo
```bash
python3 exercicio_14.py
```
- **O que observar no terminal:**
  1. Fluxo End-to-End: Submissão em `POST /agent/run` -> Polling em `GET /agent/status/{task_id}` até `"done"` -> Obtenção do resultado estruturado Pydantic (com lista de peças) via `GET /agent/response/{task_id}`.
  2. Teste da Decisão de Projeto: Consulta a um `task_id` inexistente retornando `HTTP 404 Not Found` com detalhamento de erro.

---