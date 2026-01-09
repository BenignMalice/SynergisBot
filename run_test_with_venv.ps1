# PowerShell script to run tests with venv activated
cd "C:\Coding\MoneyBotv2.7 - 10 Nov 25"
.\.venv\Scripts\Activate.ps1
python test_simple.py | Out-File -FilePath test_output_venv.txt -Encoding utf8
Get-Content test_output_venv.txt

