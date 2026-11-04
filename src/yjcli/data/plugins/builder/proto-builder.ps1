# Code generation for the shared proto contract (yjcli builder plugin; repository-owned).
#
# Read tools/builder/GUIDE.md ("Proto contract"), then implement one Invoke-Gen<Language>
# function per language below. Everything else - finding the languages under
# proto\dist\, argument checks - already works.
# This is the entry point `make.ps1 proto-build` calls; builds of platforms that need
# the contract (e.g. backend-msa) call it first. It does not have to stay a single
# file: add helper scripts next to it and call them from here.
#
# Usage: tools/builder/proto/builder.ps1 [language]
param(
    [string]$Language = ""
)
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$ProtoDir = Join-Path $RootDir "proto"

# ---------------------------------------------------------------- implement me
# Invoke-Gen<Language>
#   Generate code from $ProtoDir\*.proto into $Out (= proto\dist\<language>\, which
#   also holds the library manifest - do not delete it). Remove generated files of
#   .proto files that no longer exist. Check $LASTEXITCODE after each native command.
{{#if proto_lang_go}}
function Invoke-GenGo {  # Go module {{proto_go_module}}
    Write-Host "proto codegen for go is not implemented - read tools/builder/GUIDE.md"
    exit 1
    # protoc -I $ProtoDir --go_out=$Out --go_opt=module={{proto_go_module}} `
    #   --go-grpc_out=$Out --go-grpc_opt=module={{proto_go_module}} (Get-ChildItem "$ProtoDir\*.proto")
    # Push-Location $Out; go mod tidy; Pop-Location
}
{{/if}}
{{#if proto_lang_dart}}
function Invoke-GenDart {  # Dart package {{proto_dart_package}}
    Write-Host "proto codegen for dart is not implemented - read tools/builder/GUIDE.md"
    exit 1
    # New-Item -ItemType Directory -Force -Path (Join-Path $Out "lib") | Out-Null
    # protoc -I $ProtoDir "--dart_out=grpc:$(Join-Path $Out 'lib')" (Get-ChildItem "$ProtoDir\*.proto")
}
{{/if}}
{{#if proto_lang_python}}
function Invoke-GenPython {  # Python package {{proto_python_package}}
    Write-Host "proto codegen for python is not implemented - read tools/builder/GUIDE.md"
    exit 1
    # $pkg = Join-Path $Out "{{proto_python_package}}"; New-Item -ItemType Directory -Force -Path $pkg | Out-Null
    # uv run --with grpcio-tools python -m grpc_tools.protoc -I $ProtoDir --python_out=$pkg `
    #   --pyi_out=$pkg --grpc_python_out=$pkg (Get-ChildItem "$ProtoDir\*.proto")
}
{{/if}}
# -----------------------------------------------------------------------------

$distDir = Join-Path $ProtoDir "dist"
if ($Language) {
    if (-not (Test-Path (Join-Path $distDir $Language) -PathType Container)) {
        Write-Host "unknown language: $Language (expected $distDir\$Language)"
        exit 1
    }
    $languages = @($Language)
} else {
    $languages = @(Get-ChildItem -Path $distDir -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name | ForEach-Object { $_.Name })
}
if ($languages.Count -eq 0) {
    Write-Host "no languages under $distDir"
    exit 1
}
if (-not (Get-ChildItem -Path $ProtoDir -Filter *.proto -File -ErrorAction SilentlyContinue)) {
    Write-Host "[proto] no .proto files in proto/ yet - nothing to generate"
    exit 0
}

foreach ($lang in $languages) {
    $Out = Join-Path $distDir $lang
    $fn = "Invoke-Gen" + $lang.Substring(0, 1).ToUpper() + $lang.Substring(1)
    if (-not (Get-Command $fn -CommandType Function -ErrorAction SilentlyContinue)) {
        Write-Host "[proto] $fn is not defined - add it to $PSCommandPath (see tools/builder/GUIDE.md)"
        exit 1
    }
    Write-Host "[proto] $lang -> proto/dist/$lang"
    $global:LASTEXITCODE = 0
    & $fn
    if ($LASTEXITCODE) {
        Write-Host "[proto] $lang failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}
Write-Host "[proto] done: $($languages -join ' ')"
