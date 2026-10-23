# Instalador do Editor Viral (e das outras skills) para Windows 10/11.
# Não rode este arquivo direto: dê dois cliques em INSTALAR.bat (ele chama este script).
$ErrorActionPreference = 'Continue'
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$origem = Join-Path $aqui 'skills'
$destino = Join-Path $env:USERPROFILE '.claude\skills'
Start-Transcript -Path (Join-Path $aqui 'instalacao.log') -Force | Out-Null

function Passo($n, $t) { Write-Host ''; Write-Host "[$n/7] $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Falha($t) { Write-Host "  ERRO  $t" -ForegroundColor Red }
function Atualizar-Path {
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Instalar($id, $nome, $comando) {
  if (Get-Command $comando -ErrorAction SilentlyContinue) { Ok "$nome já estava instalado"; return }
  Write-Host "  instalando $nome (pode demorar alguns minutos)..."
  winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements --scope user | Out-Host
  if ($LASTEXITCODE -ne 0) {
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
  }
  Atualizar-Path
  if (Get-Command $comando -ErrorAction SilentlyContinue) { Ok "$nome instalado" } else { Falha "$nome não instalou. Veja instalacao.log" }
}
function Achar-Python {
  foreach ($c in @('py -3', 'python')) {
    $partes = $c.Split(' ')
    try {
      $exe = & $partes[0] $partes[1..9] -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" 2>$null
      if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
    } catch {}
  }
  return $null
}

Write-Host '=============================================================' -ForegroundColor Magenta
Write-Host '  Instalando o Editor Viral. Leva de 10 a 25 minutos.' -ForegroundColor Magenta
Write-Host '  Deixe esta janela aberta até aparecer PRONTO.' -ForegroundColor Magenta
Write-Host '=============================================================' -ForegroundColor Magenta

Passo 1 'Conferindo o instalador do Windows (winget)'
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Falha 'winget não encontrado. Abra a Microsoft Store, procure "Instalador de Aplicativo", atualize e rode de novo.'
  Stop-Transcript | Out-Null; exit 1
}
Ok 'winget'

Passo 2 'Programas: Git, Python, ffmpeg e Node.js'
Instalar 'Git.Git' 'Git' 'git'
if (-not (Achar-Python)) { Instalar 'Python.Python.3.12' 'Python 3.12' 'py' }
Instalar 'Gyan.FFmpeg' 'ffmpeg' 'ffmpeg'
Instalar 'OpenJS.NodeJS.LTS' 'Node.js' 'node'
$py = Achar-Python
if (-not $py) { Falha 'Python não encontrado depois da instalação. Feche, abra de novo o INSTALAR.bat.'; Stop-Transcript | Out-Null; exit 1 }
Ok "Python em $py"
# o Claude chama "python3": cria esse nome ao lado do python.exe
$py3 = Join-Path (Split-Path $py) 'python3.exe'
if (-not (Test-Path $py3)) { Copy-Item $py $py3 -ErrorAction SilentlyContinue }

Passo 3 "Copiando as skills para $destino"
New-Item -ItemType Directory -Force -Path $destino | Out-Null
$skills = Get-ChildItem -Directory $origem
foreach ($s in $skills) {
  robocopy $s.FullName (Join-Path $destino $s.Name) /E /NFL /NDL /NJH /NJS /NP | Out-Null
  Ok $s.Name
}
$agentesOrigem = Join-Path $aqui 'agents'
if (Test-Path $agentesOrigem) {  # equipe do Creative Studio (/creative-studio) para qualquer pasta
  $agentesDestino = Join-Path $env:USERPROFILE '.claude\agents'
  New-Item -ItemType Directory -Force -Path $agentesDestino | Out-Null
  robocopy $agentesOrigem $agentesDestino /E /NFL /NDL /NJH /NJS /NP | Out-Null
  Ok 'equipe Creative Studio (7 especialistas)'
}

Passo 4 'Bibliotecas do Python'
& $py -m pip install --upgrade pip --quiet --disable-pip-version-check
foreach ($s in $skills) {
  $req = Join-Path (Join-Path $destino $s.Name) 'requirements.txt'
  if (Test-Path $req) {
    & $py -m pip install -r $req --quiet --disable-pip-version-check
    if ($LASTEXITCODE -eq 0) { Ok $s.Name } else { Falha "bibliotecas de $($s.Name)" }
  }
}

Passo 5 'Navegador das animações (Playwright + Chromium)'
Atualizar-Path
& npm.cmd install -g playwright --silent
& npx.cmd playwright install chromium
if ($LASTEXITCODE -eq 0) { Ok 'Playwright e Chromium' } else { Falha 'Playwright (as animações 3D não vão funcionar)' }

Passo 6 'Modelos de IA (transcrição, rosto, recorte, vozes) - cerca de 1 GB'
foreach ($s in $skills) {
  $setup = Join-Path (Join-Path $destino $s.Name) 'scripts\setup.py'
  if (Test-Path $setup) { & $py $setup --models }
}

Passo 7 'Conferindo tudo'
$tudoOk = $true
foreach ($s in $skills) {
  $setup = Join-Path (Join-Path $destino $s.Name) 'scripts\setup.py'
  if (Test-Path $setup) {
    $saida = & $py $setup 2>&1 | Out-String
    if ($saida -match 'READY') { Ok "$($s.Name) pronto" } else { $tudoOk = $false; Falha "$($s.Name):"; Write-Host $saida }
  }
}

Write-Host ''
if ($tudoOk) {
  Write-Host '=============================================================' -ForegroundColor Green
  Write-Host '  PRONTO! Agora:' -ForegroundColor Green
  Write-Host '  1. Feche e abra de novo o app do Claude.' -ForegroundColor Green
  Write-Host '  2. Clique no icone </> (Code), no canto de cima, a esquerda.' -ForegroundColor Green
  Write-Host '  3. Escolha a pasta onde estao os seus videos.' -ForegroundColor Green
  Write-Host '  4. Digite: /editor-video edita os videos desta pasta' -ForegroundColor Green
  Write-Host '=============================================================' -ForegroundColor Green
} else {
  Write-Host 'Quase lá: alguma parte falhou (em vermelho acima).' -ForegroundColor Yellow
  Write-Host 'Mande o arquivo instalacao.log (nesta pasta) para o suporte.' -ForegroundColor Yellow
}
Stop-Transcript | Out-Null
