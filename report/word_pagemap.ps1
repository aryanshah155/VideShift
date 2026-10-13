# Measure real page numbers with Microsoft Word and write report/pagemap.json.
#
#   powershell -ExecutionPolicy Bypass -File report/word_pagemap.ps1
#   powershell -ExecutionPolicy Bypass -File report/word_pagemap.ps1 -Pdf
#
# The printed page numbers count from Chapter 1 (its physical page is logical
# page 1), matching the page-number footer of the document body.

param(
    [string]$Docx = "$PSScriptRoot\VibeShift_MiniProject_Report.docx",
    [string]$Out  = "$PSScriptRoot\pagemap.json",
    [switch]$Pdf
)

$ErrorActionPreference = "Stop"
$path = (Resolve-Path $Docx).Path

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($path, $false, $false)
    $doc.Fields.Update() | Out-Null
    if ($doc.TablesOfContents.Count -gt 0) { $doc.TablesOfContents | ForEach-Object { $_.Update() } }
    $doc.Repaginate()

    $headings = @{}
    $figures  = @{}
    $tables   = @{}
    $offset   = 0
    $seen     = 0

    foreach ($p in $doc.Paragraphs) {
        $text = ($p.Range.Text -replace "[\r\a\t]", " ").Trim()
        if (-not $text) { continue }
        $seen++
        $style = $p.Style.NameLocal
        $page = [int]$p.Range.Information(3)   # wdActiveEndPageNumber

        if ($style -like "Heading*" -or $style -like "Chapter*") {
            if ($text -like "Chapter 1:*" -and $offset -eq 0) { $offset = $page - 1 }
            $headings[$text] = $page - $offset
        }
        elseif ($text -match "^Figure\s+(\d+\.\d+):") {
            $figures[$Matches[1]] = $page - $offset
        }
        elseif ($text -match "^Table\s+(\d+\.\d+):") {
            $tables[$Matches[1]] = $page - $offset
        }
    }

    $result = [ordered]@{
        pages    = [int]$doc.ComputeStatistics(2)   # wdStatisticPages
        offset   = $offset
        headings = $headings
        figures  = $figures
        tables   = $tables
    }
    $json = $result | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($Out, $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "pages=$($result.pages) offset=$offset headings=$($headings.Count) figures=$($figures.Count) tables=$($tables.Count)"

    if ($Pdf) {
        $pdfPath = [System.IO.Path]::ChangeExtension($path, ".pdf")
        $doc.SaveAs([ref]$pdfPath, [ref]17)   # wdFormatPDF
        Write-Output "pdf=$pdfPath"
    }

    $doc.Close($false)
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
