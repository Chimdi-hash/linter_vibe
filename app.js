import { createClient, chains } from 'genlayer-js';

// The address of your deployed LinterVibeContract.py on StudioNet
// YOU MUST UPDATE THIS AFTER DEPLOYING LinterVibeContract.py
const LINTERVIBE_CONTRACT_ADDRESS = "0x0000000000000000000000000000000000000000";

document.addEventListener('DOMContentLoaded', () => {
    const connectBtn = document.getElementById('connectWalletBtn');
    const walletText = document.getElementById('walletAddressText');
    const contractInput = document.getElementById('contractInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const loader = analyzeBtn.querySelector('.loader');
    const globalError = document.getElementById('globalError');
    const globalErrorText = document.getElementById('globalErrorText');
    const resultsContainer = document.getElementById('resultsContainer');

    let userAddress = null;

    // Wallet Connection Logic
    connectBtn.addEventListener('click', async () => {
        if (userAddress) {
            userAddress = null;
            walletText.textContent = 'Connect Wallet';
            connectBtn.classList.remove('connected');
            return;
        }

        if (typeof window.ethereum !== 'undefined') {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                if (accounts.length > 0) {
                    userAddress = accounts[0];
                    const shortAddress = `${userAddress.substring(0, 6)}...${userAddress.substring(userAddress.length - 4)}`;
                    
                    walletText.textContent = shortAddress;
                    connectBtn.classList.add('connected');
                    
                    if (!contractInput.value) {
                        contractInput.value = userAddress;
                    }
                }
            } catch (error) {
                console.error("Wallet error", error);
                showError("Failed to connect wallet.");
            }
        } else {
            showError("No Web3 wallet detected. Please install a compatible EVM wallet.");
        }
    });

    if (typeof window.ethereum !== 'undefined') {
        window.ethereum.on('accountsChanged', (accounts) => {
            if (accounts.length > 0) {
                userAddress = accounts[0];
                const shortAddress = `${userAddress.substring(0, 6)}...${userAddress.substring(userAddress.length - 4)}`;
                walletText.textContent = shortAddress;
                connectBtn.classList.add('connected');
            } else {
                userAddress = null;
                walletText.textContent = 'Connect Wallet';
                connectBtn.classList.remove('connected');
            }
        });
    }

    contractInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performAnalysis();
    });

    analyzeBtn.addEventListener('click', performAnalysis);

    async function performAnalysis() {
        const address = contractInput.value.trim();

        if (!address || !/^0x[a-fA-F0-9]{40}$/.test(address)) {
            showError("Please enter a valid 40-character 0x-prefixed hex address.");
            return;
        }

        if (!userAddress) {
            showError("Please connect your wallet first to authorize the Vibe Check.");
            return;
        }
        
        if (LINTERVIBE_CONTRACT_ADDRESS === "0x0000000000000000000000000000000000000000") {
            showError("Developer: Please update LINTERVIBE_CONTRACT_ADDRESS in app.js after deploying the smart contract.");
            return;
        }

        setLoading(true);
        hideError();
        resultsContainer.style.display = 'none';

        try {
            // Wait for user to sign the transaction via MetaMask to execute the Vibe Check
            const client = createClient({ 
                chain: chains.studionet, 
                // Connect Viem-based GenLayer client to injected Ethereum provider (MetaMask)
                account: userAddress 
            });
            // Overriding custom transport behavior if needed, but normally genlayer-js wraps standard viem behavior
            // Since we must rely on window.ethereum for signatures, we'll try raw eth_sendTransaction if writeContract fails

            // Fallback strategy if createClient requires advanced setup:
            let txHash;
            try {
                // If genlayer-js supports window.ethereum out of the box with standard provider
                // We're signing a transaction to the GenLayer contract
                globalError.style.display = 'block';
                globalErrorText.textContent = "Please sign the transaction in your wallet to perform the Vibe Check on GenLayer...";
                globalErrorText.style.color = '#a0aec0'; // Info color
                
                txHash = await client.writeContract({
                    address: LINTERVIBE_CONTRACT_ADDRESS,
                    functionName: 'perform_vibe_check',
                    args: [address],
                    value: 0n, // Assuming GenLayer token amount
                });
            } catch (sdkErr) {
                console.warn("SDK writeContract failed, attempting manual RPC construction if necessary", sdkErr);
                throw sdkErr;
            }

            globalErrorText.textContent = `Transaction submitted (TxHash: ${txHash.substring(0, 10)}...). Waiting for GenLayer finality...`;

            // Wait for GenLayer validators to reach consensus on the Intelligent Contract execution
            await client.waitForTransactionReceipt({ hash: txHash });

            globalErrorText.textContent = `Transaction finalized. Reading analysis results from the contract state...`;

            // Read the deterministic result generated by the smart contract
            const rawResult = await client.readContract({
                address: LINTERVIBE_CONTRACT_ADDRESS,
                functionName: 'get_vibe_check_result',
                args: [address]
            });

            if (!rawResult || rawResult === "") {
                throw new Error("Analysis failed. Contract state empty.");
            }

            const data = JSON.parse(rawResult);

            if (data.analysis) {
                 renderResults(address, data.analysis, data.source_data);
                 hideError();
            } else {
                throw new Error("Invalid format returned from LinterVibe contract.");
            }

        } catch (err) {
            console.error(err);
            globalErrorText.style.color = '#f56565'; // Error color back
            showError(err.message || "Execution failed. Check console for details.");
        } finally {
            setLoading(false);
            globalErrorText.style.color = '#f56565';
        }
    }

    function renderResults(address, analysis, sourceData) {
        document.getElementById('resAddress').textContent = address;
        
        const badge = document.getElementById('resBadge');
        if (analysis.is_valid) {
            badge.textContent = '● Deterministic & Valid';
            badge.className = 'status-badge status-valid';
        } else {
            badge.textContent = '⚠ Structural Issues Detected';
            badge.className = 'status-badge status-invalid';
        }

        document.getElementById('metricErrors').textContent = analysis.errors.length;
        document.getElementById('metricWarnings').textContent = analysis.warnings.length;
        
        const functionCount = analysis.info && analysis.info.functions ? analysis.info.functions.length : 0;
        document.getElementById('metricFunctions').textContent = functionCount;

        const errorsSection = document.getElementById('errorsSection');
        const errorsList = document.getElementById('errorsList');
        if (analysis.errors.length > 0) {
            errorsList.innerHTML = analysis.errors.map(err => `<li class="err-item">${escapeHtml(err)}</li>`).join('');
            errorsSection.style.display = 'block';
        } else {
            errorsSection.style.display = 'none';
        }

        const warningsSection = document.getElementById('warningsSection');
        const warningsList = document.getElementById('warningsList');
        if (analysis.warnings.length > 0) {
            warningsList.innerHTML = analysis.warnings.map(warn => `<li class="warn-item">${escapeHtml(warn)}</li>`).join('');
            warningsSection.style.display = 'block';
        } else {
            warningsSection.style.display = 'none';
        }

        const sourceSection = document.getElementById('sourceSection');
        const sourceCode = document.getElementById('sourceCode');
        if (sourceData && sourceData.source_code) {
            const snippet = sourceData.source_code.substring(0, 1500) + (sourceData.source_code.length > 1500 ? '\n\n...[truncated]' : '');
            sourceCode.textContent = snippet;
            sourceSection.style.display = 'block';
        } else {
            sourceSection.style.display = 'none';
        }

        resultsContainer.style.display = 'block';
    }

    function setLoading(isLoading) {
        if (isLoading) {
            analyzeBtn.disabled = true;
            btnText.style.display = 'none';
            loader.style.display = 'block';
        } else {
            analyzeBtn.disabled = false;
            btnText.style.display = 'block';
            loader.style.display = 'none';
        }
    }

    function showError(msg) {
        globalErrorText.textContent = msg;
        globalError.style.display = 'block';
    }

    function hideError() {
        globalError.style.display = 'none';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});