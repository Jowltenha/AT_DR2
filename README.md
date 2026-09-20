# Assessment (AT) - Desenvolvimento com Agentes e IA

**Aluno:** João Pedro Barboza  
**Curso:** Desenvolvimento com IA / Engenharia de Software  
**Ambiente de Desenvolvimento:** Antigravity IDE  / Python 3.14  
**Vídeo de Apresentação:** [Link do Vídeo no YouTube (Não Listado)](https://youtu.be/hxg10qvkplM)

---

## 🤖 Declaração de Uso de Ferramentas de Inteligência Artificial

Em conformidade com as orientações do trabalho, a tabela abaixo detalha o uso de assistentes e modelos de IA como suporte para a realização de cada exercício do Assessment:

| Exercício | Descrição do Componente | Agente / Ferramenta Utilizada | Modelo Utilizado | Papel do Modelo / Suporte Prestado |
| :--- | :--- | :--- | :--- | :--- |
| **Exercício 01** | Ambiente e primeiro agente | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Estruturação das classes `Agent`/`Runner` assíncronas, elaboração da justificativa técnica discursiva e função auxiliar de formatação. |
| **Exercício 02** | Protocolo de conversa e hiperparâmetros | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Criação do protocolo de conversa multi-turno acumulativo e testes comparativos de hiperparâmetros (`temperature`, `top_p`, `frequency_penalty`, `max_tokens`). |
| **Exercício 03** | Primitivos do SDK e agente de diagnóstico | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Documentação dos 6 primitivos do SDK, injeção de regras de segurança operacionais na System Message, restrição de domínio e execução síncrona/assíncrona com `output_type`. |
| **Exercício 04** | Seleção de modelo, streaming e monitoramento | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Implementação de `OpenAIChatCompletionsModel`, `RunContextWrapper` para filial_id, respostas token a token com `Runner.run_streamed` e dicionário de telemetria de tokens/tempo. |
| **Exercício 05** | Primeira ferramenta: consulta ao manual | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Geração de base JSON de manuais (seed 42), implementação da ferramenta decorada com `@function_tool` e fluxo de Function Calling com duas etapas. |
| **Exercício 06** | Controle de seleção de tool e histórico | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Desambiguação de docstrings de ferramentas, uso de `tool_choice` forçado, economia de chamadas via `stop_on_first_tool` e histórico `TResponseInputItem`. |
| **Exercício 07** | Erros seguros, saída Pydantic e SQLite | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Tratamento de exceções via `failure_error_function`, resposta Pydantic `DiagnosticoEquipamento` e persistência de sessão multi-turno em banco `SQLiteSession`. |
| **Exercício 08** | Modelos aninhados e agente de diagnóstico | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Estrutura Pydantic aninhada (`PecaRecomendada` em `DiagnosticoEquipamento`), tool assíncrona com `failure_error_function_async` e acesso via `result.final_output`. |
| **Exercício 09** | Histórico de conversa e sessão persistente | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Gerenciamento de histórico estruturado `TResponseInputItem` e persistência em banco SQLite entre execuções distintas do programa. |
| **Exercício 10** | Pipeline de RAG sobre manuais técnicos | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Geração de manual extenso de 22 parágrafos, chunking semântico com `TextChunker` e recuperação RAG do Chunk 11 (torque de 340 Nm). |
| **Exercício 11** | Agente integrador com memória e RAG | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Agente híbrido integrando `SQLiteSession` e RAG, com avaliação comparativa técnica dos cenários de uso para defesa em vídeo. |
| **Exercício 12** | Expondo o agente via FastAPI | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Criação de API REST com FastAPI (`POST /agent/diagnostico` com `BackgroundTasks` não-bloqueante e `GET /agent/test`). |
| **Exercício 13** | Padrão de submissão e consulta assíncrona | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Padrão Polling REST com `POST /agent/run` (202 Accepted + `task_id`) e `GET /agent/status/{task_id}` (`pending` -> `done`). |
| **Exercício 14** | Síntese: agente como serviço REST completo | Claude Agent SDK / IDE Assistant | `ag/gemini-3.6-flash-high` | Serviço REST End-to-End (`POST /agent/run`, `GET /agent/status/{task_id}`, `GET /agent/response/{task_id}`) com justificativa de tratamento HTTP 404 para task_id inexistente. |

---

## 📌 Orientações de Execução

1. Certifique-se de ter o Python 3.10+ instalado.
2. Crie e ative o ambiente virtual:
   - `python3 -m venv venv`
   - `source venv/bin/activate` (Linux/macOS) ou `venv\Scripts\activate` (Windows)
3. Instale as dependências:
   - `pip install -r requirements.txt`
4. Configure o arquivo `.env` com sua chave de API (`OPENAI_API_KEY`).
6. Execute os scripts individuais de cada exercício (ex: `python3 exercicio_01.py`).

---

## 📂 Estrutura do Projeto

```
.
├── .env.example          # Exemplo de configuração de ambiente
├── .gitignore            # Arquivos ignorados pelo Git (venv, .env, etc.)
├── README.md             # Documentação central e citação obrigatória de uso de IA
├── Rodando.md            # Guia completo de configuração e execução dos exercícios
├── requirements.txt      # Dependências Python do projeto (openai, fastapi, uvicorn, pydantic)
├── gerar_manual.py       # Script de geração de dados JSON de manuais (seed 42)
├── gerar_manual_extenso.py # Script de geração do manual extenso (22 parágrafos)
├── exercicio_01.py / .md # Exercício 1: Ambiente e primeiro agente
├── exercicio_02.py / .md # Exercício 2: Protocolo de conversa e hiperparâmetros
├── exercicio_03.py / .md # Exercício 3: Primitivos do SDK e agente de diagnóstico
├── exercicio_04.py / .md # Exercício 4: Seleção de modelo, streaming e monitoramento
├── exercicio_05.py / .md # Exercício 5: Primeira ferramenta (consulta ao manual)
├── exercicio_06.py / .md # Exercício 6: Controle de seleção de tool e histórico
├── exercicio_07.py / .md # Exercício 7: Erros seguros, saída Pydantic e SQLite Session
├── exercicio_08.py / .md # Exercício 8: Modelos aninhados (PecaRecomendada) e async tool
├── exercicio_09.py / .md # Exercício 9: Histórico TResponseInputItem e persistência em disco
├── exercicio_10.py / .md # Exercício 10: Pipeline de RAG semântico sobre manual longo
├── exercicio_11.py / .md # Exercício 11: Agente integrador híbrido (Memória + RAG)
├── exercicio_12.py / .md # Exercício 12: Expondo agente via REST com BackgroundTasks
├── exercicio_13.py / .md # Exercício 13: Padrão de submissão e consulta assíncrona (Polling)
├── exercicio_14.py / .md # Exercício 14: Síntese REST End-to-End e tratamento HTTP 404
└── evidencias/           # Imagens de evidência das execuções (tela inteira com data/hora)
    ├── exercicio_01.png ... exercicio_14.png
```
