# Quick test script to submit message and check logs for spacing issues
# PowerShell version

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "SPACING BUG DEBUG TEST" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$API_URL = if ($env:API_URL) { $env:API_URL } else { "http://localhost:8000" }
$API_KEY = if ($env:API_KEY) { $env:API_KEY } else { "demo-lab-api-key-change-in-production" }
$PERSONA_ID = if ($env:PERSONA_ID) { $env:PERSONA_ID } else { "your-persona-id" }
$DATASET_ID = if ($env:DATASET_ID) { $env:DATASET_ID } else { "your-dataset-id" }

Write-Host "Configuration:"
Write-Host "  API URL: $API_URL"
Write-Host "  Persona ID: $PERSONA_ID"
Write-Host "  Dataset ID: $DATASET_ID"
Write-Host ""

# Test message
$TEST_MESSAGE = "Bagaimana cara reset password saya? Saya lupa password dan tidak bisa login ke aplikasi."

Write-Host "Submitting test message..."
Write-Host "Message: $TEST_MESSAGE"
Write-Host ""

# Submit request
$body = @{
    message = $TEST_MESSAGE
    persona_id = $PERSONA_ID
    dataset_id = $DATASET_ID
    session_id = "test-spacing-debug-$(Get-Date -Format 'yyyyMMddHHmmss')"
    user_id = "test-user-spacing"
} | ConvertTo-Json

$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key" = $API_KEY
}

try {
    $response = Invoke-RestMethod -Uri "$API_URL/api/v1/queue/submit" -Method Post -Headers $headers -Body $body
    
    Write-Host "API Response:"
    $response | ConvertTo-Json -Depth 3
    Write-Host ""
    
    $TASK_ID = $response.task_id
    
    if (-not $TASK_ID) {
        Write-Host "❌ Failed to get task_id from response" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Task ID: $TASK_ID" -ForegroundColor Green
    Write-Host ""
    
    # Wait for processing
    Write-Host "Waiting 5 seconds for processing..."
    Start-Sleep -Seconds 5
    
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "CHECKING WORKER LOGS FOR SPACING DEBUG OUTPUT" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check Docker logs
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "Checking Docker container logs..."
        Write-Host ""
        
        # Try to find chat worker container
        $containers = docker ps --filter "name=chat" --format "{{.Names}}"
        
        if ($containers) {
            $CONTAINER = ($containers -split "`n")[0]
            Write-Host "Found container: $CONTAINER" -ForegroundColor Green
            Write-Host ""
            
            Write-Host "--- SPACING DEBUG OUTPUT ---" -ForegroundColor Yellow
            $logs = docker logs $CONTAINER --tail 300
            $debugLogs = $logs | Select-String -Pattern "SPACING DEBUG" -Context 0,30
            
            if ($debugLogs) {
                $debugLogs | ForEach-Object { Write-Host $_.Line }
            } else {
                Write-Host "No spacing debug logs found" -ForegroundColor Yellow
            }
            
            Write-Host ""
            Write-Host "--- SPACING ISSUES (if any) ---" -ForegroundColor Yellow
            $issueLogs = $logs | Select-String -Pattern "SPACING ISSUE"
            
            if ($issueLogs) {
                $issueLogs | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
            } else {
                Write-Host "No spacing issues detected" -ForegroundColor Green
            }
        } else {
            Write-Host "⚠️  No chat worker container found" -ForegroundColor Yellow
            Write-Host "Tip: Check manually with: docker logs <container-name>"
        }
    } else {
        Write-Host "⚠️  Docker not found. Check logs manually." -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "GET TASK RESULT" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Get task result
    $result = Invoke-RestMethod -Uri "$API_URL/api/v1/queue/$TASK_ID" -Method Get
    $result | ConvertTo-Json -Depth 5
    
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "NEXT STEPS" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Check the logs above for '🚨 SPACING ISSUES DETECTED'" -ForegroundColor Yellow
Write-Host "2. Look at 'Response repr' to see hidden characters" -ForegroundColor Yellow
Write-Host "3. Compare 'Response preview' with expected format" -ForegroundColor Yellow
Write-Host "4. If issues found, implement text_cleaner.py fix" -ForegroundColor Yellow
Write-Host ""
Write-Host "To check logs manually:"
Write-Host "  docker logs <container-name> --tail 500 | Select-String 'SPACING DEBUG' -Context 0,50"
Write-Host ""
