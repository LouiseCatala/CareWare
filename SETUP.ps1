﻿$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$script:Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:PythonInstaller = Join-Path $script:Root 'prerequisites\python-3.11.9-amd64.exe'
$script:PythonExe = $null
$script:ActiveProcess = $null
$script:Mode = ''
$script:Steps = @()
$script:StepIndex = 0
$script:Installed = $false

$form = New-Object System.Windows.Forms.Form
$form.Text = 'CareWare Setup'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object System.Drawing.Size(650, 465)
$form.MinimumSize = New-Object System.Drawing.Size(650, 465)
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$form.BackColor = [System.Drawing.Color]::White

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Install CareWare'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 20, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(23, 43, 77)
$title.Location = New-Object System.Drawing.Point(28, 20)
$title.Size = New-Object System.Drawing.Size(580, 42)
$form.Controls.Add($title)

$intro = New-Object System.Windows.Forms.Label
$intro.Text = 'This setup includes the official Python 3.11.9 x64 installer. Install Python here, then install CareWare and create a Desktop shortcut.'
$intro.Location = New-Object System.Drawing.Point(30, 70)
$intro.Size = New-Object System.Drawing.Size(580, 42)
$intro.ForeColor = [System.Drawing.Color]::FromArgb(64, 83, 107)
$form.Controls.Add($intro)

$pythonStatus = New-Object System.Windows.Forms.Label
$pythonStatus.Location = New-Object System.Drawing.Point(30, 124)
$pythonStatus.Size = New-Object System.Drawing.Size(580, 28)
$pythonStatus.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($pythonStatus)

$checkButton = New-Object System.Windows.Forms.Button
$checkButton.Text = 'Check again'
$checkButton.Location = New-Object System.Drawing.Point(30, 160)
$checkButton.Size = New-Object System.Drawing.Size(140, 34)
$form.Controls.Add($checkButton)

$pythonButton = New-Object System.Windows.Forms.Button
$pythonButton.Text = 'Install Python 3.11'
$pythonButton.Location = New-Object System.Drawing.Point(182, 160)
$pythonButton.Size = New-Object System.Drawing.Size(180, 34)
$pythonButton.BackColor = [System.Drawing.Color]::FromArgb(232, 241, 255)
$form.Controls.Add($pythonButton)

$appButton = New-Object System.Windows.Forms.Button
$appButton.Text = 'Install CareWare'
$appButton.Location = New-Object System.Drawing.Point(374, 160)
$appButton.Size = New-Object System.Drawing.Size(205, 34)
$appButton.BackColor = [System.Drawing.Color]::FromArgb(44, 123, 229)
$appButton.ForeColor = [System.Drawing.Color]::White
$appButton.Enabled = $false
$form.Controls.Add($appButton)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Location = New-Object System.Drawing.Point(30, 210)
$progress.Size = New-Object System.Drawing.Size(580, 20)
$progress.Style = 'Blocks'
$form.Controls.Add($progress)

$state = New-Object System.Windows.Forms.Label
$state.Text = 'Checking this computer…'
$state.Location = New-Object System.Drawing.Point(30, 238)
$state.Size = New-Object System.Drawing.Size(580, 24)
$state.ForeColor = [System.Drawing.Color]::FromArgb(82, 98, 122)
$form.Controls.Add($state)

$log = New-Object System.Windows.Forms.TextBox
$log.Location = New-Object System.Drawing.Point(30, 268)
$log.Size = New-Object System.Drawing.Size(580, 135)
$log.Multiline = $true
$log.ReadOnly = $true
$log.ScrollBars = 'Vertical'
$log.BackColor = [System.Drawing.Color]::FromArgb(246, 248, 251)
$log.Text = 'CareWare stores customer and scan data on this computer. First-time setup needs an internet connection to download Python (if required) and app packages.'
$form.Controls.Add($log)

$footer = New-Object System.Windows.Forms.Label
$footer.Text = 'If automatic Python installation is unavailable, the setup window will offer the official Python download page.'
$footer.Location = New-Object System.Drawing.Point(30, 414)
$footer.Size = New-Object System.Drawing.Size(580, 24)
$footer.ForeColor = [System.Drawing.Color]::FromArgb(102, 117, 138)
$form.Controls.Add($footer)

function Add-Log([string]$Message) {
    $log.AppendText([Environment]::NewLine + $Message)
}

