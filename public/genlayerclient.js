/**
 * LinterVibe GenLayer Core Client
 * Interfaces directly with the GenLayer smart contract.
 */
class GenLayerClient {
    // Defines the contract address to read from, as requested.
    constructor(rpcUrl = 'https://studio.genlayer.com/api', registryAddress = '0xFa1C9aAE5FFFA7a76b6BC6f021f75BFcbe244EC6') {
        this.rpcUrl = rpcUrl;
        this.registryAddress = registryAddress;
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
     * Reads directly from the GenLayer smart contract via JSON-RPC
     * @param {string} contractAddress target contract to analyze
     * @returns {Promise<Object>}
     */
    async analyzeContract(contractAddress) {
        if (!this.isValidAddress(contractAddress)) {
            throw new Error("Invalid address format. Must be a valid 20-byte 0x hexadecimal string.");
        }

        try {
            const response = await fetch(this.rpcUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    id: Date.now(),
                    method: 'gen_call',
                    params: {
                        from: '0x0000000000000000000000000000000000000000',
                        to: this.registryAddress,
                        method: 'get_analysis',
                        args: [contractAddress]
                    }
                })
            });

            if (!response.ok) {
                throw new Error(`RPC HTTP Error: ${response.status}`);
            }

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error.message || 'Unknown RPC Error');
            }

            // data.result should be the dictionary returned by get_analysis
            // We parse it back into the format expected by app.js / index.html
            const result = data.result;
            return result;
        } catch (error) {
            console.error("GenLayerClient Error:", error);
            throw error;
        }
    }
}

// Export instance globally for app.js to consume safely
window.genLayerClient = new GenLayerClient();