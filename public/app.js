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
            // Disconnect user locally
            userAddress = null;
            walletText.textContent = 'Connect Wallet';
            connectBtn.classList.remove('connected');
            return;
        }

        if (typeof window.ethereum !== 'undefined') {
            try {
                // Request account access
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                
                if (accounts.length > 0) {
                    userAddress = accounts[0];
                    const shortAddress = `${userAddress.substring(0, 6)}...${userAddress.substring(userAddress.length - 4)}`;
                    
                    walletText.textContent = shortAddress;
                    connectBtn.classList.add('connected');
                    
                    // Optionally autofill if empty
                    if (!contractInput.value) {
                        contractInput.value = userAddress;
                    }
                }
            } catch (error) {
                console.error("User denied account access or error occurred", error);
                showError(error.message || "Failed to connect wallet.");
            }
        } else {
            showError("No Web3 wallet detected. Please install MetaMask or a compatible EVM wallet.");
        }
    });

    // Handle account changes
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

    // Analysis Logic
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

        setLoading(true);
        hideError();
        resultsContainer.style.display = 'none';

        if (!userAddress) {
            showError("Please connect your wallet first to authorize the Vibe Check.");
            setLoading(false);
            return;
        }

        try {
            // Request personal signature authorization
            const message = `Authorize LinterVibe to run a deterministic structural analysis on GenLayer StudioNet contract:\n\n${address}`;
            await window.ethereum.request({
                method: 'personal_sign',
                params: [message, userAddress]
            });
        } catch (signError) {
            console.error("Signature denied", signError);
            showError("You must sign the authorization message to proceed with the analysis.");
            setLoading(false);
            return;
        }

        try {
            // Call the robust Python backend which fetches from GenLayer Studio Network
            const response = await fetch(`/api/analyze-contract?address=${address}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || data.message || `HTTP Error ${response.status}`);
            }

            // The backend uses api_server.py which returns FullAnalysisResponse structure:
            // { analysis: { is_valid, errors, warnings, info: { functions, decorators, imports, forbidden_calls } }, source_data: { source_code } }
            // Note: If using lintervibe_backend.py, it's slightly different. We configured vercel.json to use api/index.py mapping to api_server.py.
            
            if (data.analysis) {
                 renderResults(address, data.analysis, data.source_data);
            } else if (data.status) {
                // Fallback if backend returned AnalysisResponse from lintervibe_backend.py
                renderResultsSimple(address, data);
            }

        } catch (err) {
            console.error(err);
            showError(err.message);
        } finally {
            setLoading(false);
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

        // Errors
        const errorsSection = document.getElementById('errorsSection');
        const errorsList = document.getElementById('errorsList');
        if (analysis.errors.length > 0) {
            errorsList.innerHTML = analysis.errors.map(err => `<li class="err-item">${escapeHtml(err)}</li>`).join('');
            errorsSection.style.display = 'block';
        } else {
            errorsSection.style.display = 'none';
        }

        // Warnings
        const warningsSection = document.getElementById('warningsSection');
        const warningsList = document.getElementById('warningsList');
        if (analysis.warnings.length > 0) {
            warningsList.innerHTML = analysis.warnings.map(warn => `<li class="warn-item">${escapeHtml(warn)}</li>`).join('');
            warningsSection.style.display = 'block';
        } else {
            warningsSection.style.display = 'none';
        }

        // Source snippet
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

    function renderResultsSimple(address, data) {
        document.getElementById('resAddress').textContent = address;
        
        const badge = document.getElementById('resBadge');
        if (data.status === 'success' && data.errors.length === 0) {
            badge.textContent = '● Deterministic & Valid';
            badge.className = 'status-badge status-valid';
        } else {
            badge.textContent = '⚠ Structural Issues Detected';
            badge.className = 'status-badge status-invalid';
        }

        document.getElementById('metricErrors').textContent = data.errors ? data.errors.length : 0;
        document.getElementById('metricWarnings').textContent = data.warnings ? data.warnings.length : 0;
        document.getElementById('metricFunctions').textContent = '-';

        // Errors
        const errorsSection = document.getElementById('errorsSection');
        const errorsList = document.getElementById('errorsList');
        if (data.errors && data.errors.length > 0) {
            errorsList.innerHTML = data.errors.map(err => `<li class="err-item">${escapeHtml(err)}</li>`).join('');
            errorsSection.style.display = 'block';
        } else {
            errorsSection.style.display = 'none';
        }

        // Warnings
        const warningsSection = document.getElementById('warningsSection');
        const warningsList = document.getElementById('warningsList');
        if (data.warnings && data.warnings.length > 0) {
            warningsList.innerHTML = data.warnings.map(warn => `<li class="warn-item">${escapeHtml(warn)}</li>`).join('');
            warningsSection.style.display = 'block';
        } else {
            warningsSection.style.display = 'none';
        }

        // Source snippet
        const sourceSection = document.getElementById('sourceSection');
        const sourceCode = document.getElementById('sourceCode');
        if (data.raw_code_snippet) {
            sourceCode.textContent = data.raw_code_snippet;
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