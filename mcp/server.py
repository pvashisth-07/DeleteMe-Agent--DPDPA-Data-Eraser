import asyncio
import sys
from pathlib import Path

# Ensure site-packages mcp is resolved for MCP SDK
for p in list(sys.path):
    if "site-packages" in p:
        sys.path.remove(p)
        sys.path.insert(0, p)
        break

# Ensure project root is in sys.path
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from mcp.tools import draft_erasure_request_impl, find_grievance_contact_impl

# Create MCP Server instance
mcp_server = MCPServer("deleteme-mcp-server")


@mcp_server.tool()
async def find_grievance_contact(company: str) -> dict:
    """Discovers designated Grievance Officer and email address under DPDP Rules 2025 for a company."""
    return await find_grievance_contact_impl(company)


@mcp_server.tool()
async def draft_erasure_request(company: str, user_profile: dict) -> dict:
    """Drafts a DPDPA Section 12 erasure request with strict PII validation and content hash."""
    contact = await find_grievance_contact_impl(company)
    return draft_erasure_request_impl(
        company_name=contact["company_name"],
        recipient_email=contact["email"],
        user_profile=user_profile,
        verified=contact["verified"],
    )


if __name__ == "__main__":
    # Runs the MCP Server on stdio transport for IDE / Claude Desktop integration
    asyncio.run(mcp_server.run_stdio_async())
