# Servidor estático mínimo para probar la visita virtual en local (http://localhost:8765/)
param([string]$Root = (Join-Path $PSScriptRoot 'visita'), [int]$Port = 8765)
$types = @{ '.html' = 'text/html; charset=utf-8'; '.glb' = 'model/gltf-binary'; '.js' = 'text/javascript'; '.css' = 'text/css' }
$l = [System.Net.HttpListener]::new(); $l.Prefixes.Add("http://localhost:$Port/"); $l.Start()
Write-Host "Sirviendo $Root en http://localhost:$Port/"
while ($l.IsListening) {
  $ctx = $l.GetContext(); $path = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
  if ($path -eq '') { $path = 'index.html' }
  $file = Join-Path $Root $path
  if (Test-Path $file -PathType Leaf) {
    $bytes = [IO.File]::ReadAllBytes($file); $ext = [IO.Path]::GetExtension($file)
    $ctx.Response.ContentType = $(if ($types[$ext]) { $types[$ext] } else { 'application/octet-stream' })
    if ($ext -eq '.html') {   # el artifact añade el esqueleto html; en local lo añadimos aquí
      # política parecida a la de los artifacts: sin peticiones data: ni a otros dominios
      $ctx.Response.AddHeader('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data: blob:")
      $txt = '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>' + [Text.Encoding]::UTF8.GetString($bytes) + '</body></html>'
      $bytes = [Text.Encoding]::UTF8.GetBytes($txt)
    }
    $ctx.Response.ContentLength64 = $bytes.Length; $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
  } else { $ctx.Response.StatusCode = 404 }
  $ctx.Response.Close()
}
