import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# Importa as estruturas do Exercício 11 para integração real no background task
from exercicio_11 import AgentIntegrador, RunnerIntegrador, SQLiteSession

load_dotenv()

# --- 1. MODELOS PYDANTIC PARA REQUEST E RESPONSE SCHEMAS ---


class AgentQueryRequest(BaseModel):
    """Modelo Pydantic para validação do payload HTTP POST recebido do sistema de despacho."""

    codigo_equipamento: str = Field(
        ...,
        description="Código identificador único do equipamento (ex: CG-800, EQ-101)",
        examples=["CG-800"],
    )
    pergunta: str = Field(
        ...,
        description="Pergunta ou dúvida técnica enviada pelo técnico de campo",
        examples=[
            "Qual o torque dos parafusos do flange e a graxa recomendada?"
        ],
    )
    session_id: Optional[str] = Field(
        default="sessao_despacho_default",
        description="Identificador único da sessão de atendimento para persistência",
    )


class AgentQueryResponse(BaseModel):
    """Modelo Pydantic para o corpo da resposta do POST (retornado imediatamente ao sistema externo)."""

    task_id: str = Field(
        ..., description="Identificador único da tarefa assíncrona gerada"
    )
    status: str = Field(
        ..., description="Estado inicial da tarefa (ex: 'queued', 'processing')"
    )
    mensagem: str = Field(
        ...,
        description="Confirmação de enfileiramento imediato do processamento",
    )
    timestamp: str = Field(
        ..., description="Data/hora UTC do enfileiramento em formato ISO"
    )


class AgentTestResponse(BaseModel):
    """Modelo Pydantic para o corpo da resposta do GET (retorna valor fixo de teste/healthcheck)."""

    status: str = Field(
        default="ok", description="Status de integridade do serviço"
    )
    servico: str = Field(
        default="Agente Integrador REST Service",
        description="Nome da aplicação",
    )
    versao: str = Field(
        default="1.0.0", description="Versão atual do serviço REST"
    )
    timestamp: str = Field(
        ..., description="Data/hora UTC da consulta de teste"
    )


# --- 2. INICIALIZAÇÃO DA APLICAÇÃO FASTAPI E ARMAZENAMENTO DE TAREFAS ---

app = FastAPI(
    title="Serviço REST do Agente Integrador de Manutenção",
    description="Interface HTTP REST exposta para o sistema de despacho de chamados de campo.",
    version="1.0.0",
)

# Dicionário em memória simulando a tabela de tarefas de background
TASKS_DB: Dict[str, Dict[str, Any]] = {}


# --- 3. PROCESSAMENTO EM SEGUNDO PLANO (BackgroundTasks) ---


async def processar_chamada_agente_background(
    task_id: str, codigo_equipamento: str, pergunta: str, session_id: str
):
    """Função de background executada assincronamente via BackgroundTasks.

    Invoca o agente integrador (RAG + SQLiteSession) sem bloquear o retorno HTTP.
    """
    print(
        f"\n ⚙️ [BACKGROUND TASK iniciada - TaskID: {task_id}] Processando RAG + Agent para {codigo_equipamento}..."
    )

    try:
        session = SQLiteSession(session_id=session_id)
        agente = AgentIntegrador(
            name="AgenteIntegradorREST",
            instructions="Você é um assistente técnico exposto via API REST.",
        )

        prompt_completo = (
            f"Equipamento: {codigo_equipamento}. Pergunta: {pergunta}"
        )

        # Execução do agente integrador (RAG + SQLite) em segundo plano
        resposta_agente = await RunnerIntegrador.run(
            agente, prompt_completo, session, use_rag=True
        )

        TASKS_DB[task_id] = {
            "status": "done",
            "codigo_equipamento": codigo_equipamento,
            "resposta": resposta_agente,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        print(
            f" ✅ [BACKGROUND TASK concluída - TaskID: {task_id}] Resposta salva com sucesso!"
        )

    except Exception as e:
        TASKS_DB[task_id] = {
            "status": "error",
            "erro": str(e),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        print(
            f" ❌ [BACKGROUND TASK erro - TaskID: {task_id}]: {e}"
        )


# --- 4. ENDPOINTS HTTP DA API REST ---


@app.get(
    "/agent/test",
    response_model=AgentTestResponse,
    summary="Endpoint GET de Teste e Sanidade do Serviço",
)
async def get_agent_test() -> AgentTestResponse:
    """Endpoint GET assíncrono que retorna um valor fixo de teste validado pelo Pydantic."""
    return AgentTestResponse(
        status="ok",
        servico="Agente Integrador REST Service",
        versao="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/agent/diagnostico",
    response_model=AgentQueryResponse,
    status_code=202,
    summary="Endpoint POST Assíncrono com BackgroundTasks",
)
async def post_agent_diagnostico(
    request_data: AgentQueryRequest, background_tasks: BackgroundTasks
) -> AgentQueryResponse:
    """Endpoint POST assíncrono que recebe o payload Pydantic e agenda o agente via BackgroundTasks,

    respondendo imediatamente (HTTP 202 Accepted).
    """
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    TASKS_DB[task_id] = {
        "status": "queued",
        "codigo_equipamento": request_data.codigo_equipamento,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Enfileira a tarefa pesada em segundo plano via BackgroundTasks
    background_tasks.add_task(
        processar_chamada_agente_background,
        task_id,
        request_data.codigo_equipamento,
        request_data.pergunta,
        request_data.session_id,
    )

    # Retorna resposta imediata para o sistema de despacho sem bloquear a requisição HTTP
    return AgentQueryResponse(
        task_id=task_id,
        status="queued",
        mensagem="Solicitação de diagnóstico recebida e enviada para processamento em segundo plano.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# --- EXECUÇÃO DEMONSTRATIVA VIA TESTCLIENT ---


def main():
    print("=" * 70)
    print(" EXERCÍCIO 12 - EXPONDO O AGENTE VIA FASTAPI COM BACKGROUNDTASKS ")
    print("=" * 70)

    client = TestClient(app)

    # 1. Teste do Endpoint GET /agent/test (Retorno Fixo Validado com Pydantic)
    print("\n[1. Testando Endpoint GET /agent/test (Retorno Fixo Pydantic)]")
    res_get = client.get("/agent/test")
    print(f"HTTP Status Code: {res_get.status_code}")
    print("Corpo da Resposta (AgentTestResponse):")
    print(res_get.json())

    # 2. Teste do Endpoint POST /agent/diagnostico (Resposta Imediata via BackgroundTasks)
    print("\n" + "-" * 70)
    print(
        "[2. Testando Endpoint POST /agent/diagnostico (BackgroundTasks Imprudente/Não Bloqueante)]"
    )

    payload = {
        "codigo_equipamento": "CG-800",
        "pergunta": "Qual o torque dos parafusos do flange e a graxa recomendada?",
        "session_id": "sessao_sistema_despacho_99",
    }

    print(f"Payload Enviado: {payload}\n")

    start_time = datetime.now()
    res_post = client.post("/agent/diagnostico", json=payload)
    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"HTTP Status Code: {res_post.status_code} (202 Accepted)")
    print(f"Tempo de Resposta do HTTP POST: {elapsed:.4f} segundos (Resposta IMEDIATA!)")
    print("Corpo da Resposta (AgentQueryResponse):")
    print(res_post.json())


if __name__ == "__main__":
    main()
