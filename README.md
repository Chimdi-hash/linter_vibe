# 🌌 LinterVibe

**AI-Powered Smart Contract Analytics on GenLayer**

LinterVibe is a decentralized, Web3-native application built to ensure the structural integrity, determinism, and overall quality of **GenLayer Intelligent Contracts**. By leveraging GenLayer's unique LLM consensus mechanisms, LinterVibe not only lints your code but also gives it an AI-verified "Vibe Check."

---

## 🚀 Features

- **🧠 AI Consensus "Vibe Check"**: Your contract's code is evaluated by the network's Leader Validator using a Large Language Model (LLM). The rest of the validators verify the AI's judgment to reach consensus on the quality of your code, returning a short, engaging remark.
- **🛡️ Deterministic AST Analysis**: Analyzes Python-based GenLayer Intelligent Contracts for structural integrity. It detects unsafe standard library imports, missing `gl.public` decorators, and enforces GenLayer execution principles.
- **🔗 Decentralized Architecture**: The entire linter engine is deployed as an active Smart Contract (`LinterVibeContract.py`) on the GenLayer Studio Network. No centralized backend is required!
- **📱 Fully Mobile Responsive**: A premium, glassmorphism-inspired UI that works flawlessly on mobile Web3 wallets like MetaMask.
- **🔌 Automatic Network Switching**: Seamlessly prompts mobile and desktop wallets to switch to the GenLayer Studio Network (`Chain ID: 61999` / `0xf22f`) to prevent misdirected transactions.

---

## 🛠️ Technology Stack

- **Frontend**: Vanilla HTML/JS, Modern CSS (Glassmorphism, CSS Variables, Flexbox/Grid)
- **Web3 Integration**: `genlayer-js`, `viem`
- **Smart Contract (GenVM)**: Python (GenLayer Intelligent Contract SDK)
- **Deployment**: Vercel (Frontend), GenLayer StudioNet (Backend)

---

## ⚙️ Architecture

1. **User Input**: The user connects their Web3 wallet and submits a GenLayer contract address.
2. **Transaction Submission**: `app.js` triggers a transaction to the deployed `LinterVibeContract.py` on the GenLayer network.
3. **Execution (Sandbox)**:
   - The contract uses `gl.eq_principle.strict_eq` and `gl.nondet.web.request` to securely fetch the target contract's source code from the RPC.
   - It performs a deterministic Abstract Syntax Tree (AST) analysis on the code to generate warnings and errors.
4. **AI Evaluation (Nondeterministic)**:
   - The contract passes the analysis data to `gl.eq_principle.prompt_non_comparative`. 
   - Validators use their integrated LLMs to evaluate the code and reach a decentralized consensus on a "vibe check" remark.
5. **State Finalization**: The UI polls for the `ACCEPTED` state (handling AI latency automatically) and reads the final analytics payload from the blockchain state.

---

## 💻 Local Setup & Development

### Prerequisites
- [Node.js](https://nodejs.org/) installed on your machine.
- A Web3 Wallet (like [MetaMask](https://metamask.io/)) installed in your browser.

### 1. Clone the Repository
```bash
git clone https://github.com/Chimdi-hash/linter_vibe.git
cd linter_vibe
