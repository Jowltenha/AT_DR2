import json
import random

def gerar_manual_json(caminho_arquivo: str = "manual_equipamentos.json", seed: int = 42) -> None:
    """Gera um arquivo JSON estático representando manuais de 5 equipamentos industriais fictícios

    utilizando uma seed fixa para reprodutibilidade.
    """
    random.seed(seed)

    manuais = [
        {
            "codigo": "EQ-101",
            "nome": "Bomba Centrífuga Alta Pressão BC-2000",
            "codigos_erro": [
                {"codigo": "ERR-01", "causa_provavel": "Cavitação na sucção devido a baixa pressão de entrada (NPSH insuficiente)."},
                {"codigo": "ERR-02", "causa_provavel": "Vazamento no selo mecânico primário por desgaste de gaxeta."}
            ]
        },
        {
            "codigo": "EQ-102",
            "nome": "Compressor de Parafuso Industrial CP-5000",
            "codigos_erro": [
                {"codigo": "ERR-03", "causa_provavel": "Superaquecimento do elemento compressor devido a obstrução do radiador de óleo."},
                {"codigo": "ERR-04", "causa_provavel": "Pressão de descarga elevada por falha na válvula de retenção."}
            ]
        },
        {
            "codigo": "EQ-103",
            "nome": "Inversor de Frequência Trifásico IF-900",
            "codigos_erro": [
                {"codigo": "ERR-05", "causa_provavel": "Sobretensão no barramento DC ocasionada por rampa de frenagem muito curta."},
                {"codigo": "ERR-06", "causa_provavel": "Falha de fase na alimentação de entrada R-S-T."}
            ]
        },
        {
            "codigo": "EQ-104",
            "nome": "Caldeira a Gás Alta Capacidade CG-800",
            "codigos_erro": [
                {"codigo": "ERR-07", "causa_provavel": "Falha na chama do queimador principal por sujeira nos eletrodos de ignição."},
                {"codigo": "ERR-08", "causa_provavel": "Nível crítico de água no tambor de vapor por bloqueio da bomba de alimentação."}
            ]
        },
        {
            "codigo": "EQ-105",
            "nome": "Torno CNC Alta Precisão TC-300",
            "codigos_erro": [
                {"codigo": "ERR-09", "causa_provavel": "Sobrecarga no motor do fuso principal devido a avanço excessivo da ferramenta."},
                {"codigo": "ERR-10", "causa_provavel": "Erro de posicionamento do eixo Z por desalinhamento do encoder óptico."}
            ]
        }
    ]

    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(manuais, f, indent=4, ensure_ascii=False)

    print(f"[OK] Arquivo '{caminho_arquivo}' gerado com sucesso usando a SEED {seed}.")

if __name__ == "__main__":
    gerar_manual_json()
