$env:Path = 'C:\Users\Lenovo\Documents\Playground\tools\node-v22.14.0-win-x64;' + $env:Path
Set-Location 'C:\Users\Lenovo\Documents\Playground\app\frontend'
& '..\..\tools\node-v22.14.0-win-x64\npm.cmd' run build
& '..\..\tools\node-v22.14.0-win-x64\npm.cmd' run start
