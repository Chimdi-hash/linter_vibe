"""
GenLayer Studio Network - Sample Intelligent Contract
This contract matches the LinterVibe workflow and demonstrates the use of
deterministic execution and GenLayer decorators.

Deploy this code on the GenLayer Studio Network (https://studio.genlayer.com/)
and use its deployed contract address in the LinterVibe Dashboard.
"""

from genvm_decorators import genvm_callable, require_deterministic

class OracleAgreement:
    """
    A smart contract that securely stores and updates agreed data points.
    All state modifications must be strictly deterministic.
    """
    def __init__(self, initial_admin: str):
        self.admin = initial_admin
        self.data_records = {}
        self.total_agreements = 0

    @genvm_callable
    @require_deterministic
    def store_data(self, key: str, value: str, caller: str) -> bool:
        """
        Store deterministic data into the contract state.
        This function modifies state, so it must be deterministic.
        """
        if caller != self.admin:
            return False
        
        self.data_records[key] = value
        self.total_agreements += 1
        return True

    @genvm_callable
    def get_data(self, key: str) -> str:
        """
        Retrieve data from the contract.
        Since it doesn't modify state, it only needs @genvm_callable.
        """
        return self.data_records.get(key, "Not Found")
    
    @genvm_callable
    def get_total_agreements(self) -> int:
        return self.total_agreements

    # Example of what LinterVibe would catch if you uncommented this:
    # @genvm_callable
    # def generate_random_id(self) -> int:
    #     import random
    #     return random.randint(1, 1000) # LinterVibe will flag this as non-deterministic!