function Find-Python311 {
    $candidates = @()
    $command = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    $launcher = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'
    if (Test-Path $launcher) { $candidates += $launcher }
    $launcher = Join-Path $env:WINDIR 'py.exe'
    if (Test-Path $launcher) { $candidates += $launcher }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        try {
            $result = & $candidate -3.11 --version 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0 -and $result -match 'Python 3\.11') { return $candidate }
        } catch { }
    }
    return $null
}

function Refresh-PythonStatus {
    $script:PythonExe = Find-Python311
    if ($script:PythonExe) {
        $pythonStatus.Text = 'Python 3.11 is ready.'
        $pythonStatus.ForeColor = [System.Drawing.Color]::FromArgb(31, 157, 104)
        $pythonButton.Enabled = $false
        $appButton.Enabled = $true
        $state.Text = 'Ready to install CareWare.'
        Add-Log 'Python 3.11 detected.'
    } else {
        $pythonStatus.Text = 'Python 3.11 is not installed yet.'
        $pythonStatus.ForeColor = [System.Drawing.Color]::FromArgb(183, 121, 31)
        $pythonButton.Enabled = $true
        $appButton.Enabled = $false
        $state.Text = 'Install Python 3.11 first, then install CareWare.'
    }
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 400
$timer.Add_Tick({
    if (-not $script:ActiveProcess) { return }
    if (-not $script:ActiveProcess.HasExited) { return }
    $exitCode = $script:ActiveProcess.ExitCode
    $script:ActiveProcess = $null
    if ($exitCode -ne 0) {
        $timer.Stop()
        $progress.Style = 'Blocks'
        if ($script:Mode -eq 'Python') {
            Add-Log "Python installation ended with exit code $exitCode."
            Refresh-PythonStatus
            if (-not $script:PythonExe) {
                $state.Text = 'Automatic installation did not finish. Opening the official Python download page.'
                Start-Process 'https://www.python.org/downloads/windows/'
            }
        } else {
            $state.Text = "Setup step failed (exit code $exitCode). Check the log and try again."
            $state.ForeColor = [System.Drawing.Color]::FromArgb(197, 48, 48)
            Add-Log "A setup command failed with exit code $exitCode. Check the internet connection and retry."
            $checkButton.Enabled = $true
            $appButton.Enabled = $true
        }
        return
    }
    if ($script:Mode -eq 'Python') {
        $timer.Stop()
        $progress.Style = 'Blocks'
        $progress.Value = 0
        Refresh-PythonStatus
        if (-not $script:PythonExe) {
            $state.Text = 'Python was not detected. Use the official Python download button below.'
            Add-Log 'Python installation finished, but the Python 3.11 launcher was not detected.'
            Start-Process 'https://www.python.org/downloads/windows/'
        }
        return
    }
    if ($script:Mode -eq 'CareWare') {
        $script:StepIndex++
        if ($script:StepIndex -ge $script:Steps.Count) {
            $timer.Stop()
            $progress.Style = 'Blocks'
            $progress.Maximum = 100
            $progress.Value = 100
            $script:Mode = 'Done'
            $script:Installed = $true
            $appButton.Text = 'Launch CareWare'
            $appButton.Enabled = $true
            $checkButton.Enabled = $true
            $pythonButton.Enabled = $false
            $state.Text = 'CareWare is installed. A Desktop shortcut was created.'
            $state.ForeColor = [System.Drawing.Color]::FromArgb(31, 157, 104)
            Add-Log 'CareWare installation finished successfully.'
            try {
                $desktop = [Environment]::GetFolderPath('Desktop')
                $shell = New-Object -ComObject WScript.Shell
                $shortcut = $shell.CreateShortcut((Join-Path $desktop 'CareWare.lnk'))
                $shortcut.TargetPath = Join-Path $script:Root '.venv\Scripts\pythonw.exe'
                $shortcut.Arguments = '"' + (Join-Path $script:Root 'main.py') + '"'
                $shortcut.WorkingDirectory = $script:Root
                $shortcut.IconLocation = Join-Path $script:Root 'assets\careware.ico'
                $shortcut.Save()
            } catch { Add-Log 'The Desktop shortcut could not be created. Use Launch CareWare in this window.' }
        } else {
            Start-InstallStep
        }
    }
})

function Start-InstallStep {
    $step = $script:Steps[$script:StepIndex]
    $progress.Style = 'Blocks'
    $progress.Maximum = [Math]::Max(1, $script:Steps.Count)
    $progress.Value = [Math]::Min($script:StepIndex, $progress.Maximum)
    $state.Text = $step.Label
    Add-Log($step.Label)
    try {
        $script:ActiveProcess = Start-Process -FilePath $step.File -ArgumentList $step.Args -WorkingDirectory $script:Root -PassThru -WindowStyle Hidden
        $timer.Start()
    } catch {
        $state.Text = 'Could not start the setup step. Check the log and try again.'
        $state.ForeColor = [System.Drawing.Color]::FromArgb(197, 48, 48)
        Add-Log($_.Exception.Message)
        $script:ActiveProcess = $null
        $checkButton.Enabled = $true
        $appButton.Enabled = $true
    }
}

$checkButton.Add_Click({ Refresh-PythonStatus })
$pythonButton.Add_Click({
    if (-not (Test-Path $script:PythonInstaller)) {
        $state.Text = 'The bundled Python installer is missing. Opening python.org.'
        Add-Log 'The Python installer was not found in the prerequisites folder.'
        Start-Process 'https://www.python.org/downloads/windows/'
        return
    }
    $pythonButton.Enabled = $false
    $checkButton.Enabled = $false
    $appButton.Enabled = $false
    $progress.Style = 'Marquee'
    $state.Text = 'Installing the bundled Python 3.11.9 x64 runtime…'
    Add-Log 'Starting the official Python installer included with this setup package.'
    try {
        $script:Mode = 'Python'
        $script:ActiveProcess = Start-Process -FilePath $script:PythonInstaller -ArgumentList '/passive InstallAllUsers=0 Include_launcher=1 Include_pip=1 Include_tcltk=1 Include_test=0 PrependPath=0' -PassThru -WindowStyle Normal
        $timer.Start()
    } catch {
        $progress.Style = 'Blocks'
        $state.Text = 'Could not start the bundled Python installer.'
        Add-Log($_.Exception.Message)
        Start-Process 'https://www.python.org/downloads/windows/'
        $pythonButton.Enabled = $true
        $checkButton.Enabled = $true
    }
})

$appButton.Add_Click({
    $runtimeKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    $runtimeVersions = @(
        (Get-ItemProperty -LiteralPath ('HKCU:\' + $runtimeKey) -Name pv -ErrorAction SilentlyContinue).pv
        (Get-ItemProperty -LiteralPath ('HKLM:\' + $runtimeKey) -Name pv -ErrorAction SilentlyContinue).pv
        (Get-ItemProperty -LiteralPath ('HKLM:\Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') -Name pv -ErrorAction SilentlyContinue).pv
    )
    if (-not ($runtimeVersions | Where-Object { $_ -and $_ -ne '0.0.0.0' })) {
        [System.Windows.Forms.MessageBox]::Show('Install Microsoft Edge WebView2 Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and run CareWare Setup again.', 'WebView2 required')
        return
    }
    if (-not (Test-Path (Join-Path $script:Root 'ui\dist\index.html'))) {
        [System.Windows.Forms.MessageBox]::Show('The built interface is missing. Use the complete CareWare release package.', 'Incomplete package')
        return
    }
    if ($script:Installed) {
        Start-Process -FilePath (Join-Path $script:Root '.venv\Scripts\pythonw.exe') -ArgumentList ('"' + (Join-Path $script:Root 'main.py') + '"') -WorkingDirectory $script:Root
        return
    }
    if (-not $script:PythonExe) { Refresh-PythonStatus; return }
    $venvPython = Join-Path $script:Root '.venv\Scripts\python.exe'
    $script:Steps = @()
    if (-not (Test-Path $venvPython)) {
        $script:Steps += [pscustomobject]@{ File = $script:PythonExe; Args = '-3.11 -m venv "' + (Join-Path $script:Root '.venv') + '"'; Label = 'Creating the private CareWare Python environment…' }
    }
    $script:Steps += [pscustomobject]@{ File = $venvPython; Args = '-m pip install --disable-pip-version-check --upgrade pip setuptools'; Label = 'Preparing the package installer…' }
    $script:Steps += [pscustomobject]@{ File = $venvPython; Args = '-m pip install --disable-pip-version-check -r "' + (Join-Path $script:Root 'requirements.txt') + '"'; Label = 'Downloading and installing CareWare components…' }
    $script:Mode = 'CareWare'
    $script:StepIndex = 0
    $script:Installed = $false
    $checkButton.Enabled = $false
    $pythonButton.Enabled = $false
    $appButton.Enabled = $false
    Add-Log 'Installing CareWare inside its private folder. This may take a few minutes.'
    Start-InstallStep
})

$form.Add_Shown({ Refresh-PythonStatus })
[void]$form.ShowDialog()
$timer.Dispose()
