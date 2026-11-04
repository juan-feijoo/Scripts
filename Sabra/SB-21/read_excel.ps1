$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$wb = $excel.Workbooks.Open((Resolve-Path ".\Listado_cheques_Emitidos(5).xls").Path)
$sheet = $wb.Sheets.Item(1)
$data = @()
for ($r = 6; $r -le 25; $r++) {
    $obj = [PSCustomObject]@{
        Fila = $r
        FechaEmision = $sheet.Cells.Item($r, 1).Text.Trim()
        FechaPago = $sheet.Cells.Item($r, 2).Text.Trim()
        NroCheque = $sheet.Cells.Item($r, 3).Text.Trim()
        Importe = $sheet.Cells.Item($r, 4).Text.Trim()
        CUIT = $sheet.Cells.Item($r, 5).Text.Trim()
        RazonSocial = $sheet.Cells.Item($r, 6).Text.Trim()
        Estado = $sheet.Cells.Item($r, 7).Text.Trim()
    }
    $data += $obj
}
$wb.Close($false)
$excel.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
$data | Format-Table -AutoSize
$data | ConvertTo-Json -Depth 3 | Out-File -FilePath "cheques_extraidos.json" -Encoding utf8
Write-Output "Extracted $($data.Count) cheques successfully."
