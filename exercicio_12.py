import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from agents import Agent, Runner, SQLiteSession
from exercicio_10 import buscar_no_manual_extenso_rag

load_dotenv()


class AgentQueryRequest(BaseModel):
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


app = FastAPI(
    title="Serviço REST do Agente Integrador de Manutenção",
    description="Interface HTTP REST exposta para o sistema de despacho de chamados de campo.",
    version="1.0.0",
)

TASKS_DB: Dict[str, Dict[str, Any]] = {}


async def processar_chamada_agente_background(
    task_id: str, codigo_equipamento: str, pergunta: str, session_id: str
):
    """Função de background executada assincronamente via BackgroundTasks utilizando o OpenAI Agents SDK."""
    print(
        f"\n ⚙️ [BACKGROUND TASK iniciada - TaskID: {task_id}] Processando RAG + Agent para {codigo_equipamento}..."
    )

    try:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not model_name or "/" in model_name:
            model_name = "gpt-4o-mini"

        session = SQLiteSession(session_id=session_id)
        agente = Agent(
            name="AgenteIntegradorREST",
            instructions="Você é um assistente técnico exposto via API REST.",
            tools=[buscar_no_manual_extenso_rag],
            model=model_name,
        )

        prompt_completo = (
            f"Equipamento: {codigo_equipamento}. Pergunta: {pergunta}"
        )

        result = await Runner.run(agente, prompt_completo, session=session)

        TASKS_DB[task_id] = {
            "status": "done",
            "codigo_equipamento": codigo_equipamento,
            "resposta": str(result.final_output),
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
        print(f" ❌ [BACKGROUND TASK erro - TaskID: {task_id}]: {e}")


@app.get(
    "/agent/test",
    response_model=AgentTestResponse,
    summary="Endpoint GET de Teste e Sanidade do Serviço",
)
async def get_agent_test() -> AgentTestResponse:
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
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    TASKS_DB[task_id] = {
        "status": "queued",
        "codigo_equipamento": request_data.codigo_equipamento,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(
        processar_chamada_agente_background,
        task_id,
        request_data.codigo_equipamento,
        request_data.pergunta,
        request_data.session_id,
    )

    return AgentQueryResponse(
        task_id=task_id,
        status="queued",
        mensagem="Solicitação de diagnóstico recebida e enviada para processamento em segundo plano.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def main():
    print("=" * 70)
    print(" EXERCÍCIO 12 - EXPONDO O AGENTE VIA FASTAPI COM BACKGROUNDTASKS ")
    print("=" * 70)

    client = TestClient(app)

    print("\n[1. Testando Endpoint GET /agent/test (Retorno Fixo Pydantic)]")
    res_get = client.get("/agent/test")
    print(f"HTTP Status Code: {res_get.status_code}")
    print("Corpo da Resposta (AgentTestResponse):")
    print(res_get.json())

    print("\n" + "-" * 70)
    print(
        "[2. Testando Endpoint POST /agent/diagnostico (BackgroundTasks Não Bloqueante)]"
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
