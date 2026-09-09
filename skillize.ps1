$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$pyproject = Join-Path $here "pyproject.toml"
if ((Test-Path $pyproject) -and (
    Select-String -LiteralPath $pyproject -Pattern '^name = "skillize"' -Quiet
)) {
    & uv run --project $here skillize @args
    exit $LASTEXITCODE
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("skillize: uv is not on PATH")
    exit 1
}
$uvx = @()
if ($env:SKILLIZE_OFFLINE) {
    $uvx += "--offline"
} else {
    $uvx += "--refresh"
}
& uvx @uvx --from git+https://github.com/pleware/skillize.git skillize @args
exit $LASTEXITCODE
