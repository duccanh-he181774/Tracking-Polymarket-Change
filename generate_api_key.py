from py_clob_client.client import ClobClient
import httpx
import ssl

# Your private key
private_key = "f7b76353f20131d123da5fb27e9073b60185a75b3fc870c77de98a649582c2db"

# Proxy configuration
proxy_url = "http://canhd5eumz:vs3RkucW@103.15.95.127:8113"

# Create temporary client to generate API credentials
print("Connecting to Polymarket CLOB with proxy...")

try:
    # Try with custom SSL context to avoid SSL errors
    import py_clob_client.http_helpers.helpers as http_helpers
    
    # Create a custom httpx client with proxy and relaxed SSL verification
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Override the global http client with proxy and custom SSL settings
    http_helpers._http_client = httpx.Client(
        proxy=proxy_url,
        verify=False,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )
    
    temp_client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137  # Polygon mainnet
    )
    
    # Generate API credentials
    print("Generating API credentials...")
    credentials = temp_client.create_or_derive_api_creds()
    
    # Display the credentials
    print("\n" + "="*60)
    print("POLYMARKET API CREDENTIALS")
    print("="*60)
    print(f"API Key: {credentials.api_key}")
    print(f"API Secret: {credentials.api_secret}")
    print(f"API Passphrase: {credentials.api_passphrase}")
    print("="*60)
    print("\nSave these credentials securely!")
    print("You can now use them to authenticate with Polymarket.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check your internet connection")
    print("2. Verify the private key is correct")
    print("3. Try disabling antivirus/firewall temporarily")
    print("4. Check if you can access https://clob.polymarket.com in your browser")
