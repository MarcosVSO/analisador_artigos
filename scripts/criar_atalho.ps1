<#
  Cria o atalho "Analisador de Artigos" na Area de Trabalho.

  Rode uma vez:
      powershell -ExecutionPolicy Bypass -File scripts\criar_atalho.ps1

  Use -Remover para apagar o atalho.
#>
param([switch]$Remover)

$ErrorActionPreference = 'Stop'

$pasta   = Split-Path -Parent $MyInvocation.MyCommand.Path
$raiz    = Split-Path -Parent $pasta
$alvo    = Join-Path $pasta 'Analisador de Artigos.bat'
$icone   = Join-Path $pasta 'icone.ico'

# GetFolderPath resolve a Area de Trabalho mesmo quando ela esta redirecionada
# para o OneDrive, que e o caso desta maquina.
$desktop = [Environment]::GetFolderPath('Desktop')
$atalho  = Join-Path $desktop 'Analisador de Artigos.lnk'

if ($Remover) {
  if (Test-Path $atalho) { Remove-Item $atalho; Write-Host "  Atalho removido." }
  else { Write-Host "  Nao havia atalho para remover." }
  return
}

foreach ($arquivo in @($alvo, $icone)) {
  if (-not (Test-Path $arquivo)) { throw "Arquivo nao encontrado: $arquivo" }
}

$shell = New-Object -ComObject WScript.Shell
$link  = $shell.CreateShortcut($atalho)
$link.TargetPath       = $alvo
$link.WorkingDirectory = $raiz
$link.IconLocation     = "$icone,0"
$link.Description      = 'Busca no Scopus, baixa os PDFs e analisa os artigos'
$link.WindowStyle      = 1
$link.Save()

Write-Host ""
Write-Host "  Atalho criado:"
Write-Host "    $atalho"
Write-Host "  Aponta para:"
Write-Host "    $alvo"
Write-Host ""
