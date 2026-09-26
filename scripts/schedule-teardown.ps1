<#
Schedules automatic deletion of the prototype's Azure resources.

Creates a Logic App (in its own resource group) with a system-assigned managed identity. On the
chosen date it DELETEs the app's resource group, then its own resource group, so nothing is left behind.
Before scheduling, it self-tests the mechanism on two empty throwaway resource groups.

Usage (PowerShell, after `az login`):
  .\scripts\schedule-teardown.ps1                          # defaults below
  .\scripts\schedule-teardown.ps1 -DeleteOnUtc 2026-12-01T17:00:00Z

Cancel anytime: az group delete -n rg-ttb-cleanup --yes
#>
param(
  [string]$AppResourceGroup = "rg-ttb-label-verifier",
  [string]$CleanupResourceGroup = "rg-ttb-cleanup",
  [string]$Location = "westus",
  [string]$DeleteOnUtc = "2026-11-26T17:00:00Z"
)
$ErrorActionPreference = "Stop"
$sub = az account show --query id -o tsv
$wf = "ttb-auto-delete"
$testA = "rg-ttb-deltest-a"; $testB = "rg-ttb-deltest-b"
$defFile = Join-Path $env:TEMP "ttb-teardown-workflow.json"

function Write-Definition([string]$first, [string]$second) {
  $auth = @{ type = "ManagedServiceIdentity"; audience = "https://management.azure.com/" }
  $uri = { param($rg) "https://management.azure.com/subscriptions/$sub/resourcegroups/$rg`?api-version=2021-04-01" }
  @{ definition = @{
      '$schema'      = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
      contentVersion = "1.0.0.0"
      triggers       = @{ Recurrence = @{ type = "Recurrence"; recurrence = @{ frequency = "Month"; interval = 12; startTime = $DeleteOnUtc } } }
      actions        = @{
        Delete_app_resource_group     = @{ type = "Http"; runAfter = @{}; inputs = @{ method = "DELETE"; uri = (& $uri $first); authentication = $auth } }
        Delete_cleanup_resource_group = @{ type = "Http"; runAfter = @{ Delete_app_resource_group = @("Succeeded", "Failed") }
                                           inputs = @{ method = "DELETE"; uri = (& $uri $second); authentication = $auth } }
      }
      outputs        = @{}
  } } | ConvertTo-Json -Depth 20 | Out-File -Encoding ascii $defFile
}

function Grant-Contributor([string]$principalId, [string]$rg) {
  az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
    --role Contributor --scope "/subscriptions/$sub/resourceGroups/$rg" --only-show-errors -o none
}

Write-Host "1/5 Creating resource groups..."
az group create -n $CleanupResourceGroup -l $Location --tags purpose="auto-delete $AppResourceGroup on $DeleteOnUtc" -o none
az group create -n $testA -l $Location -o none
az group create -n $testB -l $Location -o none

Write-Host "2/5 Creating Logic App (pointed at the throwaway test groups first)..."
Write-Definition $testA $testB
az logic workflow create -g $CleanupResourceGroup -n $wf -l $Location --definition $defFile --mi-system-assigned --state Enabled --only-show-errors -o none
$principal = az logic workflow show -g $CleanupResourceGroup -n $wf --query identity.principalId -o tsv

Write-Host "3/5 Granting the Logic App permission to delete ONLY these resource groups..."
foreach ($rg in $testA, $testB, $AppResourceGroup, $CleanupResourceGroup) { Grant-Contributor $principal $rg }
Start-Sleep -Seconds 60  # role assignments take a moment to propagate

Write-Host "4/5 Self-test: running it now against the empty test groups..."
az rest --method post --uri "https://management.azure.com/subscriptions/$sub/resourceGroups/$CleanupResourceGroup/providers/Microsoft.Logic/workflows/$wf/triggers/Recurrence/run?api-version=2016-06-01" -o none
$deleted = $false
for ($i = 0; $i -lt 36; $i++) {
  Start-Sleep -Seconds 5
  if ((az group exists -n $testA) -eq "false" -and (az group exists -n $testB) -eq "false") { $deleted = $true; break }
}
if (-not $deleted) {
  throw "Self-test failed: test groups still exist. Nothing real was scheduled. Check the run history of '$wf' in the Azure portal."
}
Write-Host "    Self-test passed: both test groups were deleted."

Write-Host "5/5 Pointing the Logic App at the real targets..."
Write-Definition $AppResourceGroup $CleanupResourceGroup
az logic workflow update -g $CleanupResourceGroup -n $wf --definition $defFile --only-show-errors -o none
Remove-Item $defFile

Write-Host ""
Write-Host "Done. '$AppResourceGroup' (and this cleanup job) will be deleted at $DeleteOnUtc."
Write-Host "To cancel: az group delete -n $CleanupResourceGroup --yes"
