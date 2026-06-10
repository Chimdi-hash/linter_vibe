/**
 * LinterVibe GenLayer Core Client
 * Interfaces directly with the Python local node bridging layer
 */
class GenLayerClient {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
    }

    /**
     * Validates if a string matches standard Ethereum/GenLayer 20-byte hex formatting
     * @param {string} address 
     * @returns {boolean}
     */
    isValidAddress(address) {
        const regex = /^0x[a-fA-F0-9]{40}$/;
        return regex.test(address);
    }

    /**
     * Sends the contract address to the backend for live code extraction and AST validation
     * @param {string} contractAddress 
     * @returns {Promise<Object>}
     */
    async analyzeContract(contractAddress) {
        if (!this.isValidAddress(contractAddress)) {
            throw new Error("Invalid address format. Must be a valid 20-byte 0x hexadecimal string.");
        }

        try {
            const response = await fetch(`${this.baseURL}/api/analyze-contract`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ address: contractAddress })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server returned status code ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error("GenLayerClient Error:", error);
            throw error;
        }
    }
}

// Export instance globally for app.js to consume safely
window.genLayerClient = new GenLayerClient();