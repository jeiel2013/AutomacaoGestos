@echo off
:: install.bat
:: Instala dependências do projeto no Windows 10/11.
:: Execute como Administrador ou em ambiente com Python no PATH.

echo === Gesture Control — instalacao Windows ===
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado no PATH.
    echo Instale em: https://www.python.org/downloads/
    echo Marque "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias Python...
python -m pip install --upgrade pip
python -m pip install ^
    opencv-python ^
    mediapipe ^
    pyautogui ^
    pystray ^
    pillow

if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [2/3] Verificando modelo MediaPipe...
if not exist "hand_landmarker.task" (
    echo Baixando hand_landmarker.task...
    curl -L -o hand_landmarker.task ^
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    if errorlevel 1 (
        echo ERRO: Falha ao baixar o modelo.
        echo Baixe manualmente em:
        echo https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
        echo e coloque na pasta do projeto.
        pause
        exit /b 1
    )
    echo Modelo baixado com sucesso.
) else (
    echo Modelo ja existe. OK.
)

echo.
echo [3/3] Criando atalho na Area de Trabalho...
set SCRIPT_DIR=%~dp0
set SHORTCUT=%USERPROFILE%\Desktop\Gesture Control.lnk

:: Cria o atalho via PowerShell
powershell -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s = $ws.CreateShortcut('%SHORTCUT%'); ^
     $s.TargetPath = 'pythonw'; ^
     $s.Arguments = '\"%SCRIPT_DIR%tray_icon.py\"'; ^
     $s.WorkingDirectory = '%SCRIPT_DIR%'; ^
     $s.IconLocation = 'shell32.dll,175'; ^
     $s.WindowStyle = 7; ^
     $s.Save()"

if exist "%SHORTCUT%" (
    echo Atalho criado na Area de Trabalho.
) else (
    echo Aviso: nao foi possivel criar o atalho automaticamente.
    echo Execute manualmente: pythonw tray_icon.py
)

echo.
echo === Instalacao concluida! ===
echo.
echo PROXIMOS PASSOS:
echo.
echo   1. Teste os gestos com a camera:
echo      python debug_landmarks.py
echo.
echo   2. Inicie o Gesture Control:
echo      pythonw tray_icon.py
echo      ou clique duas vezes em "Gesture Control" na Area de Trabalho
echo.
echo   3. O icone aparecera na bandeja (canto inferior direito)
echo.
pause
