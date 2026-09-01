[CmdletBinding()]
param(
    [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName)]
    [Alias('Text', 'Path')]
    [string[]]$InputText,

    [ValidateRange(0, 4)]
    [int]$MaxDecodeLayers = 2
)

begin {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $allInputs = [System.Collections.Generic.List[string]]::new()

    function Get-PathTokens {
        param([Parameter(Mandatory)][string]$Text)

        $htmlDecoded = [System.Net.WebUtility]::HtmlDecode($Text)
        $quotedPattern = '["“”''](?<path>[A-Za-z]:[\\/][^"“”''\r\n]+?)["“”'']'
        $quotedMatches = [regex]::Matches($htmlDecoded, $quotedPattern)
        if ($quotedMatches.Count -gt 0) {
            return @($quotedMatches | ForEach-Object { $_.Groups['path'].Value })
        }

        $trimmed = $htmlDecoded.Trim().Trim('"', '''', '“', '”')
        if ($trimmed -match '^[A-Za-z]:[\\/]') {
            return @($trimmed)
        }

        return @()
    }

    function Decode-OneTransportLayer {
        param([Parameter(Mandatory)][string]$Value)

        # Decode only Markdown escapes relevant to Windows paths. Ordinary
        # separators such as \L or \Work remain unchanged.
        return [regex]::Replace($Value, '\\([\\_])', '$1')
    }
}

process {
    foreach ($entry in $InputText) {
        $allInputs.Add($entry)
    }
}

end {
    $results = [System.Collections.Generic.List[object]]::new()

    foreach ($entry in $allInputs) {
        $tokens = @(Get-PathTokens -Text $entry)
        if ($tokens.Count -eq 0) {
            $results.Add([pscustomobject]@{
                input = $entry
                status = 'no_path_token'
                resolved_path = $null
                candidates = @()
                existing_candidates = @()
            })
            continue
        }

        foreach ($token in $tokens) {
            $candidateSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
            $candidate = $token
            for ($layer = 0; $layer -le $MaxDecodeLayers; $layer++) {
                [void]$candidateSet.Add($candidate)
                $next = Decode-OneTransportLayer -Value $candidate
                if ($next -ceq $candidate) { break }
                $candidate = $next
            }

            $candidateRecords = @(
                foreach ($item in $candidateSet) {
                    $exists = Test-Path -LiteralPath $item
                    [pscustomobject]@{
                        path = $item
                        exists = $exists
                        item_type = if ($exists) {
                            if ((Get-Item -LiteralPath $item).PSIsContainer) { 'directory' } else { 'file' }
                        } else {
                            $null
                        }
                    }
                }
            )

            $existing = @($candidateRecords | Where-Object { $_.exists })
            $status = if ($existing.Count -eq 1) {
                'resolved'
            } elseif ($existing.Count -gt 1) {
                'ambiguous'
            } else {
                'not_found'
            }

            $resolved = if ($status -eq 'resolved') {
                [System.IO.Path]::GetFullPath($existing[0].path)
            } else {
                $null
            }

            $results.Add([pscustomobject]@{
                input = $entry
                extracted_path = $token
                status = $status
                resolved_path = $resolved
                candidates = $candidateRecords
                existing_candidates = @($existing | ForEach-Object { $_.path })
            })
        }
    }

    $results | ConvertTo-Json -Depth 6
}
