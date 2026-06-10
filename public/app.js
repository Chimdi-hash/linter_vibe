/**
 * LinterVibe Minimalist UI Controller
 */
document.addEventListener('DOMContentLoaded', () => {
    // Select elements from your clean HTML layout
    const addressInput = document.getElementById('contract-address');
    const vibeCheckBtn = document.getElementById('vibe-check-btn');
    const outputSection = document.getElementById('analysis-output');
    const statusBadge = document.getElementById('status-badge');

    if (!vibeCheckBtn || !addressInput || !outputSection) {
        console.error("LinterVibe UI elements missing. Check your HTML element IDs.");
        return;
    }

    vibeCheckBtn.addEventListener('click', async () => {
        const address = addressInput.value.trim();

        // 1. Client-side sanity check
        if (!address) {
            updateUIError("Please enter a GenLayer contract address.");
            return;
        }

        // 2. Set UI into loading state
        setLoadingState(true);

        try {
            // 3. Trigger network query execution through the client
            const data = await window.genLayerClient.analyzeContract(address);

            // 4. Render clean results
            renderResults(data);
        } catch (err) {
            // 5. Catch compile errors or node sync drops cleanly
            updateUIError(err.message);
        } finally {
            setLoadingState(false);
        }
    });

    function setLoadingState(isLoading) {
        if (isLoading) {
            vibeCheckBtn.disabled = true;
            vibeCheckBtn.textContent = "Analyzing bytecode stream...";
            outputSection.style.opacity = "0.5";
            if (statusBadge) statusBadge.textContent = "QUERYING NODE...";
        } else {
            vibeCheckBtn.disabled = false;
            vibeCheckBtn.textContent = "Vibe Check Contract";
            outputSection.style.opacity = "1";
        }
    }

    function renderResults(data) {
        // Clear previous runs
        outputSection.innerHTML = '';

        if (statusBadge) {
            statusBadge.textContent = data.is_deterministic ? "PASSED" : "NON-DETERMINISTIC WARNING";
            statusBadge.className = data.is_deterministic ? "badge-success" : "badge-warning";
        }

        // Beautifully append contract data metadata blocks
        const layout = `
            <div class="result-card">
                <h3>📜 Deployed Source Code Stream</h3>
                <pre><code>${escapeHtml(data.source_code || '# No code returned')}</code></pre>
            </div>
            <div class="result-card lint-report">
                <h3>🔍 Linter Validation Results</h3>
                <p><strong>Status:</strong> ${data.is_deterministic ? '🟢 Valid Deterministic Layout' : '🔴 Issues Detected'}</p>
                <ul>
                    ${data.logs.map(log => `<li>⚠️ ${escapeHtml(log)}</li>`).join('') || '<li>✅ Perfect score! No forbidden imports or state structural anomalies found.</li>'}
                </ul>
            </div>
        `;
        outputSection.innerHTML = layout;
    }

    function updateUIError(errorMessage) {
        outputSection.innerHTML = `
            <div class="error-card" style="border: 1px solid #ff3333; color: #ff3333; padding: 15px; margin-top: 15px;">
                <strong>Compilation / Query Error:</strong>
                <p>${escapeHtml(errorMessage)}</p>
            </div>
        `;
        if (statusBadge) {
            statusBadge.textContent = "FAILED";
            statusBadge.className = "badge-danger";
        }
    }

    function escapeHtml(str) {
        return str.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});