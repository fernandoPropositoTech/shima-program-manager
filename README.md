# Shima Program Manager

## Sobre o projeto

Software para organizar o ciclo de programas de máquinas de malharia, inspirado em um problema real de operação industrial. Desenvolvido em Python para uso local no Windows, está em desenvolvimento com arquivos simulados.

Nomes de empresas e programas nos testes são dados simulados de desenvolvimento e não representam clientes ou usuários do produto.

## Problema

O fluxo baseado em arquivos e pen drives dificulta a organização e a localização correta dos programas. O retorno de arquivos ajustados na máquina exige cuidado para evitar sobrescritas indevidas e perda do original.

## Fluxo

APEX → ZERO-ZERO (.000) → repositório → pen drive → máquina → programa ajustado (.112) → identificação → 01_AJUSTES

As extensões `.000` e `.112` representam o fluxo estudado. Os testes utilizam arquivos simulados: o sistema não interpreta nem edita o formato industrial Shima. O pen drive e o ajuste na máquina são simulados localmente.

## Funcionalidades atuais

- Localização de ZERO-ZERO e envio de uma cópia para USB simulado.
- Simulação do retorno `.112`, preservando o `.000`.
- Identificação do programa retornado e do cliente pela estrutura do repositório, sem interpretar prefixos.
- Tratamento de ambiguidades na identificação do retorno.
- Importação e atualização segura do `.112` em `01_AJUSTES`, com temporário e substituição atômica.
- Detecção de retorno sem alteração por comparação de bytes.
- Processamento em lote com isolamento de erros por arquivo.
- Proteção do ZERO-ZERO nas operações implementadas, sem escrita no original.

O ajuste atual conserva seu nome. Não há histórico automático nem pastas de versões. A importação preserva o arquivo no USB simulado.

## Arquitetura atual

| Módulo | Responsabilidade |
| --- | --- |
| `app/config.py` | Define caminhos a partir da localização do projeto. |
| `app/program_finder.py` | Localiza a primeira correspondência de ZERO-ZERO. |
| `app/program_sender.py` | Copia o ZERO-ZERO para USB simulado, protegendo destinos existentes. |
| `app/shima_simulator.py` | Cria um `.112` simulado a partir do `.000` no USB. |
| `app/return_identifier.py` | Identifica o retorno e sinaliza correspondências ambíguas. |
| `app/adjustment_importer.py` | Importa ou atualiza o ajuste identificado em `01_AJUSTES`. |
| `app/batch_processor.py` | Processa os `.112` diretamente no USB e resume os resultados. |

`repository/` organiza os arquivos por ano, cliente e programa. `simulated_usb/` representa o pen drive. `tests/` contém testes com dados controlados em diretórios temporários e limpeza automática.

## Segurança dos dados

Arquivos industriais reais não fazem parte do repositório público. O Git ignora todo o conteúdo de `repository/` e `simulated_usb/`, independentemente da extensão, mantendo apenas os `.gitkeep` das duas pastas. Isso inclui `.000`, `.112` e futuras extensões.

Arquivos de ambiente, configurações locais de IDE e caches Python também são ignorados. Não adicione dados industriais, pessoais ou credenciais ao código ou à documentação. O ignore não remove arquivos previamente rastreados nem impede adição forçada; revise os arquivos antes de publicar.

## Testes

Os testes automatizados usam `unittest`, sem dependências externas ou programas industriais reais. Na raiz do projeto, execute:

```powershell
python -B -m unittest discover -s tests -v
```

## Status

Projeto em desenvolvimento. Próximos objetivos, ainda não implementados:

- Cadastro automatizado de novos programas.
- Aprovação.
- Integração com USB real.
- Interface Windows.
- Backup.

## Tecnologias

Python, `pathlib`, `unittest` e biblioteca padrão Python. Sem frameworks ou dependências externas.
