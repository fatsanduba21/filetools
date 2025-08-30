import os
import subprocess

def descompactar_arquivos(pasta_raiz):
    """
    Descompacta arquivos ZIP e RAR em uma pasta, recursivamente.

    Args:
        pasta_raiz (str): O caminho da pasta onde os arquivos serão descompactados.
    """

    for pasta_atual, _, arquivos in os.walk(pasta_raiz):
        for arquivo in arquivos:
            caminho_completo = os.path.join(pasta_atual, arquivo)

            # Descompactar arquivos ZIP
            if arquivo.endswith(".zip"):
                print(f"Descompactando: {caminho_completo}")
                subprocess.run(["winrar", "x", "-o+", caminho_completo, pasta_atual])  # Descompacta na mesma pasta

            # Descompactar arquivos RAR (após descompactar os ZIPs)
            elif arquivo.endswith(".rar") and not any(f.endswith(".zip") for f in os.listdir(pasta_atual)):
                print(f"Descompactando: {caminho_completo}")
                subprocess.run(["winrar", "x", "-o+", caminho_completo, pasta_atual])

if __name__ == "__main__":
    pasta_a_descompactar = input("Digite o caminho da pasta (ex: c:\\pasta\\): ")
    descompactar_arquivos(pasta_a_descompactar)
