@echo off
setlocal
echo === AlgoKYC: Circom Trusted Setup (snarkjs CLI) ===
echo.

set SNARKJS=node node_modules/snarkjs/cli.js
set BUILD=build

echo [1/5] Powers of Tau - Phase 1 init (power=15)...
%SNARKJS% powersoftau new bn128 15 %BUILD%/pot15_0000.ptau
if errorlevel 1 goto :error

echo.
echo [2/5] Phase 1 contribution...
echo AlgoKYC entropy 2026 | %SNARKJS% powersoftau contribute %BUILD%/pot15_0000.ptau %BUILD%/pot15_0001.ptau
if errorlevel 1 goto :error

echo.
echo [3/5] Prepare Phase 2...
%SNARKJS% powersoftau prepare phase2 %BUILD%/pot15_0001.ptau %BUILD%/pot15_final.ptau
if errorlevel 1 goto :error

echo.
echo [4/5] Groth16 Phase 2 setup (zkey)...
%SNARKJS% groth16 setup %BUILD%/kyc.r1cs %BUILD%/pot15_final.ptau %BUILD%/kyc_0000.zkey
if errorlevel 1 goto :error

echo.
echo [5/5] Export verification key...
%SNARKJS% zkey export verificationkey %BUILD%/kyc_0000.zkey %BUILD%/verification_key.json
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  SETUP COMPLETE
echo  WASM:             build/kyc_js/kyc.wasm
echo  Proving key:      build/kyc_0000.zkey
echo  Verification key: build/verification_key.json
echo ============================================================
goto :eof

:error
echo ERROR: setup failed
exit /b 1
