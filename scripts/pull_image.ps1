param(
    [Parameter(Mandatory=$true)]
    [string]$ImageTag
)

# Exit immediately on error
$ErrorActionPreference = "Stop"

Write-Host "Pulling image: $ImageTag" -ForegroundColor Green

# Count slashes to determine image format
$slashCount = ($ImageTag -split '/' | Measure-Object).Count - 1

# Set mirror URL based on image format
switch ($slashCount) {
    0 {
        # No prefix (e.g., python:3.13-slim)
        $mirrorUrl = "m.daocloud.io/docker.io/library"
        Write-Host "Image format: Official image (no prefix)" -ForegroundColor Cyan
    }
    1 {
        # Single prefix (e.g., milvusdb/milvus:latest)
        $mirrorUrl = "m.daocloud.io/docker.io"
        Write-Host "Image format: Hub repository (one prefix)" -ForegroundColor Cyan
    }
    default {
        # Multiple prefixes (e.g., quay.io/coreos/etcd:v3.5.5)
        $mirrorUrl = "m.daocloud.io"
        Write-Host "Image format: Third-party registry (multiple prefixes)" -ForegroundColor Cyan
    }
}

$fullMirrorUrl = "$mirrorUrl/$ImageTag"
Write-Host "Mirror URL: $fullMirrorUrl" -ForegroundColor Yellow

try {
    # Pull image from mirror
    Write-Host "Step 1: Pulling image from mirror..." -ForegroundColor Blue
    docker pull $fullMirrorUrl

    # Retag to original name
    Write-Host "Step 2: Tagging image with original name..." -ForegroundColor Blue
    docker tag $fullMirrorUrl $ImageTag

    # Remove mirror tag
    Write-Host "Step 3: Removing mirror tag..." -ForegroundColor Blue
    docker rmi $fullMirrorUrl

    Write-Host "`nProcess completed successfully!" -ForegroundColor Green
    Write-Host "`nCurrent Docker images:" -ForegroundColor Yellow
    docker images

} catch {
    Write-Host "`nError occurred: $_" -ForegroundColor Red
    exit 1
}