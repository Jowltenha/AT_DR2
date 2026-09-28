import asyncio
import json
import os
import sys
from dotenv import load_dotenv
from agents import Agent, Runner, SQLiteSession, function_tool
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)

DB_PATH = "persisted_agent_sessions.db"
SESSION_ID_TECNICO = "sessao_tecnico_carlos_eq102"


@function_tool
def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """Lê o manual em JSON e retorna dados do equipamento."""
    if not os.path.exists(MANUAL_FILE):
        return f"Erro: Arquivo {MANUAL_FILE} não encontrado."
    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)
    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)
    return f"Equipamento {codigo_equipamento} não encontrado."


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 9 - HISTÓRICO DE CONVERSA E SESSÃO PERSISTENTE (SQLITE SDK) ")
    print("=" * 70)

    is_segunda_execucao = "--segunda-execucao" in sys.argv
    session = SQLiteSession(session_id=SESSION_ID_TECNICO, db_path=DB_PATH)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente = Agent(
        name="AgenteManutencaoPersistente",
        instructions="Você é um especialista em manutenção industrial. Lembre-se sempre do histórico prévio da sessão salvo em disco para responder a dúvidas de acompanhamento.",
        tools=[consultar_manual_equipamento],
        model=model_name,
    )

    if not is_segunda_execucao:
        print(
            "\n[PRIMEIRA EXECUÇÃO - DIA 1]: Iniciando sessão de diagnóstico (3 turnos)..."
        )

        t1 = "Estou iniciando o atendimento no Compressor de Parafuso EQ-102. Ele está apresentando o erro ERR-03. Qual a causa?"
        print(f"\n[Turno 1 - Usuário]: {t1}")
        r1 = await Runner.run(agente, t1, session=session)
        print(f"[Turno 1 - Agente]:\n{r1.final_output}")

        t2 = "Quais óleos lubrificantes devo utilizar na manutenção preventiva dele?"
        print(f"\n[Turno 2 - Usuário]: {t2}")
        r2 = await Runner.run(agente, t2, session=session)
        print(f"[Turno 2 - Agente]:\n{r2.final_output}")

        t3 = "Também identificamos o código ERR-04 no painel. O que ele significa?"
        print(f"\n[Turno 3 - Usuário]: {t3}")
        r3 = await Runner.run(agente, t3, session=session)
        print(f"[Turno 3 - Agente]:\n{r3.final_output}")

        print("\n" + "=" * 70)
        print(" FIM DA PRIMEIRA EXECUÇÃO (DIA 1) - DADOS SALVOS EM DISCO ")
        print("=" * 70)
        print(
            f"Histórico estruturado gravado com sucesso no SQLite ('{DB_PATH}')."
        )

        print("\n" + "*" * 70)
        print(" INICIANDO AUTOMATICAMENTE A SEGUNDA EXECUÇÃO (SIMULAÇÃO DIA SEGUINTE) ")
        print("*" * 70)

    print(
        "\n[SEGUNDA EXECUÇÃO - PROCESSO NOVO / DIA 2]: Recarregando sessão do disco..."
    )
    session_dia2 = SQLiteSession(session_id=SESSION_ID_TECNICO, db_path=DB_PATH)

    t4 = "Olá! Voltei ao trabalho hoje. Pode fazer um resumo dos códigos de erro (ERR-03 e ERR-04) e lubrificante que discutimos ontem para este equipamento?"
    print(
        f"\n[Turno 4 (Dia 2 / Novo Processo) - Pergunta Anafórica/Contextual]:\n{t4}"
    )

    r4 = await Runner.run(agente, t4, session=session_dia2)

    print("\n" + "=" * 70)
    print(" RESPOSTA DO AGENTE NO NOVO PROCESSO (USANDO O HISTÓRICO RECARREGADO) ")
    print("=" * 70)
    print(r4.final_output)


if __name__ == "__main__":
    asyncio.run(main())
