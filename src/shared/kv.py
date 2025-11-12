# Key Vault helper
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os


class KV:
    def __init__(self):
        self.client = SecretClient(vault_url=os.environ["KEY_VAULT_URI"], credential=DefaultAzureCredential())

    def get(self, name):
        return self.client.get_secret(name).value
