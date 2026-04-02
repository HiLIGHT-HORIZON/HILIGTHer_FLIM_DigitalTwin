import subprocess
import json
import io

def test_mcp_connection():
    # Prepare the initialize request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    
    request_str = json.dumps(request)
    full_request = f"{request_str}\n"
    
    # Run the server
    process = subprocess.Popen(
        ['python', 'python/mcp_server.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False
    )
    
    try:
        # Send the request
        stdout_data, stderr_data = process.communicate(input=full_request.encode('utf-8'), timeout=5)
        
        if stderr_data:
            print("Server Error Output (stderr):")
            print(stderr_data.decode('utf-8'))
            
        if stdout_data:
            # Parse response
            # Note: The output will have headers too, we need to skip them or parse them properly
            # Looking at _write_message: header + payload
            response_data = stdout_data.decode('utf-8')
            print("Server Response (stdout):")
            print(response_data)
            
            # Simple check if "hilighter-digital-twin-mcp" is in the output
            if "hilighter-digital-twin-mcp" in response_data:
                print("\nConnection Successful: HiLIGHTer MCP is responding correctly.")
            else:
                print("\nConnection Failed: Server responded but with unexpected data.")
        else:
            print("No response from server.")
            
    except subprocess.TimeoutExpired:
        process.kill()
        print("Test failed: Server timed out.")
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_mcp_connection()
